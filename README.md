# 🏛️ MAST - Monitoramento Automatizado de Sistemas e Tribunais

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/Build-Automated-success.svg)](https://github.com/mantiniDev/noticias_alertas_2FA/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Um robô de **OSINT (Open Source Intelligence)** e **Threat Intelligence** construído em Python, focado em monitorizar, filtrar e alertar sobre a disponibilidade, segurança e atualizações dos sistemas do Poder Judiciário Brasileiro.

O **MAST** vigia continuamente a internet à procura de incidentes de TI, indisponibilidades de sistemas (PJe, eproc, e-SAJ, Projudi), ciberataques, implementação de MFA/2FA e novas portarias em mais de **60 tribunais brasileiros** (STF, STJ, TJs, TRFs, TRTs e TREs).

---

## ✨ Arquitetura Atual: Motor de Busca Avançada Modular

Nesta versão atual, o MAST opera através de um poderoso motor de varredura baseado no ecossistema de indexação de notícias, projetado com uma arquitetura modular de software para altíssima precisão e facilidade de manutenção:

- **Busca Focada e Dinâmica:** O sistema lê a base de dados interna de tribunais, extrai os domínios (ex: `tjsp.jus.br`) e cria queries avançadas no Google News agrupadas em lotes, evitando bloqueios da API (Erro 400).
- **Filtro de Malha Fina (Regex):** Um algoritmo passa as notícias por um "Raio-X" para garantir que contêm termos exatos de TI. Plurais são aceitos automaticamente, e palavras inseridas no meio de outras (ex: `SSO` dentro de `processo`) são ignoradas.
- **Bloqueio de Falsos Positivos:** Notícias sobre RH, concursos, orçamento ou eleições (que costumam poluir os feeds do judiciário) são sumariamente descartadas por uma *Blacklist* interna.
- **Smart Links Oficiais:** Ao detetar uma notícia sobre um tribunal específico, o robô cruza a informação com a base e anexa ao e-mail de alerta um link direto para a página de status/certidão oficial daquele tribunal.

---

## 📁 Estrutura do Projeto

O código-fonte foi desenhado para escalabilidade corporativa, dividindo lógicas em módulos:

```text
noticias_alertas_2FA/
│
├── config/
│   └── settings.py       # Constantes, URLs dos tribunais e listas de palavras-chave
│
├── core/
│   ├── filter.py         # Lógica da malha fina (Regex, remoção de acentos e filtros)
│   ├── scraper.py        # Lógica de extração de domínios, busca no Google e RSS
│   └── notifier.py       # Geração de relatórios HTML e integração SMTP
│
├── main.py               # Orquestrador principal da aplicação
└── .github/workflows/    # Pipeline de automação CI/CD
```

---

## 🗺️ Roadmap: Próxima Versão (Arquitetura de Motor Duplo)

Para a próxima grande atualização do MAST, já está em fase de testes a implementação do **Motor Secundário (Scraper Direto de Fontes Oficiais)**, que trabalhará em paralelo com o motor atual para criar um ecossistema 100% redundante:

- **Varredura Direta (Passive-Aggressive):** Acessará ativamente o código-fonte de dezenas de páginas de indisponibilidade oficiais e painéis de aviso (sem depender de indexadores de busca).
- **Filtro Anti-Ruído Estrutural:** Utilizará o `BeautifulSoup` para "apagar" virtualmente menus de navegação (`<nav>`) e rodapés antes da análise, garantindo que o alerta só dispare pelo conteúdo real da página.
- **Integração Telegram:** Fará a leitura direta da interface web de canais oficiais como o *PJe News* (`t.me/s/pjenews`).

---

## 🛠️ Tecnologias Utilizadas (Versão Atual)

- **Python 3.12+**
- **Feedparser** (Leitura, extração e parsing de RSS)
- **Urllib & Urllib3** (Codificação de Queries de busca)
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
O projeto já conta com o fluxo de integração configurado. Por padrão, o sistema rodará todos os dias automaticamente chamando o orquestrador `main.py` com o `PYTHONPATH` ajustado.

Se desejar forçar uma execução manual:
1. Vá na aba **Actions**.
2. Selecione o workflow de monitoramento.
3. Clique em **Run workflow**.

---

## 🚧 Desafios Superados na Engenharia de Dados

Durante o desenvolvimento deste SOC automatizado, diversos desafios comuns em OSINT foram resolvidos:

* **O Problema do "Ruído Administrativo":** Tribunais publicam muito sobre administração. Criamos uma *Blacklist* (`TERMOS_BLOQUEADOS`) aliada a Expressões Regulares (`\b`) que bloqueia sumariamente notícias não-técnicas.
* **Rate Limits de Buscadores (Erro 400):** Pesquisar em mais de 60 sites de uma vez gerava erro de "URL Too Large". A solução foi desenvolver uma lógica de paginação que divide os domínios em pequenos blocos seguros.
* **Erros Ortográficos e Plurais:** A busca por "ciberataque" ignorava "ciberataques". O motor foi aprimorado com regex flexível `(s|es)?` e a biblioteca `unicodedata` foi implementada para remover acentos (`manutencao` == `manutenção`) antes da validação.

---

## 🧠 Customização

Graças à arquitetura modular, modificar os gatilhos de alerta é extremamente simples e não requer edição de lógica de código. 

Para adicionar novos termos de monitoramento cibernético, basta editar as listas no arquivo **`config/settings.py`**:
- `TERMOS_FORTES_TI` e `TERMOS_COMPOSTOS`: Gatilhos para acionar o envio de e-mails.
- `TERMOS_BLOQUEADOS`: Palavras que reprovam e descartam a notícia instantaneamente.

---

*Desenvolvido por [mantiniDev](https://github.com/mantiniDev) - Focado em Cibersegurança, Threat Intelligence e SRE para infraestruturas críticas.*
```