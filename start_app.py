import os, time
import main
import flet as ft

# >>> CONFIGURAR FUSO HORÁRIO PARA BRASIL (Render usa UTC)
os.environ["TZ"] = "America/Sao_Paulo"
try:
    time.tzset()  # Funciona em sistemas Linux (como Render)
except:
    pass
# <<<

def _run():
    ft.app(
        target=main.main,
        view=ft.WEB_BROWSER,   # Abre no navegador no Render
        port=8000,             # Porta padrão correta do Render
        host="0.0.0.0"         # Necessário para Render aceitar conexões externas
    )

if __name__ == "__main__":
    _run()
