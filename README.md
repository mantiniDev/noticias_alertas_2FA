# 🏛️ MAST — Monitoramento Automatizado de Sistemas e Tribunais

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/Build-Automated-success.svg)](https://github.com/mantiniDev/noticias_alertas_2FA/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Um robô de **OSINT (Open Source Intelligence)** e **Threat Intelligence** construído em Python, focado em monitorar, filtrar e alertar sobre a disponibilidade, segurança e atualizações dos sistemas do Poder Judiciário Brasileiro.

O **MAST** vigia continuamente a internet à procura de incidentes de TI, indisponibilidades de sistemas (PJe, eproc, e-SAJ, Projudi), ciberataques, implementação de MFA/2FA e novas portarias em mais de **60 tribunais brasileiros** (STF, STJ, TJs, TRFs, TRTs e TREs).

---

## ✨ Como Funciona

O MAST opera em **cinco fases sequenciais** a cada execução:

### Fase 1 — Mapeamento Dinâmico de Domínios
Em vez de uma busca genérica, o script lê sua própria base de dados e extrai a URL raiz de cada um dos **60+ tribunais e portais cadastrados** (STF, STJ, TJs, TRFs, TRTs, TREs), gerando filtros de busca dinâmicos e sempre atualizados.

### Fase 2 — Varredura de Rede Larga
Cruza a sigla de cada tribunal com uma lista de palavras-chave de SRE e Segurança (`PJe`, `instabilidade`, `MFA`, `ciberataque`, `nuvem`, etc.), puxando qualquer notícia oficial dos **últimos 2 dias** via Google News RSS. As queries são agrupadas em lotes para evitar bloqueios por rate limit (Erro 400).

### Fase 3 — Busca de Precisão (Frases Exatas)
Realiza buscas superespecíficas com frases exatas (ex.: `"SRE (Site Reliability Engineering)"`, `"Desafio Captcha"`, `"WAF"`) para capturar comunicados técnicos que possam escapar da rede larga da Fase 2.

### Fase 4 — Malha Fina (Motor de Inspeção)
Para cada notícia encontrada, título e resumo passam por um "Raio-X" em três etapas:

1. **Normalização Unicode** — remove acentos e converte para lowercase, uniformizando variações ortográficas (`manutencao` == `manutenção`).
2. **Filtro de Bloqueio via Regex** — descarta termos de RH/administrativo como `estágio`, `eleição` e `orçamento`, exceto quando o título é explicitamente sobre TI.
3. **Validação com Isolamento de Palavra** — usa `\b` (word boundary) para impedir que siglas de TI validem palavras maiores (ex.: `SSO` não valida `processo`). Plurais são aceitos automaticamente via regex `(s|es)?`.

### Fase Final — Enriquecimento e Notificação
Unifica os dados validados, gera um **relatório HTML responsivo** e um **anexo CSV** com os últimos 100 registros, enviados via SMTP diretamente ao canal do Slack. Credenciais gerenciadas via GitHub Secrets.

---

## 📁 Estrutura do Projeto

```
noticias_alertas_2FA/
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

## 📄 Licença

Este projeto está licenciado sob a [MIT License](https://opensource.org/licenses/MIT).

---

*[Jusbrasil](https://www.jusbrasil.com.br) — desenvolvido por [mantiniDev](https://github.com/mantiniDev) · Focado em Cibersegurança, Threat Intelligence e SRE para infraestruturas críticas.*
