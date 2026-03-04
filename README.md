# 🏛️ MAST - Monitoramento Automatizado de Sistemas e Tribunais

> Um robô de OSINT (Open Source Intelligence) construído em Python para monitorizar, filtrar e alertar sobre a disponibilidade, segurança e atualizações dos sistemas do Poder Judiciário Brasileiro.

O **MAST** vigia continuamente as notícias indexadas no Google News à procura de incidentes de TI, indisponibilidades (PJe, eproc, e-SAJ, Projudi), ciberataques, implementação de MFA/2FA e novas portarias em **63 tribunais brasileiros** (STF, STJ, TJs, TRFs, TRTs e TREs).

---

## ✨ Funcionalidades

- **📡 Coleta Automatizada (RSS):** Realiza buscas semanais ou diárias através dos feeds RSS do Google News utilizando blocos temáticos otimizados para evitar bloqueios.
- **🛡️ Filtro de Malha Fina (Anti-Ruído):** O script não confia cegamente na busca. Um algoritmo em Python analisa o título de cada notícia para garantir que ela contém *Termos Fortes* de TI (ex: "ransomware", "instabilidade", "pje", "2fa") antes de disparar o alerta, eliminando o "Efeito Rodapé" de portais de notícias.
- **🔗 Smart Links Oficiais:** Quando uma notícia cita um tribunal específico (ex: "TJSP"), o robô cruza a informação com um banco de dados interno e anexa ao alerta o **link direto para a página de status ou certidão de indisponibilidade oficial** daquele tribunal.
- **📧 Alertas Multicanal (E-mail e Slack):** Gera relatórios responsivos em HTML e envia automaticamente via SMTP. Pode ser facilmente integrado a canais do Slack utilizando a funcionalidade de "Enviar e-mail para o canal" do Slack.
- **☁️ 100% Serverless:** Desenvolvido para rodar nativamente e sem custos no GitHub Actions (via `.yml`).

---

## 🛠️ Tecnologias Utilizadas

- **Python 3.12+**
- **Feedparser** (Leitura e conversão de RSS)
- **Urllib** (Codificação de Queries para o Google News)
- **Smtplib & Email.mime** (Geração e envio de e-mails em HTML e Plain Text)
- **GitHub Actions** (Agendamento Cron e CI/CD)

---

## 🚀 Como Configurar (Deploy no GitHub Actions)

Siga os passos abaixo para colocar o seu monitoramento a funcionar em poucos minutos, de forma totalmente automatizada.

### 1. Preparar o Repositório
Crie um ficheiro chamado `script.py` na raiz do seu repositório com o código em Python do MAST.

### 2. Configurar as Variáveis de Ambiente (Secrets)
Para que o robô consiga enviar os e-mails sem expor a sua palavra-passe, vá a:
`Settings` > `Secrets and variables` > `Actions` > `New repository secret`.

Adicione as seguintes variáveis:
- `EMAIL_REMETENTE`: O e-mail que vai **enviar** o alerta (ex: `seu-email-bot@gmail.com`).
- `EMAIL_SENHA`: A palavra-passe de aplicação do seu e-mail (se usar Gmail, crie uma [App Password](https://myaccount.google.com/apppasswords)).
- `EMAIL_DESTINATARIO`: O e-mail que vai **receber** o alerta. *(Dica: Se utiliza o Slack, crie um endereço de e-mail de integração para um canal e cole aqui).*

### 3. Criar a Automação (.yml)
Crie um ficheiro no seguinte caminho: `.github/workflows/monitor.yml` e cole o código abaixo:

```yaml
name: Monitor de Notícias OSINT

on:
  schedule:
    - cron: '0 11 * * *' # Executa todo dia às 9h00 (Horário de Brasília)
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
          pip install feedparser

      - name: Executar o Monitor
        env:
          EMAIL_REMETENTE: ${{ secrets.EMAIL_REMETENTE }}
          EMAIL_SENHA: ${{ secrets.EMAIL_SENHA }}
          EMAIL_DESTINATARIO: ${{ secrets.EMAIL_DESTINATARIO }}
        run: python script.py
