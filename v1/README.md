# 🏛️ MAST — Monitoramento Automatizado de Sistemas e Tribunais

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-success.svg)](https://github.com/features/actions)
[![Testes](https://img.shields.io/badge/testes-1398%20passando-brightgreen.svg)](#-testes)
[![Fontes Fase 3](https://img.shields.io/badge/fontes-104%20tribunais-orange.svg)](#-fase-3--not%C3%ADcias-expandidas)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Robô de **inteligência de fontes abertas (OSINT)** desenvolvido em Python para monitorar, filtrar e alertar sobre indisponibilidades de sistemas, ciberataques, novas portarias e notícias de TI de **mais de 100 fontes do Poder Judiciário Brasileiro**.

O MAST executa diariamente via GitHub Actions (10h UTC), consolida notícias de três pipelines independentes e envia um **e-mail HTML categorizado por grupo de tribunal**, com relatórios **CSV** e **PDF** anexados.

---

## 🗂️ Índice

- [Como Funciona](#-como-funciona)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Fluxo de Execução](#-fluxo-de-execução)
- [Grupos e Fontes Monitoradas](#-grupos-e-fontes-monitoradas)
- [Tecnologias](#-tecnologias)
- [Configuração e Deploy](#-configuração-e-deploy)
- [Execução Local](#-execução-local)
- [Testes](#-testes)
- [Scripts de Diagnóstico](#-scripts-de-diagnóstico)

---

## ✨ Como Funciona

O MAST opera em **três fases sequenciais** a cada execução:

### Fase 1 — Scraper RSS (Google News)
Busca notícias dos últimos 2 dias cruzando siglas de tribunais com palavras-chave de TI/SRE (`PJe`, `indisponível`, `MFA`, `ciberataque`, `instabilidade`, `2FA`, etc.) via Google News RSS. Resultado: lista de notícias filtradas pelo motor de palavras-chave.

### Fase 2 — Scraper Direto (Portais Oficiais)
Acessa diretamente as **páginas de indisponibilidade** de 61 fontes do Judiciário (STF, STJ, TJs, TRFs, TRTs, TREs) para capturar alertas de sistemas que ainda não chegaram ao Google News. Suporta páginas estáticas (via `requests`) e dinâmicas (via **Playwright/Chromium**).

### Fase 3 — Notícias Expandidas (104 Fontes)
Varre diretamente as **seções de notícias e normativos** de 104 fontes organizadas por grupo de tribunal, com parser genérico multi-CMS capaz de lidar com Liferay, Drupal, WordPress, portais JSF e CMSs customizados. Resultado: notícias categorizadas prontas para o e-mail.

### Consolidação e Notificação
As três fases são unificadas em um único relatório por categoria de tribunal. Itens de **Indisponibilidade** recebem destaque visual (borda vermelha) no e-mail. O relatório completo é enviado com anexos **CSV** e **PDF**, e os dados brutos são exportados para **Google Sheets**.

---

## 📁 Estrutura do Projeto

```
v1/
├── main.py                      # Orquestrador principal (Fases 1, 2 e 3)
│
├── config/
│   └── settings.py              # Constantes globais, palavras-chave, URLs, limites
│
├── core/
│   ├── scraper.py               # Fase 1 — RSS/Google News
│   ├── scraper_direto.py        # Fases 2 e 3 — scraper direto + 104 parsers
│   ├── filter.py                # Motor de filtro: regex, normalização, deduplicação
│   ├── notifier.py              # Geração de HTML/texto e envio de e-mail SMTP
│   ├── database.py              # SQLite — persistência e controle de duplicatas
│   ├── csv_generator.py         # Geração do relatório CSV
│   ├── pdf_generator.py         # Geração do relatório PDF
│   └── sheets_writer.py         # Exportação para Google Sheets via webhook
│
├── tests/
│   ├── test_scraper_direto.py   # 1300+ testes para parsers e scraper direto
│   ├── test_filter.py           # Testes do motor de filtragem
│   ├── test_database.py         # Testes de persistência
│   └── test_csv_generator.py    # Testes de geração de relatório
│
├── diagnostico_fase3.py         # Script de diagnóstico das 104 fontes da Fase 3
├── inspecionar_zeros.py         # Script de inspeção de fontes com ZERO itens
│
└── .github/
    └── workflows/
        └── main.yml             # Pipeline CI/CD — cron diário 10h UTC
```

---

## 🔄 Fluxo de Execução

```
main.py
  │
  ├── 1. init_db()                      → Cria/verifica tabelas no SQLite
  │
  ├── 2. buscar_noticias_semanais()     → Fase 1: RSS + filtro de palavras-chave
  │
  ├── 3. buscar_noticias_direto()       → Fase 2: scraper direto de indisponibilidades
  │
  ├── 4. buscar_noticias_fontes()       → Fase 3: 104 fontes de notícias por categoria
  │
  ├── 5. Deduplicação (Fases 1+2)       → por link e por título normalizado
  │
  ├── 6. Consolidação por grupo         → {grupo: [itens]} com todas as fases
  │
  ├── 7. gerar_csv_relatorio()          → CSV com últimos N registros do banco
  ├── 8. gerar_pdf_relatorio()          → PDF com mesma base
  │
  ├── 9. gerar_corpos_email()           → HTML + texto categorizado por tribunal
  ├── 10. enviar_email()                → SMTP com CSV e PDF anexados
  │
  └── 11. enviar_para_sheets()          → Dados brutos para Google Sheets
```

---

## 🏛️ Grupos e Fontes Monitoradas

| Grupo | Descrição | Fontes (Fase 3) |
|-------|-----------|-----------------|
| **Sistemas-CNJ** | PJe, CNJ, PDPJ-Br, Justiça 4.0 | 5 |
| **Tribunais-Superiores** | STF, STJ, TST, TSE, STM, CJF, CNMP, CSJT | 9 |
| **Tribunais-Estaduais** | TJs de todos os 27 estados | 29 |
| **TRFs** | TRF1 a TRF6 + atos normativos | 8 |
| **TRTs** | TRT1 a TRT24 | 27 |
| **TREs** | TRE de todos os estados | 27 |
| **TOTAL** | | **104 fontes** |

> **Taxa de sucesso atual (Fase 3):** 93/94 fontes ativas = **99%**
> (1 ZERO temporário por erro HTTP 500 no servidor do tribunal)

### Fontes marcadas como PULADO (skip)

Fontes legitimamente inacessíveis para scraper externo:

| Motivo | Fontes |
|--------|--------|
| Formulário/busca JS (sem listagem estática) | CNJ-Norm, TJPR-Norm, TRF4-Norm, TRT9 |
| Geo-bloqueio / rede interna do tribunal | TJRN |
| Redirecionamento para login | TRF2 |
| Bloqueio de scraper (retorna None) | TRF3 |
| URL inexistente (404) | TRT10 |
| Bot detection (Cloudflare JS challenge) | TRT17 |
| Timeout Playwright — inacessível externamente | TJPI |

---

## 🔧 Tecnologias

| Biblioteca | Versão | Uso |
|---|---|---|
| `requests` / `urllib3` | — | Fetch HTTP de portais estáticos |
| `beautifulsoup4` + `lxml` | — | Parsing HTML multi-CMS |
| `playwright` (Chromium) | — | Renderização de portais JS-only (SPA, Liferay, etc.) |
| `feedparser` | — | Parsing de feeds RSS/Atom (Fase 1 + STJ) |
| `sqlite3` | built-in | Persistência e deduplicação de notícias |
| `smtplib` / `email.mime` | built-in | Geração de e-mail HTML responsivo + SMTP |
| `reportlab` | — | Geração de relatório PDF |
| `re` / `unicodedata` | built-in | Normalização e filtragem por regex |
| `pytest` | — | 1398 testes automatizados |
| **GitHub Actions** | — | CI/CD, cron job diário, cache SQLite |

**Python 3.12+** é necessário.

---

## 🚀 Configuração e Deploy

O MAST foi projetado para rodar **sem custos** no GitHub Actions.

### 1. Secrets do Repositório

Em `Settings → Secrets and variables → Actions`, adicione:

| Secret | Descrição |
|--------|-----------|
| `EMAIL_REMETENTE` | Endereço que envia os alertas |
| `EMAIL_SENHA` | App Password do Gmail (gerada com 2FA ativo) |
| `EMAIL_SLACK_DESTINATARIO` | Destino dos alertas (e-mail ou integração Slack/Teams) |
| `SHEETS_WEBHOOK_URL` | URL do webhook do Google Sheets (opcional) |

> Para Gmail: gere uma [Senha de App](https://myaccount.google.com/apppasswords) com autenticação de dois fatores ativada.

### 2. Execução Automática

O workflow `.github/workflows/main.yml` está configurado para:
- **Cron diário** às 10h UTC (07h Brasília)
- **Disparo manual** via `workflow_dispatch` na aba Actions
- **Persistência do banco SQLite** via cache + artifact (fallback de até 90 dias)
- **Playwright/Chromium** instalado automaticamente no runner

### 3. Execução Manual via GitHub

1. Vá na aba **Actions** do repositório
2. Selecione o workflow `MAST v1 — Monitoramento Automatizado de Sistemas e Tribunais`
3. Clique em **Run workflow**

---

## 💻 Execução Local

```bash
# 1. Clone e entre na pasta
git clone <url-do-repositorio>
cd noticias_alertas_2FA/v1

# 2. Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Instale o Chromium para o Playwright
python -m playwright install chromium --with-deps

# 5. Configure as variáveis de ambiente
export EMAIL_REMETENTE="seu@email.com"
export EMAIL_SENHA="sua_app_password"
export EMAIL_SLACK_DESTINATARIO="destino@email.com"
export SHEETS_WEBHOOK_URL="https://..."   # opcional

# 6. Execute
PYTHONPATH=. python main.py
```

---

## 🧪 Testes

```bash
cd v1
pytest tests/ -v
```

**1398 testes** cobrindo parsers, filtros, banco de dados e geração de relatórios.

Principais suítes:

| Arquivo | Cobertura |
|---------|-----------|
| `test_scraper_direto.py` | Parsers multi-CMS, estratégias S1–S5, `_limpar_data_titulo`, deduplicação |
| `test_filter.py` | Motor de palavras-chave, normalização unicode, `_RE_PURE_DATE` |
| `test_database.py` | Persistência SQLite, controle de duplicatas |
| `test_csv_generator.py` | Geração e formatação do CSV de relatório |

---

## 🔍 Scripts de Diagnóstico

### `diagnostico_fase3.py`
Testa todas as 104 fontes da Fase 3 e gera um relatório `diagnostico_fase3_YYYY-MM-DD.csv`:

```bash
cd v1
python diagnostico_fase3.py
```

Saída por fonte: `✅ OK` / `⚠️ ZERO` / `❌ ERRO` / `⏭️ PULADO`

### `inspecionar_zeros.py`
Inspeciona a estrutura HTML de fontes com ZERO/ERRO para identificar qual seletor de área foi escolhido e por que o parser não extraiu itens:

```bash
# Edite ALVOS no início do script para as siglas desejadas
cd v1
python inspecionar_zeros.py
```

---

## ⚙️ Customização

Toda a lógica de filtragem da Fase 1 é controlada em **`config/settings.py`**:

| Configuração | Função |
|---|---|
| `TERMOS_FORTES_TI` | Termos simples que acionam o alerta (ex.: `MFA`, `PJe`, `indisponível`) |
| `TERMOS_COMPOSTOS` | Expressões compostas (ex.: `autenticação em dois fatores`) |
| `TERMOS_BLOQUEADOS` | Palavras que descartam a notícia (ex.: `concurso`, `eleição`) |
| `DIAS_JANELA` | Janela de tempo para busca de notícias (padrão: 2 dias) |
| `CSV_LIMITE_REGISTROS` | Limite de registros no relatório CSV |

Para **adicionar novas fontes** na Fase 3, edite a lista `FONTES` em `core/scraper_direto.py` seguindo o padrão documentado no cabeçalho do arquivo.

---

## 📄 Licença

Este projeto está licenciado sob a [MIT License](https://opensource.org/licenses/MIT).

---

*Desenvolvido por [Jusbrasil](https://www.jusbrasil.com.br) — Foco em Cibersegurança, Threat Intelligence e SRE para infraestruturas críticas do Judiciário Brasileiro.*
