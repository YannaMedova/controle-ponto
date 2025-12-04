<h1 align="center">🕒 Sistema de Controle de Ponto (Web App)</h1>

<p align="center">
  <img src="https://media.giphy.com/media/ZVik7pBtu9dNS/giphy.gif" width="300" alt="animation">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-Em%20Desenvolvimento-blue" alt="Status">
  <img src="https://img.shields.io/badge/Python-3.x-blue" alt="Python">
  <img src="https://img.shields.io/badge/Framework-Flet-red" alt="Flet">
  <img src="https://img.shields.io/badge/Armazenamento-JSON-orange" alt="JSON">
  <img src="https://img.shields.io/badge/Deploy-Render-green" alt="Render">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Made%20By-Yanna%20Medova-purple?style=for-the-badge" alt="Yanna">
  <img src="https://img.shields.io/badge/Projeto-Controle%20de%20Ponto-blue?style=for-the-badge" alt="Projeto">
</p>

---

## 🌟 Visão Geral

Este projeto surgiu da necessidade de criar uma maneira **simples, prática e acessível** de registrar horários de trabalho, especialmente para uso individual ou para pequenos grupos em ambientes remotos.

A aplicação permite **registrar pontos**, **visualizar histórico**, **exportar dados**, **personalizar perfis** e opera totalmente via navegador utilizando **Flet Web**.

O objetivo principal é oferecer uma solução leve, gratuita e funcional, com foco em **produtividade**, **segurança** e **facilidade de uso** — sem depender de plataformas pagas ou complicadas.

---

## ✨ Funcionalidades

| Função | Descrição |
|---|---|
| 🕒 **Bater ponto automático** | Botão simples que marca data e hora automaticamente. |
| 🗂 Histórico Completo | Exibição de todos os registros anteriores de forma organizada. |
| 📊 Cálculo Automático | Soma diária e mensal em tempo real. |
| 📤 Exportação | Exporta dados em **Excel (XLSX)** e **PDF**. |
| 📥 **Importação** | Importa histórico de PDFs. |
| 🔐 Tela de Login | Senha carregada via **variável de ambiente** para segurança. |
| ⚙ Configurações Gerais | Ajustes de parâmetros básicos do sistema. |
| 💾 Armazenamento | Dados persistidos localmente em **JSON** (com upgrade futuro para SQL). |
| 🕘 Correção Automática de Fuso | Ajuste automático para **America/Sao_Paulo** no servidor. |
| 🎨 **Interface Flet Web** | Leve, responsiva e moderna. |
| 🌐 100% Web | Roda no navegador sem instalação, ideal para uso remoto. |
| 👤 **(EM BREVE) Edição de Perfil** | Alterar nome, setor e informações pessoais. |
| 🗄 **(EM BREVE) Banco SQL** | Migração opcional para SQL, permitindo multiusuários. |

---

## 🛠 Tecnologias Utilizadas

| Área | Ferramentas |
|---|---|
| **Backend** | Python 3 |
| **Frontend/Web** | Flet (Python) |
| Armazenamento | JSON (com migração futura para SQL) |
| Exportação | Pandas, OpenPyXL, PDF |
| **Importação PDF** | PDFPlumber |
| **Deploy** | Render.com (free tier) |
| Controle de Versão | GitHub |
| **Segurança** | Variáveis de ambiente |

---

## 🖥 Capturas de Tela

### Tela Inicial
<img width="1425" height="736" alt="Captura de tela 2025-12-04 125810" src="https://github.com/user-attachments/assets/6e3cf360-6c17-4738-9e75-9f276f38b32f" />

### Registro de Ponto
<img width="1911" height="766" alt="Captura de tela 2025-11-27 140343" src="https://github.com/user-attachments/assets/399b401f-4422-45c3-ae2b-eae74ee415f0" />
<img width="1916" height="763" alt="Captura de tela 2025-11-27 140318" src="https://github.com/user-attachments/assets/f7f18aa1-776e-4ea1-b8a1-2fbe6b6a9031" />
<img width="1880" height="320" alt="Captura de tela 2025-11-27 140219" src="https://github.com/user-attachments/assets/167c48a1-5c15-4205-872c-7bb8bd334872" />
<img width="1877" height="323" alt="Captura de tela 2025-11-27 135933" src="https://github.com/user-attachments/assets/509ab72d-3921-4f28-b486-312bd890cadb" />

---

## 🎯 O que Este Projeto Demonstra Sobre Mim

- Capacidade de criar **aplicações web completas**, do backend à interface, usando Python.  
- Experiência com **Flet**, um framework moderno de apps web/PWA.  
- Compreensão de **persistência de dados** e lógica de negócio.  
- Cuidado com **UX/UI**, mesmo usando uma biblioteca minimalista.  
- Boa prática de **segurança**: senha via variável de ambiente, sem expor no código.  
- Capacidade de **deploy em ambiente real** (Render).
- Evolução constante: roadmap claro e melhorias planejadas.
- Solução criada a partir de problema real — não projeto escolar.

---

## 🧠 Aprendizados Técnicos

- Configuração de timezone manual em servidores Linux/UTC.  
- Separação entre lógica, interface e dados.  
- Uso correto de **variáveis de ambiente** para segurança.  
- Controle de data/hora e registro consistente.
- Deploy de aplicações Flet em servidores como **Render**.
- Upload seguro sem versionar dados sensíveis (.gitignore).
- Persistência local via JSON com criação dinâmica de arquivos + migração planejada para SQL.  

---

## 🔮 Próximos Passos (Roadmap)

- 🔄 Migrar armazenamento de JSON para **SQLite**.
- ➕ **Adicionar edição de perfil** (nome do usuário, papel, configurações pessoais). 
- 👥 Suporte para **vários colaboradores** usando banco SQL.  
- 🌐 Criar **painel de administração** com visualização de colaboradores.  
- 🧾 Relatórios avançados por período (semanal/mensal).
- 📨 Notificações e lembrete de ponto.  
- 🧩 Widgets extras no painel (gráficos, KPIs).  
- 📱 Layout responsivo para uso em smartphone.
- 🧪 Implementar testes automatizados. 

---

## 👩‍💻 Autora

**Yanna Medova**  
Brasília / DF  
Estudante de Defesa Cibernética (3º Semestre)  
LinkedIn: https://www.linkedin.com/in/yanna-medova-cyber
GitHub: https://github.com/YannaMedova

---

<p align="center">
  <i>“Resolvendo problemas reais com soluções automatizadas.”</i>
</p>
