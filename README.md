# 🏛️ MAST - Monitoramento Automatizado de Sistemas e Tribunais

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/Build-Automated-success.svg)](https://github.com/mantiniDev/noticias_alertas_2FA/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Um robô de **OSINT (Open Source Intelligence)** e **Threat Intelligence** de motor duplo, construído em Python, para monitorizar, filtrar e alertar sobre a disponibilidade, segurança e atualizações dos sistemas do Poder Judiciário Brasileiro.

O **MAST** vigia continuamente a internet à procura de incidentes de TI, indisponibilidades de sistemas (PJe, eproc, e-SAJ, Projudi), ciberataques, implementação de MFA/2FA e novas portarias em mais de **60 tribunais brasileiros** (STF, STJ, TJs, TRFs, TRTs e TREs).

---

## ✨ Arquitetura de Duplo Motor (Dual-Engine)

O MAST opera com dois scripts independentes e complementares para garantir que nenhum aviso passe despercebido, criando um ecossistema redundante e de altíssima precisão:

### 📡 Motor 1: Google News RSS Avançado (`script.py`)
- **Busca Focada e Dinâmica:** Lê a base de dados interna de tribunais, extrai os domínios (ex: `tjsp.jus.br`) e cria queries avançadas no Google News agrupadas em lotes, evitando bloqueios da API (Erro 400).
- **Filtro de Malha Fina (Regex):** Um algoritmo analisa o título de cada notícia para garantir que ela contém termos exatos de TI. Plurais são aceitos automaticamente, e palavras inseridas no meio de outras (ex: `SSO` dentro de `processo`) são ignoradas.
- **Smart Links Oficiais:** Ao detetar uma notícia sobre um tribunal específico, o robô cruza a informação com a base e anexa ao e-mail de alerta um link direto para a página de status/certidão oficial daquele tribunal.

### 🕷️ Motor 2: Scraper de Fontes Oficiais (`scraper_oficial.py`)
- **Varredura Direta (Passive-Aggressive):** Acessa ativamente o código-fonte de dezenas de páginas de indisponibilidade oficiais, murais de avisos e diários eletrônicos.
- **Filtro Anti-Ruído Estrutural:** Utiliza o `BeautifulSoup` para "apagar" virtualmente menus de navegação (`<nav>`), cabeçalhos e rodapés antes da análise. O alerta só dispara se o conteúdo estiver no texto real da página, ignorando botões fixos.
- **Integração Telegram:** Lê e processa mensagens diretamente da interface web do canal oficial *PJe News* (`t.me/s/pjenews`).

---

## 🛠️ Tecnologias Utilizadas

- **Python 3.12+**
- **Feedparser** (Leitura, extração e parsing de RSS)
- **Requests & BeautifulSoup4** (Web Scraping e higienização de DOM/HTML)
- **Urllib & Urllib3** (Codificação de Queries e bypass de certificados SSL governamentais)
- **Re & Unicodedata** (Expressões Regulares e normalização de texto para o filtro de malha fina)
- **Smtplib & Email.mime** (Geração de relatórios responsivos em HTML e Plain Text)
- **GitHub Actions** (Automação, CI/CD, Cron Jobs e ambiente Serverless)

---

## 🚀 Como Configurar e Rodar

O projeto foi desenhado para rodar nativamente e sem custos no **GitHub Actions**.

### 1. Preparar as Variáveis de Ambiente (Secrets)
Vá até a aba `Settings` > `Secrets and variables` > `Actions` > `New repository secret` no seu repositório e adicione:
- `EMAIL_REMETENTE`: O e-mail que vai enviar os relatórios automatizados.
- `EMAIL_SENHA`: A App Password (Senha de Aplicativo) do seu provedor de e-mail.
- `EMAIL_DESTINATARIO`: O e-mail (ou e-mail de integração de canal do Slack/Teams) que receberá os alertas.

### 2. Pipeline Automatizada
O projeto já conta com o arquivo `.github/workflows/monitor.yml`. Por padrão, o sistema rodará todos os dias automaticamente e enviará o relatório para os destinatários cadastrados.

Se desejar forçar uma execução manual:
1. Vá na aba **Actions**.
2. Selecione o workflow **MAST - Monitoramento Automatizado**.
3. Clique em **Run workflow**.

---

## 🚧 Desafios Superados na Engenharia de Dados

Durante o desenvolvimento deste SOC automatizado, diversos desafios comuns em scraping/OSINT foram resolvidos:

* **O Problema do "Ruído Administrativo" (Falsos Positivos):** Tribunais publicam muito sobre RH, concursos e orçamento. Criamos uma *Blacklist* (`TERMOS_BLOQUEADOS`) aliada a Expressões Regulares (`\b`) que bloqueia sumariamente notícias não-técnicas.
* **Rate Limits do Google (Erro 400):** Pesquisar em mais de 60 sites de uma vez gerava erro de "URL Too Large". A solução foi desenvolver uma lógica de paginação que divide os domínios em blocos de 20.
* **Erros Ortográficos e Plurais (Falsos Negativos):** A busca por "ciberataque" ignorava "ciberataques". O motor foi aprimorado com regex flexível `(s|es)?` e a biblioteca `unicodedata` foi implementada para remover acentos (`manutencao` == `manutenção`) antes de qualquer validação.

---

## 🧠 Customização

Para adicionar novos termos de monitoramento cibernético, basta editar as listas no topo dos scripts:
- `TERMOS_FORTES_TI` e `TERMOS_COMPOSTOS`: Gatilhos para acionar o envio de e-mails.
- `TERMOS_BLOQUEADOS`: Palavras que reprovam e descartam a notícia instantaneamente.

---

*Desenvolvido por [mantiniDev](https://github.com/mantiniDev) - Focado em Cibersegurança, Threat Intelligence e SRE para infraestruturas críticas.*
