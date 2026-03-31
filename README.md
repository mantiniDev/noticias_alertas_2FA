# 🏛️ MAST — Monitoramento Automatizado de Sistemas e Tribunais

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/Build-Automated-success.svg)](https://github.com/mantiniDev/noticias_alertas_2FA/actions)

> Um robô de **OSINT (Open Source Intelligence)** e **Threat Intelligence** construído em Python, focado em monitorar, filtrar e alertar sobre a disponibilidade, segurança e atualizações dos sistemas do Poder Judiciário Brasileiro.

O **MAST** vigia continuamente a internet à procura de incidentes de TI, indisponibilidades de sistemas (PJe, eproc, e-SAJ, Projudi), ciberataques, implementação de MFA/2FA e novas portarias em mais de **60 tribunais brasileiros** (STF, STJ, TJs, TRFs, TRTs e TREs).

---

## ✨ Como Funciona

O MAST opera através de um motor de varredura modular baseado no ecossistema de indexação de notícias, com foco em alta precisão e baixa manutenção:

- **Busca Focada e Dinâmica:** Lê a base interna de tribunais, extrai os domínios (ex: `tjsp.jus.br`) e cria queries avançadas no Google News em lotes, evitando bloqueios por rate limit (Erro 400).
- **Filtro de Malha Fina (Regex):** Cada notícia passa por uma validação com expressões regulares que aceita plurais automaticamente e ignora palavras-chave de TI inseridas no meio de outras palavras (ex: `SSO` dentro de `processo`).
- **Bloqueio de Falsos Positivos:** Uma *Blacklist* interna descarta notícias sobre RH, concursos, orçamento ou eleições — conteúdo que costuma poluir feeds do judiciário.
- **Smart Links Oficiais:** Ao detectar uma notícia sobre um tribunal específico, o robô cruza com a base interna e anexa ao alerta um link direto para a página de status/certidão oficial daquele tribunal.
- **Arquivamento em Banco de Dados:** Cada notícia processada é persistida em um banco SQLite local (`mast_dados.db`), garantindo rastreabilidade e deduplicação entre execuções.
- **Relatório em CSV:** Ao fim de cada execução, um relatório `.csv` com os últimos 100 registros novos é gerado automaticamente e anexado ao e-mail de alerta.

---

## 📁 Estrutura do Projeto

```
ops-credenciais-mast/
│
├── .github/
│   └── workflows/          # Pipeline CI/CD com GitHub Actions (cron job diário)
│
├── config/
│   └── settings.py         # Constantes, URLs dos tribunais e listas de palavras-chave
│
├── core/
│   ├── scraper.py          # Extração de domínios, busca no Google News e RSS
│   ├── filter.py           # Lógica de malha fina (Regex, normalização de texto)
│   ├── notifier.py         # Geração de relatórios HTML e integração SMTP
│   ├── database.py         # Inicialização do SQLite e queries de leitura/escrita
│   └── csv_generator.py    # Geração do relatório CSV anexado ao e-mail
│
├── main.py                 # Orquestrador principal da aplicação
└── mast_dados.db           # Banco de dados SQLite (gerado automaticamente)
```

---

## 🔄 Fluxo de Execução (`main.py`)

```
1. init_db()                    → Inicializa os bancos de dados (SQLite)
2. buscar_noticias_semanais()   → Scraper busca, filtra e arquiva notícias; retorna apenas as "novas"
3. buscar_dados_para_csv()      → Lê os últimos 100 registros novos do banco
4. gerar_csv_relatorio()        → Gera o arquivo CSV de relatório
5. gerar_corpos_email()         → Monta o corpo do e-mail em texto e HTML
6. enviar_email()               → Envia o alerta com o CSV anexado
```

---

## 🛠️ Tecnologias Utilizadas

| Biblioteca | Uso |
|---|---|
| `feedparser` | Leitura, extração e parsing de RSS/Atom |
| `urllib` / `urllib3` | Codificação de queries de busca |
| `re` / `unicodedata` | Expressões regulares e normalização de texto (remoção de acentos) |
| `sqlite3` | Persistência local de notícias e controle de duplicatas |
| `smtplib` / `email.mime` | Geração de relatórios HTML responsivos e envio de e-mail |
| `csv` | Geração de relatório tabular para anexo |
| **GitHub Actions** | Automação CI/CD, cron jobs e ambiente serverless gratuito |

**Python 3.12+** é necessário.

---

## 🚀 Como Configurar e Rodar

O projeto foi desenhado para rodar nativamente e **sem custos** no **GitHub Actions**.

### 1. Configurar os Secrets do Repositório

Vá em `Settings` → `Secrets and variables` → `Actions` → `New repository secret` e adicione:

| Secret | Descrição |
|---|---|
| `EMAIL_REMETENTE` | E-mail que enviará os relatórios automatizados |
| `EMAIL_SENHA` | App Password (Senha de Aplicativo) do provedor de e-mail |
| `EMAIL_DESTINATARIO` | E-mail (ou endereço de integração Slack/Teams) que receberá os alertas |

> **Dica:** Para Gmail, gere uma [Senha de App](https://myaccount.google.com/apppasswords) com autenticação de dois fatores ativada.

### 2. Execução Automática

O workflow já está configurado para rodar diariamente via cron job, chamando o `main.py` com o `PYTHONPATH` ajustado. Nenhuma configuração adicional é necessária após os secrets estarem definidos.

### 3. Execução Manual

1. Vá na aba **Actions** do repositório.
2. Selecione o workflow de monitoramento.
3. Clique em **Run workflow**.

### 4. Execução Local (opcional)

```bash
git clone https://github.com/mantiniDev/noticias_alertas_2FA.git
cd noticias_alertas_2FA

pip install feedparser

# Defina as variáveis de ambiente
export EMAIL_REMETENTE="seu@email.com"
export EMAIL_SENHA="sua_app_password"
export EMAIL_DESTINATARIO="destino@email.com"

python main.py
```

---

## 🧠 Customização

Toda a lógica de filtragem é controlada por listas em **`config/settings.py`** — sem necessidade de alterar código.

| Lista | Função |
|---|---|
| `TERMOS_FORTES_TI` | Termos simples que acionam o alerta (ex: `MFA`, `PJe`, `indisponível`) |
| `TERMOS_COMPOSTOS` | Expressões compostas que acionam o alerta (ex: `autenticação em dois fatores`) |
| `TERMOS_BLOQUEADOS` | Palavras que descartam a notícia instantaneamente (ex: `concurso`, `eleição`) |

---

## 🚧 Desafios de Engenharia Resolvidos

- **Ruído Administrativo:** Tribunais publicam muito conteúdo não-técnico. A `TERMOS_BLOQUEADOS` aliada a regex com `\b` (word boundary) bloqueia notícias fora do escopo de TI.
- **Rate Limits (Erro 400):** Pesquisar mais de 60 domínios simultaneamente gera URLs muito longas. O scraper divide os domínios em blocos menores para evitar o erro.
- **Plurais e Acentos:** O motor usa regex flexível com `(s|es)?` e a biblioteca `unicodedata` para normalizar acentos antes da validação (`manutencao` == `manutenção`).
- **Deduplicação:** O banco SQLite registra cada notícia já vista, garantindo que o mesmo item não gere alertas repetidos em execuções futuras.

---

## 🗺️ Roadmap

- [ ] **Motor Secundário (Scraper Direto):** Varredura direta de páginas de indisponibilidade oficiais e painéis de aviso, sem depender de indexadores de busca.
- [ ] **Filtro Anti-Ruído Estrutural:** Uso do `BeautifulSoup` para ignorar menus de navegação (`<nav>`) e rodapés antes da análise de conteúdo.
- [ ] **Integração Telegram:** Leitura de canais oficiais como *PJe News* (`t.me/s/pjenews`).
- [ ] **Dashboard Web:** Painel de visualização histórica das notícias arquivadas no SQLite.

---

*[Jusbrasil](https://www.jusbrasil.com.br) — desenvolvido por [mantiniDev](https://github.com/mantiniDev) · Focado em Cibersegurança, Threat Intelligence e SRE para infraestruturas críticas.*
