# MAST — Monitoramento Automatizado de Sistemas e Tribunais

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-success.svg)](https://github.com/features/actions)
[![Testes](https://img.shields.io/badge/testes-1398%20passando-brightgreen.svg)](#-testes)
[![Fontes Fase 3](https://img.shields.io/badge/fontes-104%20tribunais-orange.svg)](#-fase-3--notícias-expandidas)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Robô de **inteligência de fontes abertas (OSINT)** desenvolvido em Python para monitorar, filtrar e alertar sobre indisponibilidades de sistemas, ciberataques, novas portarias e notícias de TI de **mais de 100 fontes do Poder Judiciário Brasileiro**.

O MAST executa diariamente via GitHub Actions (10h UTC), consolida notícias de três pipelines independentes e envia um **e-mail HTML categorizado por grupo de tribunal**, com relatórios **CSV** e **PDF** anexados. Todos os itens coletados (antes do filtro) são exportados para o **Google Sheets** como trilha de auditoria completa.

---

## Índice

- [Como Funciona](#-como-funciona)
- [Fluxo de Execução](#-fluxo-de-execução)
- [Google Sheets — Auditoria Bruta](#-google-sheets--auditoria-bruta)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Grupos e Fontes Monitoradas](#-grupos-e-fontes-monitoradas)
- [Tecnologias](#-tecnologias)
- [Configuração e Deploy](#-configuração-e-deploy)
- [Execução Local](#-execução-local)
- [Testes](#-testes)
- [Scripts de Diagnóstico](#-scripts-de-diagnóstico)

---

## Como Funciona

O MAST opera em **três fases sequenciais** a cada execução. Todas as fases alimentam a lista `noticias_brutas` com os itens coletados **antes de qualquer filtro**, que depois é enviada ao Google Sheets. Cada item bruto também tem o conteúdo do artigo buscado para enriquecer a auditoria.

### Fase 1 — Scraper RSS (Google News)

Busca notícias dos últimos 2 dias cruzando siglas de tribunais com grupos temáticos de palavras-chave de TI/SRE via Google News RSS.

- **Grupos temáticos:** `sistemas_judiciais` (PJe, eproc, projudi, eSAJ, PDPJ), `autenticacao_seguranca` (2FA, MFA, token, SSO, WAF), `incidentes` (ciberataque, ransomware, instabilidade, fora do ar), `normativos` (portaria nº 140, resolução nº 335, certificado digital)
- **Fetch via `requests` com browser User-Agent** — evita bloqueio do Google News ao User-Agent padrão do feedparser
- **Guarda contra páginas de sistema**: descarta entradas onde fonte é domínio puro (ex: `prd.tjrj.pje.jus.br`) e título bate em tela de sistema genérica
- Após coleta, busca o conteúdo do artigo (`buscar_conteudo_artigo`) para cada item e armazena em `conteudo_artigo`

### Fase 2 — Scraper Direto (Portais Oficiais)

Acessa diretamente as páginas de notícias/indisponibilidade de fontes do Judiciário (STF, STJ, TJs, TRFs, TRTs, TREs) para capturar alertas que ainda não chegaram ao Google News.

- Suporta páginas estáticas (`requests`) e dinâmicas (`Playwright/Chromium`)
- Após coleta e avaliação, busca o conteúdo do artigo para **todos** os itens
- **Fase 4 embutida:** quando `avaliar_noticia()` retorna `irrelevante` por `Sem Termos TI`, o conteúdo já buscado é usado para uma segunda avaliação. Itens aprovados nesta segunda rodada têm motivo sufixado com `(Conteúdo Artigo)`

### Fase 3 — Notícias Expandidas (104 Fontes)

Varre diretamente as seções de notícias e normativos de 104 fontes organizadas por grupo de tribunal.

- Parser genérico multi-CMS (Liferay, Drupal, WordPress, portais JSF, CMSs customizados)
- Retorna dicionário `{grupo: [itens]}` pronto para o relatório de e-mail
- Após coleta, busca o conteúdo do artigo para cada item antes de enviar ao Sheets

### Consolidação e Notificação

As três fases são unificadas em um único relatório por categoria de tribunal. Itens de **Indisponibilidade** recebem destaque visual no e-mail. O relatório é enviado com anexos **CSV** e **PDF**.

---

## Fluxo de Execução

```
main.py
  │
  ├── 1. init_db()
  │        └── Cria tabelas SQLite (banco_scraper, banco_filter)
  │
  ├── 2. buscar_noticias_semanais(brutas)       [Fase 1 — RSS]
  │        ├── requests + browser UA → feedparser
  │        ├── avaliar_noticia(título, resumo)
  │        └── buscar_conteudo_artigo(link) → bruta["conteudo_artigo"]
  │
  ├── 3. buscar_noticias_direto(brutas)         [Fase 2 — Scraper Direto]
  │        ├── fetch_page() / Playwright
  │        ├── avaliar_noticia(título, resumo)
  │        ├── buscar_conteudo_artigo(link) → bruta["conteudo_artigo"]
  │        └── Fase 4: reavalia com conteúdo se status=irrelevante/Sem Termos TI
  │
  ├── 4. buscar_noticias_fontes(brutas)         [Fase 3 — 104 Fontes]
  │        ├── parser multi-CMS por fonte
  │        ├── avaliar_noticia(título, resumo)
  │        └── buscar_conteudo_artigo(link) → bruta["conteudo_artigo"]
  │
  ├── 5. Deduplicação (Fases 1+2)
  │        ├── por link exato
  │        └── por título normalizado (cross-run)
  │
  ├── 6. Consolidação por grupo
  │        └── {grupo: [itens]} — Fases 1+2+3 unificadas
  │
  ├── 7. gerar_csv_relatorio()    → relatório auditoria (banco_filter)
  ├── 8. gerar_pdf_relatorio()    → mesmo conteúdo em PDF
  │
  ├── 9. gerar_corpos_email()     → HTML + texto categorizados
  ├── 10. enviar_email()          → SMTP com CSV e PDF anexados
  │
  └── 11. enviar_para_sheets()    → noticias_brutas (PRÉ-filtro, todas as 3 fases)
```

> **Ordem garantida:** `brutas.append()` sempre ocorre **antes** de `avaliar_noticia()`. O Sheets recebe todos os itens coletados — incluindo os que serão bloqueados, irrelevantes ou repetidos — como trilha de auditoria completa.

---

## Google Sheets — Auditoria Bruta

O MAST envia **todos os itens coletados antes do filtro** para uma planilha via webhook do Google Apps Script. Isso permite auditar o que foi coletado em cada run, independente do resultado do filtro.

### Colunas da planilha (9 colunas)

| # | Coluna | Descrição |
|---|--------|-----------|
| 1 | **Titulo** | Título da notícia |
| 2 | **Link** | URL original do artigo |
| 3 | **Data Publicacao** | Data de publicação no veículo |
| 4 | **Fonte** | Nome da fonte (ex: TJSP, Google News) |
| 5 | **Resumo** | Resumo/excerpt extraído |
| 6 | **Termo Buscado** | Grupo temático ou termo que gerou o item |
| 7 | **Origem** | `RSS` · `Direto` · `Fontes` |
| 8 | **Data Captura** | Timestamp do run (ISO 8601) |
| 9 | **Conteudo Artigo** | Primeiros 600 chars do corpo do artigo (todas as fases) |

### Configuração do webhook

O Apps Script (`apps_script.js`) valida a requisição via secret e insere as linhas na planilha ativa. Para configurar:

1. Crie um Apps Script vinculado à planilha de destino
2. Cole o conteúdo de `v1/apps_script.js`
3. Em **Propriedades do script**, adicione:
   - `WEBHOOK_SECRET` — string secreta (mesma no GitHub Secret `SHEETS_WEBHOOK_SECRET`)
   - `SPREADSHEET_ID` — ID da planilha (entre `/d/` e `/edit` na URL)
4. Publique como **Web App** (acesso: qualquer pessoa)
5. Adicione a URL gerada como `SHEETS_WEBHOOK_URL` nos Secrets do GitHub

---

## Estrutura do Projeto

```
v1/
├── main.py                      # Orquestrador principal (Fases 1, 2, 3)
│
├── config/
│   └── settings.py              # Constantes globais, palavras-chave, URLs, limites
│
├── core/
│   ├── scraper.py               # Fase 1 — RSS/Google News
│   ├── scraper_direto.py        # Fases 2, 3 e 4 — scraper direto + 104 parsers
│   ├── filter.py                # Motor de filtro: regex, normalização, deduplicação
│   ├── notifier.py              # Geração de HTML/texto e envio de e-mail SMTP
│   ├── database.py              # SQLite — persistência e controle de duplicatas
│   ├── csv_generator.py         # Geração do relatório CSV
│   ├── pdf_generator.py         # Geração do relatório PDF
│   └── sheets_writer.py         # Exportação para Google Sheets via webhook
│
├── apps_script.js               # Google Apps Script — webhook receptor do Sheets
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

## Grupos e Fontes Monitoradas

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

### Fontes marcadas como PULADO (skip)

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

## Tecnologias

| Biblioteca | Uso |
|---|---|
| `requests` / `urllib3` | Fetch HTTP — portais estáticos e feeds RSS (com browser User-Agent) |
| `beautifulsoup4` + `lxml` | Parsing HTML multi-CMS |
| `playwright` (Chromium) | Renderização de portais JS-only (SPA, Liferay, etc.) |
| `feedparser` | Parsing local de feeds RSS/Atom (recebe bytes do requests) |
| `sqlite3` | Persistência e deduplicação cross-run |
| `smtplib` / `email.mime` | Geração de e-mail HTML responsivo + envio SMTP |
| `reportlab` | Geração de relatório PDF |
| `re` / `unicodedata` | Normalização unicode e filtragem por regex |
| `pytest` | 1398 testes automatizados |
| **GitHub Actions** | CI/CD, cron job diário, cache SQLite persistente |

**Python 3.12+** é necessário.

---

## Configuração e Deploy

O MAST foi projetado para rodar **sem custos** no GitHub Actions.

### Secrets do Repositório

Em `Settings → Secrets and variables → Actions`, adicione:

| Secret | Descrição |
|--------|-----------|
| `EMAIL_REMETENTE` | Endereço que envia os alertas |
| `EMAIL_SENHA` | App Password do Gmail (gerada com 2FA ativo) |
| `EMAIL_SLACK_DESTINATARIO` | Destino dos alertas (e-mail ou integração Slack/Teams) |
| `SHEETS_WEBHOOK_URL` | URL do webhook do Google Apps Script |
| `SHEETS_WEBHOOK_SECRET` | Secret para autenticação do webhook |

> Para Gmail: gere uma [Senha de App](https://myaccount.google.com/apppasswords) com autenticação de dois fatores ativada.

### Execução Automática

O workflow `.github/workflows/main.yml` está configurado para:
- **Cron diário** às 10h UTC (07h Brasília)
- **Disparo manual** via `workflow_dispatch` na aba Actions
- **Persistência do banco SQLite** via cache + artifact (fallback de até 90 dias)
- **Playwright/Chromium** instalado automaticamente no runner

### Execução Manual via GitHub

1. Vá na aba **Actions** do repositório
2. Selecione o workflow `MAST v1 — Monitoramento Automatizado de Sistemas e Tribunais`
3. Clique em **Run workflow**

---

## Execução Local

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
export SHEETS_WEBHOOK_URL="https://script.google.com/..."
export SHEETS_WEBHOOK_SECRET="seu_secret"

# 6. Execute
PYTHONPATH=. python main.py
```

---

## Testes

```bash
cd v1
pytest tests/ -v
```

**1398 testes** cobrindo parsers, filtros, banco de dados e geração de relatórios.

| Arquivo | Cobertura |
|---------|-----------|
| `test_scraper_direto.py` | Parsers multi-CMS, estratégias S1–S5, `_limpar_data_titulo`, deduplicação |
| `test_filter.py` | Motor de palavras-chave, normalização unicode, `_RE_PURE_DATE` |
| `test_database.py` | Persistência SQLite, controle de duplicatas |
| `test_csv_generator.py` | Geração e formatação do CSV de relatório |

---

## Scripts de Diagnóstico

### `diagnostico_fase3.py`

Testa todas as 104 fontes da Fase 3 e gera um relatório `diagnostico_fase3_YYYY-MM-DD.csv`:

```bash
cd v1
python diagnostico_fase3.py
```

Saída por fonte: `OK` / `ZERO` / `ERRO` / `PULADO`

### `inspecionar_zeros.py`

Inspeciona a estrutura HTML de fontes com ZERO/ERRO para identificar qual seletor de área foi escolhido e por que o parser não extraiu itens:

```bash
# Edite ALVOS no início do script para as siglas desejadas
cd v1
python inspecionar_zeros.py
```

---

## Customização

Toda a lógica de filtragem é controlada em **`config/settings.py`**:

| Configuração | Função |
|---|---|
| `TERMOS_FORTES_TI` | Termos simples que acionam o alerta (ex.: `MFA`, `PJe`, `indisponível`) |
| `TERMOS_COMPOSTOS` | Expressões compostas (ex.: `autenticação em dois fatores`) |
| `TERMOS_BLOQUEADOS` | Palavras que descartam a notícia (ex.: `concurso`, `eleição`) |
| `DIAS_JANELA` | Janela de tempo para busca de notícias (padrão: 2 dias) |
| `CSV_LIMITE_REGISTROS` | Limite de registros no relatório CSV |

Para **adicionar novas fontes** na Fase 3, edite a lista `FONTES` em `core/scraper_direto.py` seguindo o padrão documentado no cabeçalho do arquivo.

---

## Licença

Este projeto está licenciado sob a [MIT License](https://opensource.org/licenses/MIT).

---

*Desenvolvido por [Jusbrasil](https://www.jusbrasil.com.br) — Foco em Cibersegurança, Threat Intelligence e SRE para infraestruturas críticas do Judiciário Brasileiro.*
