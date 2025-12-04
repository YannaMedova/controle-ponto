import flet as ft
import json
import os
import shutil
from datetime import datetime, timedelta
import calendar
import locale
import re
import hashlib
# >>> FIX FUSO HORÁRIO (Brasil - Brasília)
import os, time
# define TZ para São Paulo / Brasília
os.environ["TZ"] = "America/Sao_Paulo"
# time.tzset() funciona em Linux (servidores). Envolvemos em try/except por segurança.
try:
    time.tzset()
except Exception:
    # No Windows ou ambientes sem suporte, ignoramos sem travar
    pass


# --- BIBLIOTECAS OPCIONAIS PARA EXPORTAÇÃO E PDF ---
try:
    import pandas as pd
    from fpdf import FPDF
except ImportError:
    print("AVISO: Para usar a exportação, instale: pip install pandas openpyxl fpdf")

try:
    import pdfplumber
except ImportError:
    print("AVISO: Para importar PDF, instale: pip install pdfplumber")
    pdfplumber = None

# Tenta configurar o idioma do sistema para Português-BR
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    pass

# --- CONFIGURAÇÕES GLOBAIS ---
ARQUIVO_DADOS = "dados_ponto.json"
ARQUIVO_CONFIG = "config.json"  # Arquivo para salvar as preferências


# --- CLASSE DE GERENCIAMENTO DE FERIADOS ---
class GerenciadorFeriados:
    """Classe utilitária para verificar feriados nacionais e do DF (Brasília)."""

    @staticmethod
    def calcular_pascoa(ano):
        """Calcula a data da Páscoa usando o algoritmo de Meeus/Jones/Butcher."""
        a = ano % 19
        b = ano // 100
        c = ano % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        mes = (h + l - 7 * m + 114) // 31
        dia = ((h + l - 7 * m + 114) % 31) + 1
        return datetime(ano, mes, dia).date()

    @staticmethod
    def obter_feriados(ano):
        pascoa = GerenciadorFeriados.calcular_pascoa(ano)
        carnaval = pascoa - timedelta(days=47)
        sexta_santa = pascoa - timedelta(days=2)
        corpus_christi = pascoa + timedelta(days=60)

        feriados = {
            f"{ano}-01-01", f"{ano}-04-21", f"{ano}-05-01", f"{ano}-09-07",
            f"{ano}-10-12", f"{ano}-11-02", f"{ano}-11-15", f"{ano}-11-20", f"{ano}-12-25",
            f"{ano}-04-21", f"{ano}-11-30",  # Distritais DF
            carnaval.strftime("%Y-%m-%d"), sexta_santa.strftime("%Y-%m-%d"), corpus_christi.strftime("%Y-%m-%d"),
        }
        return feriados

    @staticmethod
    def eh_feriado(data_date):
        feriados_ano = GerenciadorFeriados.obter_feriados(data_date.year)
        return data_date.strftime("%Y-%m-%d") in feriados_ano


# --- CLASSE PRINCIPAL (BACKEND) ---
class ControlePontoApp:
    def __init__(self):
        self.config = self.carregar_config()  # Carrega config primeiro
        self.dados = self.carregar_dados()

    def carregar_dados(self):
        if os.path.exists(ARQUIVO_DADOS):
            try:
                with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def carregar_config(self):
        """Carrega configurações do usuário (Meta, Fatores, Tema)."""
        default = {
            "meta_diaria": 8,
            "fator_dia_util": 1.0,  # Multiplicador normal
            "fator_fds": 2.0,  # Multiplicador FDS (Dobro)
            "tema_inicial": "light",
            "data_inicio_contagem": None,  # Data de corte para o banco de horas
            "ultimo_hash_pdf": None  # Armazena o hash do último PDF importado
        }
        if os.path.exists(ARQUIVO_CONFIG):
            try:
                with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
                    salvo = json.load(f)
                    # Garante que todas as chaves existam mesclando
                    for k, v in default.items():
                        if k not in salvo:
                            salvo[k] = v
                    return salvo
            except:
                return default
        return default

    def salvar_dados(self):
        with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
            json.dump(self.dados, f, indent=4, ensure_ascii=False)

    def salvar_config(self, meta=None, f_util=None, f_fds=None, tema=None):
        # Atualiza apenas o que for passado
        if meta is not None: self.config["meta_diaria"] = meta
        if f_util is not None: self.config["fator_dia_util"] = f_util
        if f_fds is not None: self.config["fator_fds"] = f_fds
        if tema is not None: self.config["tema_inicial"] = tema

        with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def zerar_banco_horas(self):
        """Define a data de hoje como o início da contagem, arquivando o passado virtualmente."""
        self.config["data_inicio_contagem"] = datetime.now().strftime("%Y-%m-%d")
        with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def obter_hoje_str(self):
        return datetime.now().strftime("%Y-%m-%d")

    def converter_input_tempo_para_minutos(self, valor_str):
        valor_str = valor_str.strip()
        try:
            if ":" in valor_str:
                sinal = 1
                if valor_str.startswith("-"):
                    sinal = -1
                    valor_str = valor_str.replace("-", "")
                partes = valor_str.split(":")
                horas = int(partes[0])
                minutos = int(partes[1])
                total = (horas * 60) + minutos
                return total * sinal
            else:
                return int(valor_str)
        except:
            return 0

    def calcular_segundos_trabalhados(self, horarios):
        total_segundos = 0
        formato = "%H:%M"
        for i in range(0, len(horarios), 2):
            if i + 1 < len(horarios):
                try:
                    entrada = datetime.strptime(horarios[i], formato)
                    saida = datetime.strptime(horarios[i + 1], formato)
                    total_segundos += (saida - entrada).total_seconds()
                except ValueError:
                    pass  # Ignora horários inválidos
        return total_segundos

    def formatar_duracao(self, segundos):
        sinais = ""
        if segundos < 0:
            sinais = "-"
            segundos = abs(segundos)
        horas = int(segundos // 3600)
        minutos = int((segundos % 3600) // 60)
        return f"{sinais}{horas:02d}:{minutos:02d}"

    def obter_saldo_dia(self, data_str, info_dia):
        """Calcula saldo usando as configurações personalizadas."""
        horarios = info_dia.get("batidas", [])
        ajuste_manual_min = info_dia.get("ajuste_manual", 0)
        eh_folga = info_dia.get("folga", False)

        # Retorna 4 valores para evitar erro de unpack
        if eh_folga:
            return 0, 0, 0, False

        total_trabalhado_seg = self.calcular_segundos_trabalhados(horarios)

        # --- CORREÇÃO AQUI: Tratamento de erro para data inválida ---
        try:
            data_obj = datetime.strptime(data_str, "%Y-%m-%d")
        except ValueError:
            # Se a data for "null" ou inválida, retorna zerado para não travar o app
            print(f"AVISO: Data inválida ignorada: {data_str}")
            return 0, 0, 0, False
            # -----------------------------------------------------------

        eh_fds = data_obj.weekday() >= 5
        eh_feriado = GerenciadorFeriados.eh_feriado(data_obj.date())

        # --- APLICAÇÃO DAS CONFIGURAÇÕES ---
        meta_horas = self.config.get("meta_diaria", 8)
        fator_util = self.config.get("fator_dia_util", 1.0)
        fator_fds = self.config.get("fator_fds", 2.0)

        meta_segundos = meta_horas * 3600
        saldo_segundos = 0

        if eh_fds or eh_feriado:
            # FDS/Feriado: Meta 0, aplica multiplicador configurado
            meta_segundos = 0
            saldo_segundos = total_trabalhado_seg * fator_fds
        else:
            # Dia Útil
            saldo_bruto = total_trabalhado_seg - meta_segundos
            # Aplica multiplicador apenas se for hora extra (positivo)
            if saldo_bruto > 0:
                saldo_segundos = saldo_bruto * fator_util
            else:
                saldo_segundos = saldo_bruto

        saldo_final = saldo_segundos + (ajuste_manual_min * 60)

        return total_trabalhado_seg, meta_segundos, saldo_final, eh_feriado

    def registrar_batida(self, data_str, hora_str):
        if data_str not in self.dados:
            self.dados[data_str] = {"batidas": [], "ajuste_manual": 0, "folga": False}

        if hora_str not in self.dados[data_str]["batidas"]:
            self.dados[data_str]["batidas"].append(hora_str)
            self.dados[data_str]["batidas"].sort()
            self.salvar_dados()
            return True
        return False

    def atualizar_batida(self, data, hora_antiga, hora_nova):
        if data in self.dados and hora_antiga in self.dados[data]["batidas"]:
            self.dados[data]["batidas"].remove(hora_antiga)
            self.dados[data]["batidas"].append(hora_nova)
            self.dados[data]["batidas"].sort()
            self.salvar_dados()
            return True
        return False

    def remover_batida(self, data_str, hora_str):
        if data_str in self.dados and hora_str in self.dados[data_str]["batidas"]:
            self.dados[data_str]["batidas"].remove(hora_str)
            self.salvar_dados()

    def bater_ponto_agora(self):
        hoje = self.obter_hoje_str()
        agora = datetime.now().strftime("%H:%M")
        self.registrar_batida(hoje, agora)
        return f"Ponto batido às {agora}"

    def ajustar_manual(self, data, minutos):
        if data in self.dados:
            self.dados[data]["ajuste_manual"] = minutos
            self.salvar_dados()

    # ALTERAÇÃO: Agora aceita parâmetro opcional 'eh_ferias'
    def definir_folga(self, data, status, eh_ferias=False):
        if data not in self.dados:
            self.dados[data] = {"batidas": [], "ajuste_manual": 0, "folga": False}

        self.dados[data]["folga"] = status

        # Salva uma marcação especial se for férias
        if status and eh_ferias:
            self.dados[data]["is_ferias"] = True
        else:
            # Se desmarcar ou se for folga normal, remove a marcação de férias
            self.dados[data]["is_ferias"] = False

        self.salvar_dados()

    # --- NOVA FUNÇÃO: REGISTRAR PERÍODO DE FÉRIAS ---
    def registrar_ferias_lote(self, data_ini_str, data_fim_str):
        """Define folga para todos os dias no intervalo."""
        dt_ini = datetime.strptime(data_ini_str, "%Y-%m-%d")
        dt_fim = datetime.strptime(data_fim_str, "%Y-%m-%d")

        delta = (dt_fim - dt_ini).days
        if delta < 0: return  # Data fim menor que inicio

        for i in range(delta + 1):
            dia = dt_ini + timedelta(days=i)
            dia_str = dia.strftime("%Y-%m-%d")
            # AQUI: Passa o True para dizer que é férias
            self.definir_folga(dia_str, True, eh_ferias=True)

        self.salvar_dados()

    def excluir_dia(self, data):
        if data in self.dados:
            del self.dados[data]
            self.salvar_dados()

    def limpar_tudo(self):
        # ESTE MÉTODO AGORA É ZERAR BANCO
        self.zerar_banco_horas()

    def calcular_dias_uteis_mes(self, ano, mes):
        cal = calendar.monthcalendar(ano, mes)
        dias_uteis = 0
        for semana in cal:
            for dia_da_semana in range(0, 5):  # 0-4 = Seg a Sex
                dia_mes = semana[dia_da_semana]
                if dia_mes != 0:
                    data_atual = datetime(ano, mes, dia_mes).date()
                    if not GerenciadorFeriados.eh_feriado(data_atual):
                        dias_uteis += 1
        return dias_uteis

    def gerar_dataframe_exportacao(self, mes_filtro=None):
        """Prepara dados para Pandas exportar."""
        registros = []
        dias_pt = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        datas_ordenadas = sorted(self.dados.keys())

        for data in datas_ordenadas:
            if mes_filtro and not data.startswith(mes_filtro):
                continue

            info = self.dados[data]
            trabalhado, meta, saldo, eh_feriado = self.obter_saldo_dia(data, info)

            dt_obj = datetime.strptime(data, "%Y-%m-%d")
            dia_semana = dias_pt[dt_obj.weekday()]

            batidas_str = " | ".join(info['batidas'])
            ajuste = info.get("ajuste_manual", 0)

            observacao = ""
            if info['folga']:
                # Verifica se é férias para a exportação também
                if info.get("is_ferias"):
                    observacao = "FÉRIAS"
                else:
                    observacao = "FOLGA"
            elif eh_feriado:
                observacao = "FERIADO"
            elif dt_obj.weekday() >= 5:
                observacao = "FIM DE SEMANA"

            registros.append({
                "Data": datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y"),
                "Dia da Semana": dia_semana,
                "Batidas": batidas_str,
                "Horas Trabalhadas": self.formatar_duracao(trabalhado),
                "Saldo do Dia": self.formatar_duracao(saldo),
                "Ajuste Manual (min)": ajuste,
                "Observação": observacao
            })
        return pd.DataFrame(registros)

    # --- IMPORTAÇÃO PDF INTELIGENTE (HÍBRIDA) ---
    def calcular_hash_arquivo(self, caminho_pdf):
        try:
            with open(caminho_pdf, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return None

    def processar_pdf(self, caminho_arquivo, substituir=False):
        if not pdfplumber:
            return "error", "Biblioteca pdfplumber não instalada."

        novo_hash = self.calcular_hash_arquivo(caminho_arquivo)
        ultimo_hash = self.config.get("ultimo_hash_pdf")

        if (ultimo_hash == novo_hash) and (not substituir):
            return "duplicate", "Arquivo já importado."

        dados_temp = {}
        count_total = 0

        print("-" * 30)
        print(f"LENDO ARQUIVO: {caminho_arquivo}")

        try:
            with pdfplumber.open(caminho_arquivo) as pdf:
                for i, page in enumerate(pdf.pages):
                    print(f"--- Processando Página {i + 1} ---")

                    leu_tabela_na_pagina = False  # Flag para evitar ler texto se já leu tabela

                    # TENTA LER TABELAS
                    tabelas = page.extract_tables()

                    # Se achou tabelas, processa linha a linha
                    if tabelas:
                        for tabela in tabelas:
                            for linha in tabela:
                                # Verifica se a linha tem pelo menos 2 colunas (Data e Batidas)
                                if len(linha) >= 2:
                                    # Junta APENAS coluna 0 e 1 (Ignora Ajustes e Resultados)
                                    raw_data = str(linha[0] or "")
                                    raw_batidas = str(linha[1] or "")

                                    linha_limpa = f"{raw_data} {raw_batidas}".replace("\n", " ")

                                    if len(linha_limpa) > 5:
                                        self._extrair_e_adicionar(linha_limpa, dados_temp)
                                        leu_tabela_na_pagina = True

                    # TENTA LER TEXTO (FALLBACK)
                    # Só lê texto se NÃO conseguiu ler tabela nesta página
                    if not leu_tabela_na_pagina:
                        texto = page.extract_text()
                        if texto:
                            for linha_txt in texto.split('\n'):
                                # Filtra linhas perigosas (Resultados)
                                if "Banco de Horas" not in linha_txt and "Previstas" not in linha_txt:
                                    if len(linha_txt) > 5:
                                        self._extrair_e_adicionar(linha_txt, dados_temp)

            if not dados_temp:
                print("ERRO: Nenhuma data válida encontrada no dicionário final.")
                return "error", "Não foi possível identificar datas. Verifique o terminal para detalhes."

            # GRAVAÇÃO
            datas_processadas = []
            for data, lista_horas in dados_temp.items():
                lista_limpa = sorted(list(set(lista_horas)))

                if substituir:
                    # Atualiza/Substitui o dia
                    self.dados[data] = {"batidas": lista_limpa, "ajuste_manual": 0, "folga": False}
                    count_total += len(lista_limpa)
                else:
                    # Modo seguro: Adiciona se não existir
                    if data not in self.dados: self.dados[data] = {"batidas": [], "ajuste_manual": 0, "folga": False}
                    for h in lista_limpa:
                        if h not in self.dados[data]["batidas"]:
                            self.dados[data]["batidas"].append(h)
                            count_total += 1
                    self.dados[data]["batidas"].sort()

            self.config["ultimo_hash_pdf"] = novo_hash
            self.salvar_config(None, None, None, None)
            self.salvar_dados()

            ultima_data = sorted(datas_processadas)[-1] if datas_processadas else "N/A"
            print(f"SUCESSO: {count_total} batidas importadas. Última data: {ultima_data}")

            return "ok", f"Sucesso! {count_total} batidas. (Última: {ultima_data})"

        except Exception as ex:
            print(f"ERRO CRÍTICO: {ex}")
            return "error", f"Erro crítico: {ex}"

    def _extrair_e_adicionar(self, texto_linha, dic_dados):
        """
        Extrai data e horas de uma string suja.
        """
        try:
            # 1. ENCONTRAR DATA (Regex robusto)
            # Regex: (2 digitos) + (separador opcional) + (2 digitos) + (separador opcional) + (4 digitos)
            match_data = re.search(r"(\d{2})[\W_]*(\d{2})[\W_]*(\d{4})", texto_linha)

            if match_data:
                dia, mes, ano = match_data.groups()

                # Validação de segurança
                if int(mes) > 12 or int(mes) < 1 or int(dia) > 31:
                    return

                # Monta a data ISO
                data_iso = f"{ano}-{mes}-{dia}"

                # 2. ENCONTRAR HORAS
                # Procura padrao HH:MM
                horas = re.findall(r"(\d{2}:\d{2})", texto_linha)

                # Filtra horas inválidas (ex: 99:99 ou horas > 24)
                horas_reais = []
                for h in horas:
                    hh, mm = map(int, h.split(':'))
                    if hh <= 24 and mm < 60:
                        horas_reais.append(h)

                if horas_reais:
                    if data_iso not in dic_dados: dic_dados[data_iso] = []
                    dic_dados[data_iso].extend(horas_reais)
        except Exception as e:
            pass


# --- INTERFACE GRÁFICA ---

def main(page: ft.Page):
    app = ControlePontoApp()

    page.locale_configuration = ft.LocaleConfiguration(
        supported_locales=[ft.Locale("pt", "BR"), ft.Locale("en", "US")],
        current_locale=ft.Locale("pt", "BR")
    )
    page.locale = "pt-BR"
    page.title = "Controle de Ponto - Renan"

    tema_salvo = app.config.get("tema_inicial", "light")
    page.theme_mode = ft.ThemeMode.DARK if tema_salvo == "dark" else ft.ThemeMode.LIGHT

    page.window_width = 1200
    page.window_height = 900
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    # Variáveis de Estado
    data_manual_temp = None
    data_edicao_atual = None
    var_mes_export = None
    var_formato_export = "xlsx"

    # --- FUNÇÃO AUXILIAR: MÁSCARA AUTOMÁTICA PARA HORA ---
    def formatar_hora_input(e):
        """Formata automaticamente o input de hora para HH:MM enquanto digita."""
        valor_raw = e.control.value
        sinal = "-" if valor_raw.startswith("-") else ""
        digitos = "".join(filter(str.isdigit, valor_raw))
        if len(digitos) > 4: digitos = digitos[:4]
        novo_valor = f"{sinal}{digitos[:2]}:{digitos[2:]}" if len(digitos) > 2 else f"{sinal}{digitos}"
        if e.control.value != novo_valor:
            e.control.value = novo_valor
            e.control.update()

    # --- COMPONENTES AUXILIARES ---

    def mostrar_mensagem(texto, cor=ft.Colors.GREEN):
        snack = ft.SnackBar(ft.Text(texto), bgcolor=cor)
        page.overlay.append(snack)
        snack.open = True
        page.update()

    # --- FILE PICKERS (Backup/Restore/Export/Import) ---

    def importar_pdf_result(e):
        if not e.files: return

        # 1. Limpa a tela (fecha configs)
        dlg_config.open = False
        page.update()

        caminho = e.files[0].path
        print(f"\n--- INICIANDO IMPORTAÇÃO ---")
        print(f"Arquivo: {caminho}")

        # 2. Mostra barra de carregamento
        snack_loading = ft.SnackBar(
            content=ft.Text("Processando PDF... Aguarde...", color=ft.Colors.WHITE),
            bgcolor=ft.Colors.BLUE_800,
            duration=20000,  # Duração longa para não sumir antes da hora
        )
        page.overlay.append(snack_loading)
        snack_loading.open = True
        page.update()

        # 3. Processa (Pode demorar um pouco)
        import time
        # Pequena pausa para garantir que a UI atualizou a barra azul
        time.sleep(0.5)

        status, msg = app.processar_pdf(caminho, substituir=False)
        print(f"Status: {status} | Msg: {msg}")

        # 4. REMOVE a barra de carregamento IMEDIATAMENTE
        snack_loading.open = False
        page.update()

        # 5. Tratamento de Duplicado
        if status == "duplicate":
            def confirmar_subst(evt):
                dlg_duplicado.open = False
                page.update()

                # Força substituição
                st2, m2 = app.processar_pdf(caminho, substituir=True)

                app.dados = app.carregar_dados()
                atualizar_tabela()

                # Aviso final
                cor = ft.Colors.GREEN if st2 == "ok" else ft.Colors.RED
                page.overlay.append(ft.SnackBar(ft.Text(f"Resultado: {m2}"), bgcolor=cor, open=True))
                page.update()

            dlg_duplicado = ft.AlertDialog(
                title=ft.Text("Arquivo Duplicado"),
                content=ft.Text(
                    "Este arquivo já foi importado anteriormente.\nDeseja processar novamente e substituir os dados?"),
                actions=[
                    ft.TextButton("Cancelar",
                                  on_click=lambda _: setattr(dlg_duplicado, 'open', False) or page.update()),
                    ft.TextButton("Sim, Substituir", on_click=confirmar_subst),
                ]
            )
            page.dialog = dlg_duplicado
            dlg_duplicado.open = True
            page.update()

        else:
            # SUCESSO OU ERRO
            cor = ft.Colors.GREEN if status == "ok" else ft.Colors.RED

            if status == "ok":
                app.dados = app.carregar_dados()
                atualizar_tabela()

            # Popup de confirmação (mais visível que SnackBar)
            dlg_resultado = ft.AlertDialog(
                title=ft.Text("Resultado da Importação"),
                content=ft.Text(msg),
                actions=[ft.TextButton("OK", on_click=lambda _: setattr(dlg_resultado, 'open', False) or page.update())]
            )
            page.dialog = dlg_resultado
            dlg_resultado.open = True
            page.update()

    def salvar_backup_result(e):
        if e.path:
            try:
                shutil.copy(ARQUIVO_DADOS, e.path)
                mostrar_mensagem("Backup salvo com sucesso!", ft.Colors.GREEN)
            except Exception as ex:
                mostrar_mensagem(f"Erro ao salvar backup: {ex}", ft.Colors.RED)

    def restaurar_backup_result(e):
        if e.files:
            try:
                shutil.copy(e.files[0].path, ARQUIVO_DADOS)
                app.dados = app.carregar_dados()
                atualizar_tabela()
                mostrar_mensagem("Dados restaurados com sucesso!", ft.Colors.GREEN)
            except Exception as ex:
                mostrar_mensagem(f"Erro ao restaurar: {ex}", ft.Colors.RED)

    def exportar_result(e):
        if not e.path:
            return
        try:
            df = app.gerar_dataframe_exportacao(var_mes_export)

            if var_formato_export == "xlsx":
                df.to_excel(e.path, index=False)
            else:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=10)
                pdf.cell(200, 10, txt="Relatorio de Ponto", ln=1, align='C')
                pdf.ln(10)
                for col in df.columns:
                    w = 40 if col == "Batidas" else 25
                    pdf.cell(w, 10, str(col)[:12], border=1)
                pdf.ln()
                for i in range(len(df)):
                    for col in df.columns:
                        w = 40 if col == "Batidas" else 25
                        val = str(df.iloc[i][col])
                        pdf.cell(w, 10, val, border=1)
                    pdf.ln()
                pdf.output(e.path)

            mostrar_mensagem(f"Arquivo salvo em: {e.path}", ft.Colors.GREEN)
            dlg_exportar.open = False
            page.update()
        except Exception as ex:
            mostrar_mensagem(f"Erro na exportação: {ex}", ft.Colors.RED)

    # --- DEFINIÇÃO DOS FILE PICKERS ---
    fp_importar_pdf = ft.FilePicker(on_result=importar_pdf_result)  # CORREÇÃO AQUI
    fp_backup = ft.FilePicker(on_result=salvar_backup_result)
    fp_restore = ft.FilePicker(on_result=restaurar_backup_result)
    fp_export = ft.FilePicker(on_result=exportar_result)

    page.overlay.extend([fp_backup, fp_restore, fp_export, fp_importar_pdf])

    # --- DIALOGO CONFIGURAÇÕES (AVANÇADO) ---

    tf_meta = ft.TextField(label="Meta Diária (h)", value=str(app.config.get("meta_diaria", 8)), width=100)
    tf_fator_util = ft.TextField(label="Fator Extra Dia Útil (Ex: 1.0 ou 1.5)",
                                 value=str(app.config.get("fator_dia_util", 1.0)), width=250)
    tf_fator_fds = ft.TextField(label="Fator Extra FDS (Ex: 2.0)", value=str(app.config.get("fator_fds", 2.0)),
                                width=250)
    dd_tema = ft.Dropdown(
        label="Tema Padrão",
        width=150,
        options=[ft.dropdown.Option("light", "Claro"), ft.dropdown.Option("dark", "Escuro")],
        value=app.config.get("tema_inicial", "light")
    )

    def salvar_configuracoes(e):
        try:
            meta = int(tf_meta.value)
            f_util = float(tf_fator_util.value)
            f_fds = float(tf_fator_fds.value)
            tema = dd_tema.value

            app.salvar_config(meta, f_util, f_fds, tema)

            # Aplica o tema imediatamente
            page.theme_mode = ft.ThemeMode.DARK if tema == "dark" else ft.ThemeMode.LIGHT
            footer.bgcolor = ft.Colors.GREY_900 if tema == "dark" else ft.Colors.BLUE_GREY_50

            mostrar_mensagem("Configurações salvas! Tabela recalculada.")
            atualizar_tabela()
            dlg_config.open = False
            page.update()
        except:
            mostrar_mensagem("Erro: Verifique os números digitados.", ft.Colors.RED)

    dlg_config = ft.AlertDialog(
        title=ft.Text("Configurações Gerais"),
        content=ft.Container(
            content=ft.Column([
                ft.Text("Regras de Banco de Horas", weight="bold", size=16),
                ft.Row([tf_meta, dd_tema]),
                ft.Text("Multiplicadores:", weight="bold"),
                tf_fator_util,
                tf_fator_fds,
                ft.Divider(),
                ft.Text("Dados & Backup", weight="bold", size=16),
                ft.Row([
                    ft.ElevatedButton("Fazer Backup", icon=ft.Icons.SAVE, on_click=lambda _: fp_backup.save_file(
                        file_name=f"backup_ponto_{datetime.now().strftime('%Y%m%d')}.json")),
                    ft.ElevatedButton("Restaurar", icon=ft.Icons.RESTORE_PAGE,
                                      on_click=lambda _: fp_restore.pick_files(allowed_extensions=["json"])),
                ]),
                # BOTÃO IMPORTAR PDF
                ft.ElevatedButton("Importar PDF", icon=ft.Icons.PICTURE_AS_PDF, bgcolor=ft.Colors.RED_100,
                                  color=ft.Colors.RED,
                                  on_click=lambda _: fp_importar_pdf.pick_files(allowed_extensions=["pdf"])),
            ], spacing=15, scroll=ft.ScrollMode.AUTO),
            height=500, width=500
        ),
        actions=[ft.TextButton("Salvar Alterações", on_click=salvar_configuracoes)]
    )

    # --- DIALOGO EXPORTAR ---

    def acao_escolher_tipo_export(e, tipo):
        nonlocal var_mes_export
        if tipo == "relatorio":
            var_mes_export = datetime.now().strftime("%Y-%m")
            tab_export.selected_index = 2
        else:
            tab_export.selected_index = 1
        page.update()

    def acao_escolher_mes_export(e):
        nonlocal var_mes_export
        var_mes_export = dd_mes_export.value
        tab_export.selected_index = 2
        page.update()

    def acao_escolher_formato_export(e, fmt):
        nonlocal var_formato_export
        var_formato_export = fmt
        ext = "xlsx" if fmt == "xlsx" else "pdf"
        nome_arq = f"Relatorio_Ponto_{datetime.now().strftime('%Y%m%d')}.{ext}"
        fp_export.save_file(file_name=nome_arq, allowed_extensions=[ext])

    dd_mes_export = ft.Dropdown(
        label="Selecione o Período",
        options=[ft.dropdown.Option(key=None, text="Todo o Histórico")] +
                [ft.dropdown.Option(key=f"2025-{m:02d}", text=f"{m:02d}/2025") for m in range(1, 13)]
    )

    tab_export = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text="1. Tipo",
                content=ft.Column([
                    ft.Text("O que deseja exportar?", size=16, weight="bold"),
                    ft.ElevatedButton("Relatório Mensal (Mês Atual)",
                                      on_click=lambda e: acao_escolher_tipo_export(e, "relatorio"), width=300),
                    ft.ElevatedButton("Planilha Completa (Selecionar)",
                                      on_click=lambda e: acao_escolher_tipo_export(e, "planilha"), width=300),
                ], spacing=20, alignment=ft.MainAxisAlignment.CENTER)
            ),
            ft.Tab(
                text="2. Período",
                content=ft.Column([
                    ft.Text("Qual período deseja?", size=16, weight="bold"),
                    dd_mes_export,
                    ft.ElevatedButton("Próximo >", on_click=acao_escolher_mes_export)
                ], spacing=20, alignment=ft.MainAxisAlignment.CENTER)
            ),
            ft.Tab(
                text="3. Formato",
                content=ft.Column([
                    ft.Text("Qual formato de arquivo?", size=16, weight="bold"),
                    ft.Row([
                        ft.ElevatedButton("Excel (.xlsx)", icon=ft.Icons.TABLE_VIEW,
                                          on_click=lambda e: acao_escolher_formato_export(e, "xlsx")),
                        ft.ElevatedButton("PDF (.pdf)", icon=ft.Icons.PICTURE_AS_PDF,
                                          on_click=lambda e: acao_escolher_formato_export(e, "pdf")),
                    ], alignment=ft.MainAxisAlignment.CENTER)
                ], spacing=20, alignment=ft.MainAxisAlignment.CENTER)
            )
        ]
    )

    dlg_exportar = ft.AlertDialog(
        title=ft.Text("Exportar Dados"),
        content=ft.Container(content=tab_export, width=400, height=300)
    )

    # --- DIALOGO DE EDIÇÃO GRANULAR ---

    lv_batidas = ft.ListView(expand=True, spacing=10, height=150)

    # Input Nova Batida com MÁSCARA e ENTER
    input_nova_batida = ft.TextField(
        hint_text="00:00", width=100, text_align=ft.TextAlign.CENTER,
        on_change=formatar_hora_input,  # Máscara
        on_submit=lambda e: adicionar_batida_individual(e)  # Enter
    )

    def salvar_alteracao_batida(e, data, hora_antiga, novo_valor):
        try:
            datetime.strptime(novo_valor, "%H:%M")
            app.atualizar_batida(data, hora_antiga, novo_valor)
            mostrar_mensagem("Horário atualizado com sucesso!")
            carregar_lista_edicao(data)
            atualizar_tabela()
        except ValueError:
            mostrar_mensagem("Formato inválido! Use HH:MM", ft.Colors.RED)

    def carregar_lista_edicao(data):
        lv_batidas.controls.clear()
        batidas = app.dados.get(data, {}).get("batidas", [])

        if not batidas:
            lv_batidas.controls.append(ft.Text("Nenhuma batida registrada.", color=ft.Colors.GREY))

        cor_item = ft.Colors.GREY_200 if page.theme_mode == ft.ThemeMode.LIGHT else ft.Colors.GREY_800

        for b in batidas:
            # Campo existente com MÁSCARA e ENTER
            txt_hora = ft.TextField(
                value=b,
                width=80,
                height=40,
                content_padding=5,
                text_align=ft.TextAlign.CENTER,
                text_size=14,
                on_change=formatar_hora_input,  # Máscara
                on_submit=lambda e, h=b: salvar_alteracao_batida(e, data, h, e.control.value)  # Enter
            )

            btn_salvar = ft.IconButton(
                icon=ft.Icons.CHECK_CIRCLE,
                icon_color=ft.Colors.GREEN,
                tooltip="Salvar Alteração",
                on_click=lambda e, h=b, t=txt_hora: salvar_alteracao_batida(e, data, h, t.value)
            )

            btn_excluir = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED,
                tooltip="Apagar esta batida",
                on_click=lambda e, h=b, d=data: remover_batida_individual(d, h)
            )

            row = ft.Row([
                ft.Icon(ft.Icons.ACCESS_TIME, size=16),
                txt_hora,
                btn_salvar,
                btn_excluir
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

            lv_batidas.controls.append(ft.Container(content=row, bgcolor=cor_item, padding=5, border_radius=5))

        page.update()

    def remover_batida_individual(data, hora):
        app.remover_batida(data, hora)
        carregar_lista_edicao(data)
        atualizar_tabela()
        mostrar_mensagem(f"Batida {hora} removida.")

    def adicionar_batida_individual(e):
        hora = input_nova_batida.value
        try:
            datetime.strptime(hora, "%H:%M")
            app.registrar_batida(data_edicao_atual, hora)
            input_nova_batida.value = ""
            carregar_lista_edicao(data_edicao_atual)
            atualizar_tabela()
        except:
            mostrar_mensagem("Formato inválido. Use HH:MM", ft.Colors.RED)

    def abrir_edicao(e):
        nonlocal data_edicao_atual
        data_edicao_atual = e.control.data
        carregar_lista_edicao(data_edicao_atual)
        page.dialog = dlg_editar
        dlg_editar.open = True
        page.update()

    dlg_editar = ft.AlertDialog(
        title=ft.Text("Gerenciar Batidas"),
        content=ft.Container(
            content=ft.Column([
                ft.Text("Edite ou remova batidas específicas:"),
                ft.Divider(),
                lv_batidas,
                ft.Divider(),
                ft.Row([
                    ft.Text("Adicionar Nova:"),
                    input_nova_batida,
                    ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=ft.Colors.BLUE, on_click=adicionar_batida_individual)
                ], alignment=ft.MainAxisAlignment.CENTER)
            ]),
            width=400, height=400
        ),
        actions=[
            ft.TextButton("Concluir", on_click=lambda e: setattr(dlg_editar, 'open', False) or page.update()),
        ],
    )

    # --- DIALOGO AJUSTE MANUAL ---

    dlg_ajuste_input = ft.TextField(
        label="Valor (ex: 60 ou 01:00)", hint_text="Minutos ou HH:MM",
        on_change=formatar_hora_input,
        on_submit=lambda e: salvar_ajuste_click(e)
    )
    dlg_ajuste_data_ref = ft.Text(visible=False)

    def salvar_ajuste_click(e):
        val_minutos = app.converter_input_tempo_para_minutos(dlg_ajuste_input.value)
        app.ajustar_manual(dlg_ajuste_data_ref.value, val_minutos)
        dlg_ajuste.open = False
        atualizar_tabela()
        mostrar_mensagem("Ajuste salvo!")

    def abrir_ajuste(e):
        data = e.control.data
        dlg_ajuste_data_ref.value = data
        ajuste_atual = app.dados[data].get("ajuste_manual", 0)
        dlg_ajuste_input.value = app.formatar_duracao(ajuste_atual * 60)
        page.dialog = dlg_ajuste
        dlg_ajuste.open = True
        page.update()

    dlg_ajuste = ft.AlertDialog(
        title=ft.Text("Ajuste Manual de Banco"),
        content=ft.Column([
            ft.Text("Adicione tempo (ex: 01:30) ou subtraia (ex: -00:15)"),
            dlg_ajuste_data_ref,
            dlg_ajuste_input
        ], height=120),
        actions=[ft.TextButton("Confirmar", on_click=salvar_ajuste_click)]
    )

    # --- DIALOGO FÉRIAS EM LOTE ---
    txt_ini_ferias = ft.TextField(label="Início", width=120, read_only=True)
    txt_fim_ferias = ft.TextField(label="Fim", width=120, read_only=True)

    def confirmar_ferias_click(e):
        if txt_ini_ferias.value and txt_fim_ferias.value:
            app.registrar_ferias_lote(txt_ini_ferias.value, txt_fim_ferias.value)
            dlg_ferias.open = False
            atualizar_tabela()
            mostrar_mensagem("Férias registradas com sucesso!")
        else:
            mostrar_mensagem("Selecione início e fim.", ft.Colors.RED)

    def abrir_dp_ini(e):
        page.open(dp_ini_ferias)

    def abrir_dp_fim(e):
        page.open(dp_fim_ferias)

    dp_ini_ferias = ft.DatePicker(
        on_change=lambda e: setattr(txt_ini_ferias, 'value', e.control.value.strftime("%Y-%m-%d")) or page.update()
    )
    dp_fim_ferias = ft.DatePicker(
        on_change=lambda e: setattr(txt_fim_ferias, 'value', e.control.value.strftime("%Y-%m-%d")) or page.update()
    )

    dlg_ferias = ft.AlertDialog(
        title=ft.Text("Registrar Férias"),
        content=ft.Column([
            ft.Text("Selecione o período para marcar como folga:"),
            ft.Row([
                txt_ini_ferias,
                ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=abrir_dp_ini)
            ]),
            ft.Row([
                txt_fim_ferias,
                ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=abrir_dp_fim)
            ])
        ], height=200),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda e: setattr(dlg_ferias, 'open', False) or page.update()),
            ft.TextButton("Confirmar", on_click=confirmar_ferias_click),
        ]
    )

    # --- DIALOGOS DE EXCLUSÃO E LIMPEZA ---

    dlg_excluir_data_ref = ft.Text(visible=False)

    def confirmar_exclusao_click(e):
        app.excluir_dia(dlg_excluir_data_ref.value)
        dlg_confirmar_exclusao.open = False
        atualizar_tabela()
        mostrar_mensagem("Dia excluído.")

    def abrir_exclusao(e):
        dlg_excluir_data_ref.value = e.control.data
        page.dialog = dlg_confirmar_exclusao
        dlg_confirmar_exclusao.open = True
        page.update()

    dlg_confirmar_exclusao = ft.AlertDialog(
        title=ft.Text("Excluir Dia Inteiro?"),
        content=ft.Column([ft.Text("Isso apagará todos os registros desta data."), dlg_excluir_data_ref], height=50),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: setattr(dlg_confirmar_exclusao, 'open', False) or page.update()),
            ft.TextButton("Sim, Excluir", on_click=confirmar_exclusao_click, style=ft.ButtonStyle(color=ft.Colors.RED)),
        ]
    )

    def limpar_tudo_final(e):
        app.limpar_tudo()
        dlg_certeza_absoluta.open = False
        atualizar_tabela()
        mostrar_mensagem("Banco Reiniciado! (Histórico preservado)", ft.Colors.GREEN)

    dlg_certeza_absoluta = ft.AlertDialog(
        title=ft.Text("ZERAR BANCO?"),
        content=ft.Text("Isso zerará o saldo total, começando a contagem de agora.\nO histórico antigo será mantido."),
        actions=[
            ft.TextButton("CANCELAR", on_click=lambda e: setattr(dlg_certeza_absoluta, 'open', False) or page.update()),
            ft.TextButton("ZERAR", on_click=limpar_tudo_final,
                          style=ft.ButtonStyle(color=ft.Colors.RED, bgcolor=ft.Colors.RED_50)),
        ]
    )

    dlg_confirmar_limpeza = ft.AlertDialog(
        title=ft.Text("Zerar Banco de Horas?"),
        content=ft.Text("Deseja zerar o banco atual e começar um novo ciclo?"),
        actions=[
            ft.TextButton("Não", on_click=lambda e: setattr(dlg_confirmar_limpeza, 'open', False) or page.update()),
            ft.TextButton("Sim", on_click=lambda e: (
                    setattr(dlg_confirmar_limpeza, 'open', False) or setattr(dlg_certeza_absoluta, 'open',
                                                                             True) or page.update()),
                          style=ft.ButtonStyle(color=ft.Colors.RED)),
        ]
    )

    # --- SISTEMA DE INSERÇÃO MANUAL ---

    def abrir_calendario_manual(e):
        page.open(date_picker)

    def ao_escolher_data_manual(e):
        nonlocal data_manual_temp
        if date_picker.value:
            data_manual_temp = date_picker.value
            page.open(time_picker)

    def ao_escolher_hora_manual(e):
        if time_picker.value and data_manual_temp:
            data_str = data_manual_temp.strftime("%Y-%m-%d")
            hora_str = time_picker.value.strftime("%H:%M")
            if app.registrar_batida(data_str, hora_str):
                mostrar_mensagem(f"Inserido: {data_str} às {hora_str}")
                atualizar_tabela()
            else:
                mostrar_mensagem("Horário já existe para este dia.", ft.Colors.ORANGE)

    date_picker = ft.DatePicker(
        on_change=ao_escolher_data_manual,
        confirm_text="Confirmar", cancel_text="Cancelar",
        help_text="Selecione a data",
    )
    time_picker = ft.TimePicker(
        on_change=ao_escolher_hora_manual,
        confirm_text="Confirmar", cancel_text="Cancelar",
        help_text="Selecione o horário"
    )

    # --- ADICIONAR COMPONENTES AO OVERLAY ---
    page.overlay.extend([
        dlg_editar, dlg_ajuste, dlg_ferias,
        dlg_confirmar_exclusao, dlg_confirmar_limpeza, dlg_certeza_absoluta,
        dlg_exportar, dlg_config,
        date_picker, time_picker, dp_ini_ferias, dp_fim_ferias,
        fp_backup, fp_restore, fp_export, fp_importar_pdf
    ])

    # --- FUNÇÕES DA UI (BOTÕES) ---

    def toggle_folga(e):
        # Se clicou no Checkbox, é FOLGA MANUAL (is_ferias=False)
        app.definir_folga(e.control.data, e.control.value, eh_ferias=False)
        atualizar_tabela()

    def bater_ponto_click(e):
        msg = app.bater_ponto_agora()
        mostrar_mensagem(msg)
        atualizar_tabela()

    def alternar_tema(e):
        is_light = page.theme_mode == ft.ThemeMode.LIGHT
        page.theme_mode = ft.ThemeMode.DARK if is_light else ft.ThemeMode.LIGHT
        e.control.icon = ft.Icons.LIGHT_MODE if is_light else ft.Icons.DARK_MODE

        # Atualiza cor do rodapé
        footer.bgcolor = ft.Colors.GREY_900 if is_light else ft.Colors.BLUE_GREY_50

        page.update()
        atualizar_tabela()

    # --- GRÁFICO VISUAL ---

    chart = ft.LineChart(
        data_series=[],
        border=ft.border.all(1, ft.Colors.GREY_400),
        left_axis=ft.ChartAxis(labels_size=40, title=ft.Text("Horas Saldo")),
        bottom_axis=ft.ChartAxis(
            labels_size=30,
            title=ft.Text("Dia do Mês"),
            labels_interval=1
        ),
        horizontal_grid_lines=ft.ChartGridLines(color=ft.Colors.GREY_200, width=1, dash_pattern=[3, 3]),
        vertical_grid_lines=ft.ChartGridLines(color=ft.Colors.GREY_200, width=1),
        tooltip_bgcolor=ft.Colors.with_opacity(0.9, ft.Colors.BLACK),
        min_y=-10, max_y=10,
        expand=True, height=250
    )

    # --- ALTERAÇÃO NO GRÁFICO (ROLAGEM HORIZONTAL) ---
    container_grafico = ft.Container(
        content=ft.Column([
            ft.Text("Evolução do Banco no Mês:", weight="bold", size=16),
            # Envolvemos o gráfico em uma Row com Scroll
            ft.Row(
                controls=[
                    ft.Container(
                        content=chart,
                        width=1000,  # LARGURA FIXA: O gráfico sempre terá 1000px
                        height=250  # Isso garante que ele fique "bonito" e rolável no celular
                    )
                ],
                scroll=ft.ScrollMode.ALWAYS  # Habilita o scroll horizontal
            )
        ]),
        padding=20,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE),
        border_radius=10,
        visible=False,
        margin=ft.margin.only(top=20, bottom=50)
    )


    # 1. CRIAÇÃO DA TABELA (Sem largura fixa para aceitar responsividade)
    tabela = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Data", weight="bold")),
            ft.DataColumn(ft.Text("Dia")),
            ft.DataColumn(ft.Text("Batidas")),
            ft.DataColumn(ft.Text("Horas")),
            ft.DataColumn(ft.Text("Saldo (Puro)")),
            ft.DataColumn(ft.Text("Ajuste (Manual)")),
            ft.DataColumn(ft.Text("Ações")),
        ],
        heading_row_color=ft.Colors.BLUE_GREY_500,
        data_row_min_height=55,
        column_spacing=20,
    )

    # 2. LABELS DO RESUMO
    lbl_trab_mes = ft.Text("00:00")
    lbl_prev_mes = ft.Text("00:00")
    lbl_banco_mes = ft.Text("00:00", weight="bold")
    lbl_banco_ant = ft.Text("00:00")
    lbl_banco_total = ft.Text("00:00", weight="bold", size=16)

    linha_resumo_1 = ft.Row([
        ft.Column([ft.Text("Trabalhado"), lbl_trab_mes]),
        ft.Column([ft.Text("Previsto"), lbl_prev_mes]),
        ft.Column([ft.Text("Banco Mês"), lbl_banco_mes]),
        ft.Column([ft.Text("Banco Ant."), lbl_banco_ant]),
        ft.Column([ft.Text("TOTAL GERAL"), lbl_banco_total]),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # 3. CRIAÇÃO DOS BOTÕES E INPUTS (Importante criar antes de usar)
    # Precisamos criar o filtro aqui para a função 'atualizar_tabela' conseguir ler ele
    txt_filtro = ft.TextField(
        label="Filtro",
        value=datetime.now().strftime("%Y-%m"),
        width=100,
        on_submit=lambda e: atualizar_tabela()  # Agora vai funcionar pois a função vem logo abaixo
    )

    btn_bater = ft.ElevatedButton(
        "BATER PONTO",
        icon=ft.Icons.TOUCH_APP,
        on_click=bater_ponto_click,
        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE, padding=20,
                             shape=ft.RoundedRectangleBorder(radius=10))
    )

    btn_manual = ft.ElevatedButton(
        "Inserir Manual",
        icon=ft.Icons.CALENDAR_MONTH,
        on_click=abrir_calendario_manual
    )

    btn_ferias = ft.ElevatedButton(
        "FÉRIAS",
        icon=ft.Icons.BEACH_ACCESS,
        color=ft.Colors.ORANGE,
        on_click=lambda e: (setattr(dlg_ferias, 'open', True), page.update())
    )

    btn_exportar = ft.IconButton(icon=ft.Icons.PIE_CHART, tooltip="Exportar Relatório",
                                 on_click=lambda e: (setattr(dlg_exportar, 'open', True), page.update()))
    btn_config = ft.IconButton(icon=ft.Icons.SETTINGS, tooltip="Configurações/Backup",
                               on_click=lambda e: (setattr(dlg_config, 'open', True), page.update()))

    # 4. A FUNÇÃO QUE TINHA SUMIDO (Restaurada)
    def atualizar_tabela():
        tabela.rows.clear()
        datas_ordenadas = sorted(app.dados.keys())

        filtro_input = txt_filtro.value.strip()
        filtro_ano_mes = ""
        try:
            if "-" not in filtro_input:
                filtro_ano_mes = datetime.now().strftime("%Y-%m")
            else:
                filtro_ano_mes = filtro_input
        except:
            filtro_ano_mes = datetime.now().strftime("%Y-%m")

        soma_trab_mes = 0
        soma_banco_mes = 0
        soma_banco_anterior = 0

        hoje_str = app.obter_hoje_str()
        is_dark = page.theme_mode == ft.ThemeMode.DARK
        data_corte = app.config.get("data_inicio_contagem")

        pontos_grafico = []
        saldo_acumulado_grafico = 0

        for i, data in enumerate(datas_ordenadas):
            info = app.dados[data]
            trabalhado, meta, saldo_final, eh_feriado = app.obter_saldo_dia(data, info)

            ajuste_min = info.get("ajuste_manual", 0)
            saldo_puro_segundos = saldo_final - (ajuste_min * 60)

            eh_mes_corrente = data.startswith(filtro_ano_mes)

            if not data_corte or data >= data_corte:
                if eh_mes_corrente:
                    soma_trab_mes += trabalhado
                    soma_banco_mes += saldo_final
                    saldo_acumulado_grafico += saldo_final
                    dia_mes = int(data.split("-")[2])
                    pontos_grafico.append(ft.LineChartDataPoint(
                        x=dia_mes,
                        y=saldo_acumulado_grafico / 3600,
                        tooltip=f"Dia {dia_mes}: {app.formatar_duracao(saldo_acumulado_grafico)}",
                        show_tooltip=True, point=True
                    ))
                elif data < (filtro_ano_mes + "-01"):
                    soma_banco_anterior += saldo_final

            if not eh_mes_corrente:
                continue

            # Montagem visual da linha
            batidas_str = " | ".join(info['batidas'])
            coluna_batidas_content = [ft.Text(batidas_str)]

            # Badge de Saída
            if len(info['batidas']) % 2 != 0:
                batidas_str += " ..."
                parcial = app.calcular_segundos_trabalhados(info['batidas'] + [datetime.now().strftime("%H:%M")])
                meta_atual = app.config.get("meta_diaria", 8)
                falta = (meta_atual * 3600) - parcial
                if falta > 0:
                    saida_dt = datetime.now() + timedelta(seconds=falta)
                    badge_saida = ft.Container(
                        content=ft.Text(f"Saída: {saida_dt.strftime('%H:%M')}", size=12, color=ft.Colors.WHITE,
                                        weight="bold"),
                        bgcolor=ft.Colors.BLUE_700, padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4, margin=ft.margin.only(top=4)
                    )
                    coluna_batidas_content.append(badge_saida)

            cor_base = ft.Colors.GREY_900 if is_dark and i % 2 == 0 else ft.Colors.GREY_800 if is_dark else ft.Colors.WHITE if i % 2 == 0 else ft.Colors.GREY_200
            if data == hoje_str:
                cor_base = ft.Colors.BLUE_900 if is_dark else ft.Colors.BLUE_50

            str_saldo = app.formatar_duracao(saldo_puro_segundos)
            cor_saldo = ft.Colors.GREEN if saldo_puro_segundos >= 0 else ft.Colors.RED

            txt_ajuste = ""
            color_ajuste = ft.Colors.GREY
            if ajuste_min != 0:
                val_fmt = app.formatar_duracao(ajuste_min * 60)
                txt_ajuste = f"+{val_fmt}" if ajuste_min > 0 else f"{val_fmt}"
                color_ajuste = ft.Colors.GREEN if ajuste_min > 0 else ft.Colors.RED

            dt_obj = datetime.strptime(data, "%Y-%m-%d")
            dias_sem = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
            dia_txt = dias_sem[dt_obj.weekday()]

            txt_saldo_ui = ft.Text(str_saldo, color=cor_saldo, weight="bold")
            if info['folga']:
                if info.get("is_ferias"):
                    txt_saldo_ui = ft.Text("FÉRIAS", color=ft.Colors.BLUE, weight="bold")
                else:
                    txt_saldo_ui = ft.Text("FOLGA", color=ft.Colors.ORANGE, weight="bold")
            elif eh_feriado:
                cor_feriado = ft.Colors.PURPLE_200 if is_dark else ft.Colors.PURPLE
                txt_saldo_ui = ft.Text(f"{str_saldo} (FERIADO)", color=cor_feriado, weight="bold")
                dia_txt += " (F)"
            elif dt_obj.weekday() >= 5:
                fator_fds_show = app.config.get('fator_fds', 2.0)
                txt_saldo_ui = ft.Text(f"{str_saldo} (x{fator_fds_show})", color=ft.Colors.GREEN, weight="bold")

            tabela.rows.append(
                ft.DataRow(
                    color={ft.ControlState.DEFAULT: cor_base},
                    cells=[
                        ft.DataCell(ft.Text(dt_obj.strftime("%d/%m"))),
                        ft.DataCell(ft.Text(dia_txt, color=ft.Colors.ORANGE if (
                                    dt_obj.weekday() >= 5 or eh_feriado) else ft.Colors.ON_SURFACE)),
                        ft.DataCell(ft.Column(coluna_batidas_content, spacing=0)),
                        ft.DataCell(ft.Text(app.formatar_duracao(trabalhado))),
                        ft.DataCell(txt_saldo_ui),
                        ft.DataCell(ft.Row([
                            ft.Text(txt_ajuste, color=color_ajuste, size=12, weight="bold"),
                            ft.IconButton(icon=ft.Icons.TUNE, tooltip="Ajuste Manual", on_click=abrir_ajuste, data=data,
                                          icon_size=20),
                        ], spacing=5)),
                        ft.DataCell(ft.Row([
                            ft.Checkbox(value=info['folga'], label="Folga",
                                        on_change=lambda e, d=data: toggle_folga(e)),
                            ft.IconButton(ft.Icons.EDIT_NOTE, on_click=abrir_edicao, data=data,
                                          icon_color=ft.Colors.BLUE),
                            ft.IconButton(ft.Icons.DELETE, icon_color="red", on_click=lambda e, d=data: (
                            setattr(dlg_excluir_data_ref, 'value', d), setattr(dlg_confirmar_exclusao, 'open', True),
                            page.update()))
                        ]))
                    ]
                )
            )

        lbl_trab_mes.value = app.formatar_duracao(soma_trab_mes)
        try:
            partes_data = filtro_ano_mes.split("-")
            dias_uteis = app.calcular_dias_uteis_mes(int(partes_data[0]), int(partes_data[1]))
            previsto_seg = dias_uteis * app.config.get("meta_diaria", 8) * 3600
            lbl_prev_mes.value = app.formatar_duracao(previsto_seg)
        except:
            lbl_prev_mes.value = "--:--"

        lbl_banco_mes.value = app.formatar_duracao(soma_banco_mes)
        lbl_banco_mes.color = ft.Colors.GREEN if soma_banco_mes >= 0 else ft.Colors.RED
        lbl_banco_ant.value = app.formatar_duracao(soma_banco_anterior)
        lbl_banco_ant.color = ft.Colors.GREEN if soma_banco_anterior >= 0 else ft.Colors.RED

        total_geral = soma_banco_mes + soma_banco_anterior
        lbl_banco_total.value = app.formatar_duracao(total_geral)
        lbl_banco_total.color = ft.Colors.GREEN if total_geral >= 0 else ft.Colors.RED

        # Atualiza Gráfico
        if pontos_grafico:
            container_grafico.visible = True
            cor_linha = (ft.Colors.GREEN_400 if saldo_acumulado_grafico >= 0 else ft.Colors.RED_400) if is_dark else (
                ft.Colors.GREEN if saldo_acumulado_grafico >= 0 else ft.Colors.RED)
            chart.data_series = [
                ft.LineChartData(data_points=pontos_grafico, stroke_width=4, color=cor_linha, curved=True,
                                 stroke_cap_round=True, below_line_bgcolor=ft.Colors.with_opacity(0.1, cor_linha),
                                 point=True)]
            vals = [p.y for p in pontos_grafico]
            chart.min_y = min(vals) - 2 if vals else -10
            chart.max_y = max(vals) + 2 if vals else 10
            chart.bottom_axis.labels = [ft.ChartAxisLabel(value=p.x, label=ft.Container(
                ft.Text(str(int(p.x)), size=10, weight=ft.FontWeight.BOLD), padding=ft.padding.only(top=5))) for p in
                                        pontos_grafico]
        else:
            container_grafico.visible = False

        page.update()

    # 5. HEADER, FOOTER E LÓGICA DE RESPONSIVIDADE

    header_content = ft.Row([
        ft.Column([
            ft.Text("CONTROLE DE PONTO", size=24, weight="bold"),
            ft.Text("RENAN", size=16, color=ft.Colors.ORANGE, weight="bold")
        ], spacing=0),
        ft.Container(width=20),
        txt_filtro,
        ft.IconButton(ft.Icons.SEARCH, on_click=lambda e: atualizar_tabela()),
        btn_exportar, btn_config,
        ft.IconButton(ft.Icons.DARK_MODE, on_click=alternar_tema, tooltip="Tema"),
        btn_manual, btn_ferias, btn_bater
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    header_container = ft.Row(controls=[header_content], scroll=ft.ScrollMode.AUTO)

    footer = ft.Container(
        content=ft.Column([
            ft.Divider(),
            # A Row agora tem scroll AUTO para permitir deslizar o resumo no celular
            ft.Row([linha_resumo_1], scroll=ft.ScrollMode.AUTO),
            ft.Divider(height=10, color="transparent"),
            ft.Row([ft.TextButton("Zerar Banco (Mantém Histórico)", icon=ft.Icons.RESTART_ALT, icon_color="orange",
                                  on_click=lambda e: (setattr(dlg_confirmar_limpeza, 'open', True), page.update()))]),
            ft.Row([ft.Text("© 2025 Controle de Ponto - Desenvolvido por YannaMedova", size=12, color=ft.Colors.GREY)],
                   alignment=ft.MainAxisAlignment.CENTER)
        ]),
        # ALTERAÇÃO AQUI: Usamos symmetric para zerar a horizontal
        padding=ft.padding.symmetric(vertical=20, horizontal=0),
        bgcolor=ft.Colors.BLUE_GREY_50 if page.theme_mode == ft.ThemeMode.LIGHT else ft.Colors.GREY_900,
        border_radius=10
    )

    # --- 5. LÓGICA DE REDIMENSIONAMENTO

    def ajustar_layout(e):
        # Calcula a largura disponível na tela
        largura_tela = page.width if page.width else (page.window_width if page.window_width else 1000)

        # Define um padding de segurança da página (ex: 20px de cada lado)
        padding_pagina = 40

        # Largura real disponível
        largura_disponivel = largura_tela - padding_pagina

        # Lógica de Responsividade:
        # Se a tela for pequena (celular), travamos em 950px para forçar a rolagem horizontal.
        # Se for monitor grande, usa a largura total da tela.
        largura_minima_tabela = 950

        if largura_disponivel < largura_minima_tabela:
            w_final = largura_minima_tabela
        else:
            w_final = largura_disponivel

        # APLICA A MESMA LARGURA PARA TODOS OS ELEMENTOS
        # Isso garante que o início e o fim deles fiquem perfeitamente alinhados visualmente

        # 1. Tabela
        tabela.width = w_final

        # 2. Resumo (Rodapé)
        linha_resumo_1.width = w_final

        # 3. Cabeçalho
        try:
            header_content.width = w_final
        except NameError:
            pass

        # 4. Gráfico (opcional, mas bom manter alinhado)
        try:
            # O container do gráfico dentro do scroll deve seguir a mesma largura
            chart.parent.width = w_final
        except:
            pass

        page.update()

    # Vincula o evento de redimensionamento
    page.on_resized = ajustar_layout

    # --- 6. MONTAGEM FINAL DA PÁGINA ---

    # Define a altura da tabela dinamicamente (Tela inteira - Cabeçalho/Rodapé)
    # Isso evita ter duas barras de rolagem verticais
    altura_tabela = 500  # Valor padrão seguro

    page.add(
        header_container,
        ft.Divider(),

        # Container da Tabela
        ft.Column(
            controls=[
                ft.Row(
                    controls=[tabela],
                    scroll=ft.ScrollMode.ALWAYS,  # Habilita rolagem HORIZONTAL (Crucial para celular)
                )
            ],
            scroll=ft.ScrollMode.AUTO,  # Habilita rolagem VERTICAL
            height=altura_tabela,  # Define altura fixa para a rolagem vertical funcionar
            expand=True  # Tenta ocupar espaço vertical disponível
        ),

        footer,
        container_grafico
    )

    # INICIALIZAÇÃO
    atualizar_tabela()
    # Força o layout a se ajustar imediatamente
    page.update()
    ajustar_layout(None)

# =============================
# 🔐 LOGIN PROTECT
# =============================

# >>> SENHA: carregar via variável de ambiente (segurança)
import os

_ENV_KEY_SENHA = "PONTO_PASSWORD"

# Tenta ler a senha do ambiente
SENHA_CORRETA = os.getenv(_ENV_KEY_SENHA)
print(">>> DEBUG: SENHA_CORRETA lida do ambiente =", SENHA_CORRETA)


# Segurança: se estiver em desenvolvimento e a variável não existir, define uma senha temporária
# **** Só para DEV local: remova/override no servidor! ****
if not SENHA_CORRETA:
    #senha amigável para DEV local. Troque ou remova em produção.
    SENHA_CORRETA = "dev_local_change_me"
    print("⚠️ AVISO: variável de ambiente PONTO_PASSWORD não definida. Usando senha de DEV local.")


def tela_login(page: ft.Page):
    """
    Tela de login futurista + responsiva
    - Enter confirma
    - Card translúcido
    - Imagem centralizada
    - Rodapé adicionado
    """

    # Config da página
    page.title = "Login - Controle de Ponto"
    page.window_scroll = "auto"
    page.bgcolor = "#071027"

    # --- INPUT / MENSAGENS ---
    senha_input = ft.TextField(
        label="Senha",
        password=True,
        can_reveal_password=True,
        width=320,
        filled=True,
        bgcolor="#0b1220",
        color="white",
        label_style=ft.TextStyle(color="#bcd8ff"),
    )

    mensagem_erro = ft.Text("", color=ft.Colors.RED_300, size=13)

    texto_motivacional = ft.Text(
        "Você é totalmente substituível no trabalho, mas não pode ser substituído em casa.\nMantenha isso em perspectiva.",
        size=12,
        italic=True,
        color="#9fb7ff",
        text_align=ft.TextAlign.CENTER
    )

    # --- LOGIN ---
    def tentar_entrar(e=None):
        if senha_input.value == SENHA_CORRETA:
            page.clean()
            main(page)
        else:
            mensagem_erro.value = "Senha incorreta!"
            page.update()

    senha_input.on_submit = tentar_entrar

    def on_key(e):
        k = getattr(e, "key", None) or getattr(e, "key_name", None)
        if k in ("Enter", "Return"):
            tentar_entrar()

    page.on_keyboard_event = on_key

    # --- BOTÃO ---
    btn_entrar = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.LOGIN, color="white", size=16),
                ft.Text("Entrar", size=15, weight="bold", color="white"),
            ],
            alignment=ft.MainAxisAlignment.CENTER
        ),
        width=320,
        height=48,
        border_radius=12,
        bgcolor="#0f62fe",
        on_click=tentar_entrar
    )

    # --- CARD LOGIN ---
    card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            ft.Icon(ft.Icons.ACCESS_TIME_FILLED, size=46, color="#a9d1ff"),
                            padding=ft.padding.all(8),
                            bgcolor="#071b2b",
                            border_radius=12
                        ),
                        ft.Column(
                            [
                                ft.Text("CONTROLE DE PONTO", size=20, weight="bold", color="white"),
                                ft.Text("Acesso Seguro", size=12, color="#9fb7ff")
                            ],
                            spacing=4
                        )
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=12
                ),
                ft.Divider(height=12, color="transparent"),
                senha_input,
                ft.Divider(height=8, color="transparent"),
                btn_entrar,
                ft.Divider(height=10, color="transparent"),
                mensagem_erro,
                ft.Divider(height=8, color="transparent"),
                texto_motivacional,
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=420,
        padding=ft.padding.symmetric(vertical=22, horizontal=20),
        border_radius=16,
        bgcolor=ft.Colors.with_opacity(0.35, "#071831"),
        border=ft.border.all(1, "#11304f"),
        shadow=ft.BoxShadow(blur_radius=22, color=ft.Colors.with_opacity(0.35, "black")),
    )

    # --- BACKGROUND (compatível com Flet 0.28.3) ---
    bg = ft.Container(
        content=ft.Image(
            src="https://images.unsplash.com/photo-1535223289827-42f1e9919769?auto=format&fit=crop&w=1500&q=80",
            fit=ft.ImageFit.COVER,
        ),
        expand=True,
    )

    overlay = ft.Container(
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.45, "#031225")
    )

    # Neon decor
    neon_top = ft.Container(
        height=6,
        bgcolor="#0f62fe",
        opacity=0.08,
        margin=ft.margin.only(bottom=18),
        border_radius=8,
        width=420
    )


    rodape = ft.Text(
        "© 2025 Controle de Ponto — Desenvolvido por YannaMedova",
        size=11,
        color="#9fb7ff",
        text_align=ft.TextAlign.CENTER
    )

    # --- MONTAGEM FINAL ---
    stack = ft.Stack(
        [
            bg,
            overlay,
            ft.Container(
                content=ft.Column(
                    [
                        neon_top,
                        card,
                        ft.Divider(height=22, color="transparent"),
                        rodape
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                alignment=ft.alignment.center,
                expand=True
            ),
        ],
        expand=True
    )

    page.controls.clear()
    page.add(stack)
    page.update()


# =============================
# APP STARTER
# =============================
if __name__ == "__main__":
    ft.app(
        target=tela_login,
        view=ft.WEB_BROWSER,
        host="0.0.0.0",
        port=8000
    )

