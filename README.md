# 🏛️ MAST - Monitoramento Automatizado de Sistemas e Tribunais

> Um robô de OSINT (Open Source Intelligence) de motor duplo, construído em Python, para monitorizar, filtrar e alertar sobre a disponibilidade, segurança e atualizações dos sistemas do Poder Judiciário Brasileiro.

O **MAST** vigia continuamente a internet à procura de incidentes de TI, indisponibilidades (PJe, eproc, e-SAJ, Projudi), ciberataques, implementação de MFA/2FA e novas portarias em **63 tribunais brasileiros** (STF, STJ, TJs, TRFs, TRTs e TREs).

---

## ✨ Arquitetura de Duplo Motor (Dual-Engine)

O MAST agora opera com dois scripts independentes e complementares para garantir que nenhum aviso passe despercebido:

### 📡 Motor 1: Google News RSS (`script.py`)
- **Busca Focada:** Utiliza operadores avançados (`site:jus.br OR site:csjt.jus.br`) no Google News para varrer apenas domínios oficiais, eliminando ruído de jornais locais e blogs jurídicos.
- **Filtro de Malha Fina:** Um algoritmo analisa o título de cada notícia para garantir que ela contém *Termos Fortes* de TI (ex: "ransomware", "instabilidade", "pje") antes de disparar o alerta.
- **Smart Links Oficiais:** Ao detetar uma notícia sobre um tribunal específico (ex: "TJSP"), o robô cruza a informação com o banco de dados interno e anexa ao alerta um link direto para a página de status oficial daquele tribunal.

### 🕷️ Motor 2: Scraper de Fontes Oficiais (`scraper_oficial.py`)
- **Varredura Direta:** Acessa ativamente o código-fonte de mais de 60 páginas de indisponibilidade oficiais, murais de avisos e diários eletrónicos.
- **Integração com Telegram:** Lê e processa mensagens diretamente do canal oficial *PJe News* (`t.me/s/pjenews`).
- **Filtro Anti-Ruído Estrutural:** Utiliza inteligência no `BeautifulSoup` para "apagar" virtualmente menus de navegação (`<nav>`), cabeçalhos e rodapés dos sites antes da análise, garantindo que o alerta seja disparado apenas pelo conteúdo real da página e não por botões fixos.

---

## 📧 Notificações e Relatórios
- **Design Distinto:** Gera relatórios responsivos em HTML. Alertas de notícias (RSS) chegam com detalhes em azul, enquanto detecções diretas nos painéis (Scraper) chegam sinalizadas em vermelho.
- **Integração Nativa:** Envia alertas automaticamente via SMTP (E-mail). Pode ser facilmente integrado ao Slack utilizando a funcionalidade de "Enviar e-mail para o canal".

---

## 🛠️ Tecnologias Utilizadas

- **Python 3.12+**
- **Feedparser** (Leitura e conversão de RSS)
- **Requests & BeautifulSoup4** (Web Scraping e parsing de HTML)
- **Urllib & Urllib3** (Codificação de Queries e bypass de certificados SSL governamentais)
- **Smtplib & Email.mime** (Geração e envio de e-mails)
- **GitHub Actions** (Automação, Agendamento Cron e ambiente Serverless)

---

## 🚀 Como Configurar (Deploy no GitHub Actions)

### 1. Preparar o Repositório
Adicione os dois ficheiros principais na raiz do seu repositório:
- `script.py`
- `scraper_oficial.py`

### 2. Configurar as Variáveis de Ambiente (Secrets)
Para que os robôs consigam enviar os relatórios de forma segura, vá a:
`Settings` > `Secrets and variables` > `Actions` > `New repository secret`.

Adicione as seguintes variáveis:
- `EMAIL_REMETENTE`: O e-mail que vai **enviar** o alerta (ex: `seu-email-bot@gmail.com`).
- `EMAIL_SENHA`: A palavra-passe de aplicação do seu e-mail (se usar Gmail, crie uma [App Password](https://myaccount.google.com/apppasswords)).
- `EMAIL_DESTINATARIO`: O e-mail que vai **receber** o alerta. *(Dica: Se utiliza o Slack, crie um endereço de e-mail de integração do canal e cole aqui).*

### 3. Criar a Automação (.yml)
Crie um ficheiro no seguinte caminho: `.github/workflows/monitor.yml` e cole o código abaixo. *Neste exemplo, o robô está programado para rodar todos os dias às 08h00 (horário de Brasília).*

```yaml
name: MAST - Monitoramento Automatizado de Sistemas e Tribunais

on:
  schedule:
    - cron: '0 11 * * 4' 
  workflow_dispatch: 

jobs:
  rodar-monitoramento:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout do código
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12' 

      - name: Instalar Dependências
        run: |
          python -m pip install --upgrade pip
          pip install feedparser requests beautifulsoup4

      - name: Executar o Monitor e o Scraper
        env:
          EMAIL_REMETENTE: ${{ secrets.EMAIL_REMETENTE }}
          EMAIL_SENHA: ${{ secrets.EMAIL_SENHA }}
          EMAIL_DESTINATARIO: ${{ secrets.EMAIL_DESTINATARIO }}
        run: |
          python script.py
          python scraper_oficial.py
