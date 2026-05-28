# core/scraper_direto.py
"""
Motor secundário do MAST — lista unificada de fontes por tribunal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FONTES — Lista unificada (97 entradas, 2 pipelines)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Cada entrada representa um tribunal/sistema e contém obrigatoriamente:
    alertas  : dict | None  — fonte de indisponibilidade
    noticias : list[dict]   — lista de fontes de notícias/normativos

  Listas planas derivadas:
    TRIBUNAIS_DIRETO — 61 entradas de alertas → buscar_noticias_direto()
    FONTES_NOTICIAS  — 104 entradas de noticias → buscar_noticias_fontes()
                       agrupadas por: Sistemas/CNJ, Superiores, TJEs, TRFs, TRTs

Integração:
  - Usa verificar_status_noticia() e salvar_auditoria() do database.py
    para deduplicação e persistência — mesma lógica do scraper RSS.
  - Usa avaliar_noticia() do filter.py para classificar cada item.
  - Ambas retornam listas no mesmo formato base, prontas para main.py.
"""

import logging
import re
import time
import warnings
from datetime import datetime, timezone

import requests
import urllib3
from bs4 import BeautifulSoup

from config.settings import REQUEST_TIMEOUT, PLAYWRIGHT_TIMEOUT, MAX_ITEMS, DIAS_JANELA
from core.filter import avaliar_noticia, normalizar_titulo_chave
from core.database import verificar_status_noticia, verificar_titulo_chave, salvar_auditoria

# Suprime aviso de SSL apenas quando o fallback verify=False é acionado explicitamente
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes locais de apresentação HTTP
# ---------------------------------------------------------------------------

# Regex para detectar títulos que são APENAS datas/timestamps sem conteúdo textual.
# Usada pelo parse_generic_table para evitar usar uma data como título da notícia.
# Exemplos cobertos: "07.05.2026", "09/03/2026 das 06:00 até ...", "Janeiro"
_RE_PURE_DATE = re.compile(
    r'^\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4}'          # "07.05.2026", "09/03/2026 ..."
    r'|^\d{4}[/\.\-]\d{1,2}[/\.\-]\d{1,2}'            # "2026-05-09"
    r'|^(janeiro|fevereiro|mar[cç]o|abril|maio|junho'   # nomes de mês isolados
    r'|julho|agosto|setembro|outubro|novembro|dezembro)$',
    re.IGNORECASE,
)

# Prefixo de data em títulos de notícias de tribunais.
# Muitos portais incluem a data no texto do link: "28/05/2026 - TJSP participa..."
# Esse padrão remove apenas o prefixo; _RE_PURE_DATE continua rejeitando títulos
# que são SOMENTE datas (sem texto adicional).
_RE_TITULO_DATA_PREFIX = re.compile(
    # "28/05/2026 -" / "27/05/2026 18h00" / "27/05/2026 - 13:32"
    r'^\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4}'
    r'(?:[\s\-–—]+(?:\d{1,2}[hH]\d{0,2}|\d{1,2}:\d{2}))?'
    r'[\s\-–—]*'
    r'|^\d{1,2}\s+de\s+\w+\s+de\s+\d{4}[\s\-–—:]*'   # "27 de maio de 2026 -"
    r'|^\d{1,2}\s+\w{3}[\s\.\-–—:]*',                   # "26 mai -"
    re.IGNORECASE,
)


def _limpar_data_titulo(titulo: str) -> str:
    """Remove prefixo de data do início de um título de notícia.

    Exemplos:
      "28/05/2026 - TJSP participa..."  → "TJSP participa..."
      "27/05/2026 18h00 TJMG…"         → "TJMG…"
      "27 de maio de 2026 TJAC inova…" → "TJAC inova…"
      "26 mai TRT-8 Presente…"         → "TRT-8 Presente…"

    Mantém o título original se o resultado limpo ficar com menos de 10 chars
    (evita apagar título que seja APENAS uma data — esse caso vai para _RE_PURE_DATE).
    """
    if not titulo:
        return ""
    clean = _RE_TITULO_DATA_PREFIX.sub("", titulo).strip()
    return clean if len(clean) >= 10 else titulo


# Tags HTML que representam navegação/acessibilidade — jamais contêm notícias reais.
_NAV_TAGS = "nav, header, footer, .menu, .navbar, .breadcrumb, .lfr-nav, " \
            ".taglib-navigation, aside, .accessibility, .vlibras, " \
            ".skip-nav, #accessibility-tools"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ===========================================================================
# FONTES — Lista unificada de todas as fontes de monitoramento
#
# Cada entrada representa um tribunal/sistema monitorado.
# Campos obrigatórios: acronym, nome, grupo, alertas, noticias
#
# alertas : dict | None
#   Fonte de INDISPONIBILIDADE do tribunal.
#   None quando não há página pública de indisponibilidade.
#   Campos obrigatórios dentro de alertas: url, parser, base_url
#   Campos opcionais: nome, tipo, force_playwright, wait_selector, extra_wait
#
# noticias : list[dict]
#   Lista de fontes de NOTÍCIAS/NORMATIVOS do tribunal.
#   Cada item precisa de: nome, url, parser, base_url, tipo
#   O acronym do item herda do parent, mas pode ser sobrescrito com acronym local.
#
# Listas derivadas (usadas pelos dois pipelines e pelos testes):
#   TRIBUNAIS_DIRETO = lista plana de entradas de alertas (63 fontes)
#   FONTES_NOTICIAS  = lista plana de todas as entradas de noticias (104 fontes)
# ===========================================================================
FONTES: list[dict] = [

    # ── Sistemas e CNJ ────────────────────────────────────────────────────────
    {
        "acronym": "PJeNews",
        "nome": "PJe News (Telegram)",
        "grupo": "Sistemas-CNJ",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "Telegram - PJe News",
                "url": "https://t.me/s/pjenews",
                "parser": "telegram",
                "base_url": "https://t.me",
                "tipo": "Notícias PJe",
                "force_playwright": True,
                "wait_selector": ".tgme_widget_message_wrap",
                "extra_wait": 3,
            },
        ],
    },
    {
        "acronym": "PJeDocs",
        "nome": "PJe Legacy Docs",
        "grupo": "Sistemas-CNJ",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "PJe Legacy - Notas da Versão",
                "url": "https://docs.pje.jus.br/servicos-negociais/servico-pje-legacy/notas-da-versao",
                "parser": "generic_news",
                "base_url": "https://docs.pje.jus.br",
                "tipo": "Release Notes",
            },
        ],
    },
    {
        "acronym": "CNJ-PDPJ",
        "nome": "CNJ - PDPJ-Br",
        "grupo": "Sistemas-CNJ",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "CNJ - Notícias PDPJ-Br",
                "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/plataforma-digital-do-poder-judiciario-brasileiro-pdpj-br/noticias/",
                "parser": "generic_news",
                "base_url": "https://www.cnj.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "CNJ-J40",
        "nome": "CNJ - Justiça 4.0",
        "grupo": "Sistemas-CNJ",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "CNJ - Notícias Justiça 4.0",
                "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/justica-4-0/noticias/",
                "parser": "generic_news",
                "base_url": "https://www.cnj.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "CNJ-Norm",
        "nome": "CNJ - Atos Normativos",
        "grupo": "Sistemas-CNJ",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "CNJ - Atos Normativos",
                "url": "https://www.cnj.jus.br/atos_normativos/",
                "parser": "generic_news",
                "base_url": "https://www.cnj.jus.br",
                "tipo": "Normativos",
                "skip": True,
                "skip_reason": "página de busca/formulário — não é listagem estática",
            },
        ],
    },

    # ── Tribunais Superiores e Conselhos ──────────────────────────────────────
    {
        "acronym": "STF",
        "nome": "Supremo Tribunal Federal",
        "grupo": "Tribunais-Superiores",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "STF - Notícias",
                "url": "https://noticias.stf.jus.br/",
                "parser": "generic_news",
                "base_url": "https://noticias.stf.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "STJ",
        "nome": "Superior Tribunal de Justiça",
        "grupo": "Tribunais-Superiores",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "STJ - RSS Notícias",
                "url": "https://res.stj.jus.br/hrestp-c-portalp/RSS.xml",
                "parser": "rss",
                "base_url": "https://www.stj.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TST",
        "nome": "Tribunal Superior do Trabalho",
        "grupo": "Tribunais-Superiores",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TST - Notícias",
                "url": "https://www.tst.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tst.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "CSJT",
        "nome": "Conselho Superior da Justiça do Trabalho",
        "grupo": "Tribunais-Superiores",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "acronym": "CSJT-Norm",
                "nome": "CSJT - Normativos",
                "url": "https://www.csjt.jus.br/web/csjt/normativos",
                "parser": "generic_news",
                "base_url": "https://www.csjt.jus.br",
                "tipo": "Normativos",
            },
            {
                "acronym": "CSJT-Leg",
                "nome": "CSJT - Legislação e Atos",
                "url": "https://www.csjt.jus.br/web/csjt/legislacao-atos",
                "parser": "generic_news",
                "base_url": "https://www.csjt.jus.br",
                "tipo": "Normativos",
            },
        ],
    },
    {
        "acronym": "TSE",
        "nome": "Tribunal Superior Eleitoral",
        "grupo": "Tribunais-Superiores",
        "principal": False,
        "alertas": {
            "nome": "TSE - Indisponibilidade PJe",
            "url": "https://www.tse.jus.br/servicos-judiciais/processos/processo-judicial-eletronico/indisponibilidade-pje",
            "parser": "generic_news",
            "base_url": "https://www.tse.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TSE - Notícias",
                "url": "https://www.tse.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tse.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "STM",
        "nome": "Superior Tribunal Militar",
        "grupo": "Tribunais-Superiores",
        "principal": False,
        "alertas": {
            "nome": "STM - Indisponibilidade SEI",
            "url": "https://sei.stm.jus.br/modulos/peticionamento/md_pet_usu_ext_indisponibilidade_lista.php?acao_externa=md_pet_usu_ext_indisponibilidade_listar&id_orgao_acesso_externo=0",
            "parser": "generic_table",
            "base_url": "https://sei.stm.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "STM - Notícias",
                "url": "https://www.stm.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.stm.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "CJF",
        "nome": "Conselho da Justiça Federal",
        "grupo": "Tribunais-Superiores",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "CJF - Notícias",
                "url": "https://www.cjf.jus.br/cjf/noticias",
                "parser": "generic_news",
                "base_url": "https://www.cjf.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "CNMP",
        "nome": "Conselho Nacional do Ministério Público",
        "grupo": "Tribunais-Superiores",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "CNMP - Notícias",
                "url": "https://www.cnmp.mp.br/portal/noticias",
                "parser": "generic_news",
                "base_url": "https://www.cnmp.mp.br",
                "tipo": "Notícias",
            },
        ],
    },

    # ── Tribunais de Justiça Estaduais ────────────────────────────────────────
    {
        "acronym": "TJSP",
        "nome": "Tribunal de Justiça de São Paulo",
        "grupo": "Tribunais-Estaduais",
        "principal": True,
        "alertas": {
            "nome": "TJSP - Indisponibilidade",
            "url": "https://www.tjsp.jus.br/Indisponibilidade/Comunicados",
            "parser": "tjsp",
            "base_url": "https://www.tjsp.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "acronym": "TJSP-Eproc",
                "nome": "TJSP - Notícias eproc",
                "url": "https://www.tjsp.jus.br/eproc/Noticias",
                "parser": "tjsp",
                "base_url": "https://www.tjsp.jus.br",
                "tipo": "Notícias eproc",
            },
            {
                "nome": "TJSP - Notícias Tecnologia",
                "url": "https://www.tjsp.jus.br/Noticias?codigoCategoria=14",
                "parser": "generic_news",
                "base_url": "https://www.tjsp.jus.br",
                "tipo": "Notícias",
            },
            {
                "acronym": "TJSP-Prec",
                "nome": "TJSP - Comunicados (Precatórios)",
                "url": "https://www.tjsp.jus.br/Precatorios/Comunicados?tipoDestino=85",
                "parser": "tjsp",
                "base_url": "https://www.tjsp.jus.br",
                "tipo": "Comunicados",
            },
        ],
    },
    {
        "acronym": "TJRS",
        "nome": "Tribunal de Justiça do Rio Grande do Sul",
        "grupo": "Tribunais-Estaduais",
        "principal": True,
        "alertas": None,
        "noticias": [
            {
                "nome": "TJRS - Notícias",
                "url": "https://www.tjrs.jus.br/novo/comunicacao/noticias-do-tjrs/",
                "parser": "generic_news",
                "base_url": "https://www.tjrs.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TJMG",
        "nome": "Tribunal de Justiça de Minas Gerais",
        "grupo": "Tribunais-Estaduais",
        "principal": True,
        "alertas": {
            "nome": "TJMG - Indisponibilidade",
            "url": "https://www.tjmg.jus.br/pje/certidao-de-indisponibilidade/",
            "parser": "tjmg",
            "base_url": "https://www.tjmg.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJMG - Notícias",
                "url": "https://www.tjmg.jus.br/portal-tjmg/noticias/",
                "parser": "generic_news",
                "base_url": "https://www.tjmg.jus.br",
                "tipo": "Notícias",
            },
            {
                "acronym": "TJMG-Norm",
                "nome": "TJMG - Atos Normativos",
                "url": "https://www.tjmg.jus.br/portal-tjmg/atos-normativos/",
                "parser": "tjmg",
                "base_url": "https://www.tjmg.jus.br",
                "tipo": "Normativos",
            },
        ],
    },
    {
        "acronym": "TJPR",
        "nome": "Tribunal de Justiça do Paraná",
        "grupo": "Tribunais-Estaduais",
        "principal": True,
        # TJPR desativou o PJe e usa Projudi como sistema principal
        "alertas": {
            "nome": "TJPR - Indisponibilidade Projudi",
            "url": "https://projudi.tjpr.jus.br/projudi/indisponibilidades.jsp",
            "parser": "projudi",
            "base_url": "https://projudi.tjpr.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJPR - Notícias",
                "url": "https://www.tjpr.jus.br/noticias",
                "parser": "tjpr",
                "base_url": "https://www.tjpr.jus.br",
                "tipo": "Notícias",
            },
            {
                "acronym": "TJPR-Norm",
                "nome": "TJPR - Legislação e Atos Normativos",
                "url": "https://www.tjpr.jus.br/legislacao-atos-normativos",
                "parser": "generic_news",
                "base_url": "https://www.tjpr.jus.br",
                "skip": True,
                "skip_reason": "página de busca/formulário — não é listagem estática",
                "tipo": "Normativos",
            },
        ],
    },
    {
        "acronym": "TJRJ",
        "nome": "Tribunal de Justiça do Rio de Janeiro",
        "grupo": "Tribunais-Estaduais",
        "principal": True,
        "alertas": {
            "nome": "TJRJ - Indisponibilidade",
            "url": "https://www3.tjrj.jus.br/portalservicos/#/modindpub-principal",
            "parser": "generic_table",
            "base_url": "https://www3.tjrj.jus.br",
            "tipo": "Indisponibilidade",
            "force_playwright": True,
            "wait_selector": "table, .indisponibilidade, .card",
            "extra_wait": 4,
        },
        "noticias": [
            {
                "nome": "TJRJ - Notícias",
                "url": "https://www.tjrj.jus.br/web/guest/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjrj.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TJPI",
        "nome": "Tribunal de Justiça do Piauí",
        "grupo": "Tribunais-Estaduais",
        "principal": True,
        "alertas": {
            "nome": "TJPI - Indisponibilidade PJe",
            "url": "https://www.tjpi.jus.br/portaltjpi/pje/indisponibilidade-do-sistema/",
            "parser": "generic_news",
            "base_url": "https://www.tjpi.jus.br",
            "tipo": "Indisponibilidade",
            "skip_playwright": True,
        },
        "noticias": [
            {
                "nome": "TJPI - Notícias",
                "url": "https://www.tjpi.jus.br/portaltjpi/noticias/",
                "parser": "generic_news",
                "base_url": "https://www.tjpi.jus.br",
                "tipo": "Notícias",
                "skip_playwright": True,
            },
        ],
    },
    {
        "acronym": "TJTO",
        "nome": "Tribunal de Justiça do Tocantins",
        "grupo": "Tribunais-Estaduais",
        "principal": True,
        # eproc não tem página pública de indisponibilidade; usa notícias gerais
        "alertas": {
            "nome": "TJTO - Comunicados eproc",
            "url": "https://www.tjto.jus.br/comunicacao/noticias",
            "parser": "generic_news",
            "base_url": "https://www.tjto.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJTO - Notícias",
                "url": "https://www.tjto.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjto.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TJBA",
        "nome": "Tribunal de Justiça da Bahia",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJBA - Indisponibilidade PJe",
            "url": "https://www.tjba.jus.br/portal/aviso-indisponibilidade/",
            "parser": "generic_news",
            "base_url": "https://www.tjba.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJBA - Agência de Notícias",
                "url": "https://www.tjba.jus.br/portal/agencia-de-noticias/",
                "parser": "generic_news",
                "base_url": "https://www.tjba.jus.br",
                "tipo": "Notícias",
            },
        ],
    },

    # TJAC
    {
        "acronym": "TJAC",
        "nome": "Tribunal de Justiça do Acre",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJAC - Indisponibilidade",
            "url": "https://www.tjac.jus.br/indisponibilidade/?tax=grau-1grau",
            "parser": "generic_table",
            "base_url": "https://www.tjac.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJAC - Notícias",
                "url": "https://www.tjac.jus.br/category/noticias/",
                "parser": "generic_news",
                "base_url": "https://www.tjac.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJAL
    {
        "acronym": "TJAL",
        "nome": "Tribunal de Justiça de Alagoas",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJAL - Indisponibilidade",
            "url": "https://www.tjal.jus.br/indisponibilidades",
            "parser": "generic_table",
            "base_url": "https://www.tjal.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJAL - Notícias",
                "url": "https://www.tjal.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjal.jus.br",
                "tipo": "Notícias",
                "force_playwright": True,
            },
        ],
    },
    # TJAP
    {
        "acronym": "TJAP",
        "nome": "Tribunal de Justiça do Amapá",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TJAP - Notícias",
                "url": "https://www.tjap.jus.br/portal/noticias.html",
                "parser": "generic_news",
                "base_url": "https://www.tjap.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJAM
    {
        "acronym": "TJAM",
        "nome": "Tribunal de Justiça do Amazonas",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJAM - Calendário de Indisponibilidade",
            "url": "https://www.tjam.jus.br/index.php/certidoes-de-indisponibilidade",
            "parser": "generic_table",
            "base_url": "https://www.tjam.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJAM - Sala de Imprensa",
                "url": "https://www.tjam.jus.br/index.php/menu/sala-de-imprensa",
                "parser": "generic_news",
                "base_url": "https://www.tjam.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJCE
    {
        "acronym": "TJCE",
        "nome": "Tribunal de Justiça do Ceará",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJCE - Histórico de Indisponibilidade PJe",
            "url": "https://www.tjce.jus.br/pje/historico-de-indisponibilidade/",
            "parser": "generic_table",
            "base_url": "https://www.tjce.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJCE - Notícias",
                "url": "https://www.tjce.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjce.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJDFT
    {
        "acronym": "TJDFT",
        "nome": "Tribunal de Justiça do Distrito Federal e Territórios",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJDFT - Indisponibilidade PJe",
            "url": "https://pje-indisponibilidade.tjdft.jus.br/",
            "parser": "generic_table",
            "base_url": "https://pje-indisponibilidade.tjdft.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJDFT - Notícias",
                "url": "https://www.tjdft.jus.br/institucional/imprensa/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjdft.jus.br",
                "tipo": "Notícias",
                "skip_playwright": True,
            },
        ],
    },
    # TJES
    {
        "acronym": "TJES",
        "nome": "Tribunal de Justiça do Espírito Santo",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJES - Consulta Indisponibilidade PJe",
            "url": "https://www.tjes.jus.br/pje_sla/consulta.php",
            "parser": "generic_table",
            "base_url": "https://www.tjes.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJES - Últimas Notícias",
                "url": "https://www.tjes.jus.br/category/s1-front-page/ultimasnoticias/",
                "parser": "generic_news",
                "base_url": "https://www.tjes.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJGO
    {
        "acronym": "TJGO",
        "nome": "Tribunal de Justiça de Goiás",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJGO - Períodos de Indisponibilidade",
            "url": "https://www.tjgo.jus.br/index.php/39-tribunal/pje/132-periodos-de-indisponabilidade",
            "parser": "generic_news",
            "base_url": "https://www.tjgo.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJGO - Agência de Notícias",
                "url": "https://www.tjgo.jus.br/index.php/agencia-de-noticias/noticias-ccs",
                "parser": "generic_news",
                "base_url": "https://www.tjgo.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJMA
    {
        "acronym": "TJMA",
        "nome": "Tribunal de Justiça do Maranhão",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJMA - Relatório de Indisponibilidade",
            "url": "https://www.tjma.jus.br/servicos/tj/relatorio/indisponibilidade-sistemas",
            "parser": "generic_table",
            "base_url": "https://www.tjma.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJMA - Notícias",
                "url": "https://www.tjma.jus.br/midia/portal/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjma.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJMT
    {
        "acronym": "TJMT",
        "nome": "Tribunal de Justiça do Mato Grosso",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJMT - Registro de Indisponibilidade",
            "url": "https://www.tjmt.jus.br/indisponibilidade/RegistroIndisponivel",
            "parser": "generic_table",
            "base_url": "https://www.tjmt.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJMT - Notícias",
                "url": "https://www.tjmt.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjmt.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJMS
    {
        "acronym": "TJMS",
        "nome": "Tribunal de Justiça do Mato Grosso do Sul",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TJMS - Notícias",
                "url": "https://www.tjms.jus.br/noticias/",
                "parser": "generic_news",
                "base_url": "https://www.tjms.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJPA — sem página dedicada de indisponibilidade encontrada
    {
        "acronym": "TJPA",
        "nome": "Tribunal de Justiça do Pará",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TJPA - Portal de Notícias",
                "url": "https://www.tjpa.jus.br/PortalExterno/index-noticias.xhtml",
                "parser": "generic_news",
                "base_url": "https://www.tjpa.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJPB
    {
        "acronym": "TJPB",
        "nome": "Tribunal de Justiça da Paraíba",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TJPB - Notícias",
                "url": "https://www.tjpb.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjpb.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJPE
    {
        "acronym": "TJPE",
        "nome": "Tribunal de Justiça de Pernambuco",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJPE - Registro de Indisponibilidade",
            "url": "https://portal.tjpe.jus.br/web/processo-judicial-eletronico/registro-de-indisponibilidade",
            "parser": "generic_table",
            "base_url": "https://portal.tjpe.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJPE - Notícias",
                "url": "https://portal.tjpe.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://portal.tjpe.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJRN — site com geo-bloqueio para IPs externos (CI): retorna página de acesso negado
    {
        "acronym": "TJRN",
        "nome": "Tribunal de Justiça do Rio Grande do Norte",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": None,  # geo-bloqueio: retorna "Clique aqui para abrir sua solicitação"
        "noticias": [
            {
                "nome": "TJRN - Notícias",
                "url": "https://www.tjrn.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjrn.jus.br",
                "tipo": "Notícias",
                "skip": True,
                "skip_reason": "geo-bloqueio — inacessível fora da rede interna do tribunal",
            },
        ],
    },
    # TJRO — sem página pública de indisponibilidade encontrada
    {
        "acronym": "TJRO",
        "nome": "Tribunal de Justiça de Rondônia",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TJRO - Notícias",
                "url": "https://www.tjro.jus.br/noticias/mais-noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjro.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJRR — usa Projudi (não PJe)
    {
        "acronym": "TJRR",
        "nome": "Tribunal de Justiça de Roraima",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJRR - Indisponibilidade Projudi",
            "url": "https://projudi.tjrr.jus.br/projudi/indisponibilidades.jsp",
            "parser": "projudi",
            "base_url": "https://projudi.tjrr.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJRR - Notícias",
                "url": "https://www.tjrr.jus.br/index.php/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjrr.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJSC — usa eproc (não PJe)
    {
        "acronym": "TJSC",
        "nome": "Tribunal de Justiça de Santa Catarina",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJSC - Comunicados eproc",
            "url": "https://www.tjsc.jus.br/web/processo-eletronico-eproc/comunicados-eproc",
            "parser": "generic_news",
            "base_url": "https://www.tjsc.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJSC - Notícias",
                "url": "https://www.tjsc.jus.br/web/imprensa/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tjsc.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TJSE — usa eproc
    {
        "acronym": "TJSE",
        "nome": "Tribunal de Justiça de Sergipe",
        "grupo": "Tribunais-Estaduais",
        "principal": False,
        "alertas": {
            "nome": "TJSE - Indisponibilidade de Sistemas",
            "url": "https://www.tjse.jus.br/portal/consultas/novo-cpc/indisponibilidade-de-sistemas",
            "parser": "generic_news",
            "base_url": "https://www.tjse.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TJSE - Agência de Notícias",
                "url": "https://agencia.tjse.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://agencia.tjse.jus.br",
                "tipo": "Notícias",
            },
        ],
    },

    # ── Tribunais Regionais Federais ───────────────────────────────────────────
    {
        "acronym": "TRF1",
        "nome": "Tribunal Regional Federal da 1ª Região",
        "grupo": "TRFs",
        "principal": True,
        "alertas": {
            "nome": "TRF1 - Indisponibilidade",
            "url": "https://app.trf1.jus.br/indisponibilidades-relatorio/",
            "parser": "trf1",
            "base_url": "https://portal.trf1.jus.br",
            "tipo": "Indisponibilidade",
            "force_playwright": True,
            "wait_selector": "table, .mat-row, .cdk-row",
        },
        "noticias": [
            {
                "nome": "TRF1 - Notícias",
                "url": "https://www.trf1.jus.br/trf1/noticias/",
                "parser": "generic_news",
                "base_url": "https://www.trf1.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TRF2",
        "nome": "Tribunal Regional Federal da 2ª Região",
        "grupo": "TRFs",
        "principal": False,
        # eproc; usa página de avisos como melhor proxy de indisponibilidade
        "alertas": {
            "nome": "TRF2 - Avisos de Sistema",
            "url": "https://www.trf2.jus.br/jf2/aviso-jf2/",
            "parser": "generic_news",
            "base_url": "https://www.trf2.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRF2 - Notícias",
                "url": "https://portal.trf2.jus.br/noticias/",
                "parser": "generic_news",
                "base_url": "https://portal.trf2.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TRF3",
        "nome": "Tribunal Regional Federal da 3ª Região",
        "grupo": "TRFs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRF3 - Últimas Notícias",
                "url": "https://www.trf3.jus.br/noticias/",
                "parser": "generic_news",
                "base_url": "https://web.trf3.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TRF4",
        "nome": "Tribunal Regional Federal da 4ª Região",
        "grupo": "TRFs",
        "principal": False,
        # eproc; usa lista de avisos como melhor proxy de indisponibilidade
        "alertas": {
            "nome": "TRF4 - Avisos de Sistema",
            "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=aviso_listar&id_orgao=1",
            "parser": "generic_news",
            "base_url": "https://www.trf4.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRF4 - Notícias",
                "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=noticia_portal",
                "parser": "generic_news",
                "base_url": "https://www.trf4.jus.br",
                "tipo": "Notícias",
            },
            {
                "acronym": "TRF4-Norm",
                "nome": "TRF4 - Atos Normativos",
                "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=ato_normativo_pesquisar",
                "parser": "generic_news",
                "base_url": "https://www.trf4.jus.br",
                "tipo": "Normativos",
                "skip": True,
                "skip_reason": "formulário JS — exige interação para listar resultados",
            },
        ],
    },
    {
        "acronym": "TRF5",
        "nome": "Tribunal Regional Federal da 5ª Região",
        "grupo": "TRFs",
        "principal": True,
        "alertas": {
            "nome": "TRF5 - Indisponibilidade PJe",
            "url": "https://pje.trf5.jus.br/pje/IndisponibilidadeSistema/listView.seam",
            "parser": "trf5",
            "base_url": "https://pje.trf5.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRF5 - Notícias",
                "url": "https://www.trf5.jus.br/index.php/noticias",
                "parser": "generic_news",
                "base_url": "https://www.trf5.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TRF6",
        "nome": "Tribunal Regional Federal da 6ª Região",
        "grupo": "TRFs",
        "principal": False,
        # eproc; usa página de avisos como melhor proxy de indisponibilidade
        "alertas": {
            "nome": "TRF6 - Avisos de Sistema",
            "url": "https://portal.trf6.jus.br/avisos/",
            "parser": "generic_news",
            "base_url": "https://portal.trf6.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRF6 - Notícias",
                "url": "https://portal.trf6.jus.br/noticias/",
                "parser": "generic_news",
                "base_url": "https://portal.trf6.jus.br",
                "tipo": "Notícias",
            },
            {
                "acronym": "TRF6-Norm",
                "nome": "TRF6 - Atos Normativos",
                "url": "https://portal.trf6.jus.br/atos-normativos/",
                "parser": "generic_news",
                "base_url": "https://portal.trf6.jus.br",
                "tipo": "Normativos",
            },
        ],
    },

    # ── Tribunais Regionais do Trabalho ────────────────────────────────────────
    {
        "acronym": "TRT1",
        "nome": "Tribunal Regional do Trabalho da 1ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT1 - Indisponibilidade PJe",
            "url": "https://www.trt1.jus.br/certidao-de-indisponibilidade",
            "parser": "generic_table",
            "base_url": "https://www.trt1.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT1 - Últimas Notícias",
                "url": "https://www.trt1.jus.br/ultimas-noticias",
                "parser": "generic_news",
                "base_url": "https://www.trt1.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TRT2",
        "nome": "Tribunal Regional do Trabalho da 2ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT2 - Indisponibilidade PJe",
            "url": "https://aplicacoes8.trt2.jus.br/sis/indisponibilidade/consulta",
            "parser": "generic_table",
            "base_url": "https://aplicacoes8.trt2.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT2 - Notícias",
                "url": "https://ww2.trt2.jus.br/noticias/noticias",
                "parser": "generic_news",
                "base_url": "https://ww2.trt2.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TRT3",
        "nome": "Tribunal Regional do Trabalho da 3ª Região",
        "grupo": "TRTs",
        "principal": False,
        # Sem página pública de indisponibilidade encontrada
        "alertas": None,
        "noticias": [
            {
                "nome": "TRT3 - Notícias Institucionais",
                "url": "https://portal.trt3.jus.br/internet/conheca-o-trt/comunicacao/noticias-institucionais",
                "parser": "generic_news",
                "base_url": "https://portal.trt3.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TRT4",
        "nome": "Tribunal Regional do Trabalho da 4ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT4 - Indisponibilidade PJe",
            "url": "https://www.trt4.jus.br/portais/trt4/pje-indisponibilidade",
            "parser": "generic_table",
            "base_url": "https://www.trt4.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT4 - Notícias",
                "url": "https://www.trt4.jus.br/portais/trt4/modulos/noticias/todas/0",
                "parser": "generic_news",
                "base_url": "https://www.trt4.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    {
        "acronym": "TRT15",
        "nome": "Tribunal Regional do Trabalho da 15ª Região",
        "grupo": "TRTs",
        "principal": True,
        "alertas": {
            "nome": "TRT15 - Indisponibilidade PJe",
            "url": "https://trt15.jus.br/pje/indisponibilidade-pje",
            "parser": "generic_table",
            "base_url": "https://trt15.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT15 - Notícias",
                "url": "https://trt15.jus.br/noticia/",
                "parser": "generic_news",
                "base_url": "https://trt15.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT5
    {
        "acronym": "TRT5",
        "nome": "Tribunal Regional do Trabalho da 5ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT5 - Indisponibilidade PJe",
            "url": "https://portalpje.trt5.jus.br/pje-indisponibilidades",
            "parser": "generic_news",
            "base_url": "https://portalpje.trt5.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT5 - Notícias",
                "url": "https://www.trt5.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://www.trt5.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT6
    {
        "acronym": "TRT6",
        "nome": "Tribunal Regional do Trabalho da 6ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT6 - Períodos de Indisponibilidade PJe",
            "url": "https://www.trt6.jus.br/portal/pje/historico",
            "parser": "generic_table",
            "base_url": "https://www.trt6.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT6 - Notícias",
                "url": "https://www.trt6.jus.br/portal/noticias",
                "parser": "generic_news",
                "base_url": "https://www.trt6.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT7
    {
        "acronym": "TRT7",
        "nome": "Tribunal Regional do Trabalho da 7ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT7 - Indisponibilidades PJe",
            "url": "https://www.trt7.jus.br/index.php/blog/200-servicos/227-pje/7512-indisponibilidades-do-pje",
            "parser": "generic_news",
            "base_url": "https://www.trt7.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT7 - Notícias",
                "url": "https://www.trt7.jus.br/index.php/noticias/todas-as-noticias",
                "parser": "generic_news",
                "base_url": "https://www.trt7.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT8
    {
        "acronym": "TRT8",
        "nome": "Tribunal Regional do Trabalho da 8ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT8 - Indisponibilidade PJe",
            "url": "https://www.trt8.jus.br/pje/indisponibilidade-do-sistema",
            "parser": "generic_table",
            "base_url": "https://www.trt8.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT8 - Notícias",
                "url": "https://www.trt8.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://www.trt8.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT9
    {
        "acronym": "TRT9",
        "nome": "Tribunal Regional do Trabalho da 9ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT9 - Certidões de Indisponibilidade",
            "url": "https://www.trt9.jus.br/portal/pagina.xhtml?secao=67&pagina=Certidoes_de_Indisponibilidade_de_Sistemas",
            "parser": "generic_news",
            "base_url": "https://www.trt9.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT9 - Notícias",
                "url": "https://www.trt9.jus.br/portal/noticias.xhtml",
                "parser": "generic_news",
                "base_url": "https://www.trt9.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT10 — sem página pública de indisponibilidade encontrada
    {
        "acronym": "TRT10",
        "nome": "Tribunal Regional do Trabalho da 10ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRT10 - ASCOM Notícias",
                "url": "https://www.trt10.jus.br/ascom/noticias",
                "parser": "generic_news",
                "base_url": "https://www.trt10.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT11
    {
        "acronym": "TRT11",
        "nome": "Tribunal Regional do Trabalho da 11ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT11 - Períodos de Indisponibilidade PJe",
            "url": "https://portal.trt11.jus.br/index.php/advogados/pagina-pje/33-pje/365-periodos-de-indisponibilidade-do-pje-jt",
            "parser": "generic_news",
            "base_url": "https://portal.trt11.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT11 - Notícias",
                "url": "https://portal.trt11.jus.br/index.php/comunicacao/noticias-lista",
                "parser": "generic_news",
                "base_url": "https://portal.trt11.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT12
    {
        "acronym": "TRT12",
        "nome": "Tribunal Regional do Trabalho da 12ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT12 - Registros de Indisponibilidade PJe",
            "url": "https://portal.trt12.jus.br/pje/uso_indisponibilidade",
            "parser": "generic_news",
            "base_url": "https://portal.trt12.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT12 - Notícias",
                "url": "https://portal.trt12.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://portal.trt12.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT13
    {
        "acronym": "TRT13",
        "nome": "Tribunal Regional do Trabalho da 13ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT13 - Relatório de Indisponibilidade PJe",
            "url": "https://www.trt13.jus.br/pje/indisponibilidade",
            "parser": "generic_news",
            "base_url": "https://www.trt13.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT13 - Notícias",
                "url": "https://www.trt13.jus.br/informe-se/noticias",
                "parser": "generic_news",
                "base_url": "https://www.trt13.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT14
    {
        "acronym": "TRT14",
        "nome": "Tribunal Regional do Trabalho da 14ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT14 - Agenda de Indisponibilidade PJe",
            "url": "https://portal.trt14.jus.br/portal/pje/indisponibilidade",
            "parser": "generic_news",
            "base_url": "https://portal.trt14.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT14 - Notícias",
                "url": "https://portal.trt14.jus.br/portal/noticias",
                "parser": "generic_news",
                "base_url": "https://portal.trt14.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT16
    {
        "acronym": "TRT16",
        "nome": "Tribunal Regional do Trabalho da 16ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT16 - Calendário de Indisponibilidade",
            "url": "https://www.trt16.jus.br/servicos/outros-servicos/calendario-indisponibilidade",
            "parser": "generic_table",
            "base_url": "https://www.trt16.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT16 - Notícias",
                "url": "https://www.trt16.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://www.trt16.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT17
    {
        "acronym": "TRT17",
        "nome": "Tribunal Regional do Trabalho da 17ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT17 - Certidão de Indisponibilidade PJe",
            "url": "https://www.trt17.jus.br/web/servicos/w/certidao-de-indisponibilidade-do-pje",
            "parser": "generic_news",
            "base_url": "https://www.trt17.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT17 - Notícias",
                "url": "https://www.trt17.jus.br/noticias/",
                "parser": "generic_news",
                "base_url": "https://www.trt17.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT18
    {
        "acronym": "TRT18",
        "nome": "Tribunal Regional do Trabalho da 18ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT18 - Certidões de Indisponibilidade PJe",
            "url": "https://www.trt18.jus.br/portal/servicos/pje/01-certidoes-indisponibilidades-do-pje-no-trt-18a-regiao/",
            "parser": "generic_news",
            "base_url": "https://www.trt18.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT18 - Notícias",
                "url": "https://www.trt18.jus.br/portal/noticias/",
                "parser": "generic_news",
                "base_url": "https://www.trt18.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT19
    {
        "acronym": "TRT19",
        "nome": "Tribunal Regional do Trabalho da 19ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": None,  # site retorna "Erro temporário. Tente novamente." no CI
        "noticias": [
            {
                "nome": "TRT19 - Notícias",
                "url": "https://site.trt19.jus.br/portalTRT19/noticiafoco/",
                "parser": "generic_news",
                "base_url": "https://site.trt19.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT20
    {
        "acronym": "TRT20",
        "nome": "Tribunal Regional do Trabalho da 20ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT20 - Indisponibilidade PJe",
            "url": "https://www.trt20.jus.br/pje/indisponibilidade",
            "parser": "generic_table",
            "base_url": "https://www.trt20.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT20 - Notícias",
                "url": "https://www.trt20.jus.br/noticias",
                "parser": "generic_news",
                "base_url": "https://www.trt20.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT21
    {
        "acronym": "TRT21",
        "nome": "Tribunal Regional do Trabalho da 21ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT21 - Indisponibilidade PJe",
            "url": "https://www.trt21.jus.br/servicos/pje/indisponibilidade-sistema",
            "parser": "generic_table",
            "base_url": "https://www.trt21.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT21 - Notícias",
                "url": "https://www.trt21.jus.br/comunicacao/noticias/",
                "parser": "generic_news",
                "base_url": "https://www.trt21.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT22
    {
        "acronym": "TRT22",
        "nome": "Tribunal Regional do Trabalho da 22ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT22 - Indisponibilidade de Serviços de TIC",
            "url": "https://www.trt22.jus.br/servicos/indisponibilidade-de-servicos-de-tic",
            "parser": "generic_table",
            "base_url": "https://www.trt22.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT22 - Notícias",
                "url": "https://www.trt22.jus.br/noticia",
                "parser": "generic_news",
                "base_url": "https://www.trt22.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT23 — sem página pública de indisponibilidade encontrada
    {
        "acronym": "TRT23",
        "nome": "Tribunal Regional do Trabalho da 23ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRT23 - Notícias",
                "url": "https://portal.trt23.jus.br/portal/noticias",
                "parser": "generic_news",
                "base_url": "https://portal.trt23.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRT24
    {
        "acronym": "TRT24",
        "nome": "Tribunal Regional do Trabalho da 24ª Região",
        "grupo": "TRTs",
        "principal": False,
        "alertas": {
            "nome": "TRT24 - Relatório de Indisponibilidade PJe",
            "url": "https://www.trt24.jus.br/relatorio-indisponibilidade-pje",
            "parser": "generic_table",
            "base_url": "https://www.trt24.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRT24 - Notícias Institucionais",
                "url": "https://www.trt24.jus.br/web/guest/noticias-institucionais",
                "parser": "generic_news",
                "base_url": "https://www.trt24.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # ── Tribunais Regionais Eleitorais ────────────────────────────────────────
    # TRE-AC
    {
        "acronym": "TRE-AC",
        "nome": "Tribunal Regional Eleitoral do Acre",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-AC - Indisponibilidade PJe",
            "url": "https://www.tre-ac.jus.br/servicos-judiciais/pje-processo-judicial-eletronico/indisponibilidades-do-sistema-pje-tse",
            "parser": "generic_news",
            "base_url": "https://www.tre-ac.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-AC - Notícias",
                "url": "https://www.tre-ac.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-ac.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-AL
    {
        "acronym": "TRE-AL",
        "nome": "Tribunal Regional Eleitoral de Alagoas",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-AL - Notícias",
                "url": "https://www.tre-al.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-al.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-AP
    {
        "acronym": "TRE-AP",
        "nome": "Tribunal Regional Eleitoral do Amapá",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-AP - Notícias",
                "url": "https://www.tre-ap.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-ap.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-AM
    {
        "acronym": "TRE-AM",
        "nome": "Tribunal Regional Eleitoral do Amazonas",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-AM - Notícias",
                "url": "https://www.tre-am.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-am.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-BA
    {
        "acronym": "TRE-BA",
        "nome": "Tribunal Regional Eleitoral da Bahia",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-BA - Indisponibilidades PJe",
            "url": "https://www.tre-ba.jus.br/servicos-judiciais/processo-judicial-eletronico-pje/indisponibilidades-do-pje",
            "parser": "generic_news",
            "base_url": "https://www.tre-ba.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-BA - Notícias",
                "url": "https://www.tre-ba.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-ba.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-CE — sem página dedicada de indisponibilidade
    {
        "acronym": "TRE-CE",
        "nome": "Tribunal Regional Eleitoral do Ceará",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-CE - Notícias",
                "url": "https://www.tre-ce.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-ce.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-DF
    {
        "acronym": "TRE-DF",
        "nome": "Tribunal Regional Eleitoral do Distrito Federal",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-DF - Notícias",
                "url": "https://www.tre-df.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-df.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-ES
    {
        "acronym": "TRE-ES",
        "nome": "Tribunal Regional Eleitoral do Espírito Santo",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-ES - Notícias",
                "url": "https://www.tre-es.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-es.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-GO
    {
        "acronym": "TRE-GO",
        "nome": "Tribunal Regional Eleitoral de Goiás",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-GO - Indisponibilidades PJe",
            "url": "https://www.tre-go.jus.br/servicos-judiciais/processo-judicial-eletronico-pje/indisponibilidades-do-sistema-pje",
            "parser": "generic_news",
            "base_url": "https://www.tre-go.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-GO - Notícias",
                "url": "https://www.tre-go.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-go.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-MA
    {
        "acronym": "TRE-MA",
        "nome": "Tribunal Regional Eleitoral do Maranhão",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-MA - Comunicados Institucionais",
            "url": "https://www.tre-ma.jus.br/institucional/comunicados",
            "parser": "generic_news",
            "base_url": "https://www.tre-ma.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-MA - Notícias",
                "url": "https://www.tre-ma.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-ma.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-MG
    {
        "acronym": "TRE-MG",
        "nome": "Tribunal Regional Eleitoral de Minas Gerais",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-MG - Indisponibilidade PJe",
            "url": "https://www.tre-mg.jus.br/servicos-judiciais/processo-judicial-eletronico-pje/indisponibilidade-do-sistema-pje",
            "parser": "generic_news",
            "base_url": "https://www.tre-mg.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-MG - Notícias",
                "url": "https://www.tre-mg.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-mg.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-MS
    {
        "acronym": "TRE-MS",
        "nome": "Tribunal Regional Eleitoral do Mato Grosso do Sul",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-MS - Indisponibilidades PJe",
            "url": "https://www.tre-ms.jus.br/servicos-judiciais/processo-judicial-eletronico-pje/indisponibilidades-do-sistema-pje",
            "parser": "generic_news",
            "base_url": "https://www.tre-ms.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-MS - Notícias",
                "url": "https://www.tre-ms.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-ms.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-MT
    {
        "acronym": "TRE-MT",
        "nome": "Tribunal Regional Eleitoral do Mato Grosso",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-MT - Serviço de Indisponibilidade PJe",
            "url": "https://www.tre-mt.jus.br/servicos-judiciais/processos/processo-judicial-eletronico/servico-de-indisponibilidade-do-pje",
            "parser": "generic_news",
            "base_url": "https://www.tre-mt.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-MT - Notícias",
                "url": "https://www.tre-mt.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-mt.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-PA
    {
        "acronym": "TRE-PA",
        "nome": "Tribunal Regional Eleitoral do Pará",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-PA - Notícias",
                "url": "https://www.tre-pa.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-pa.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-PB
    {
        "acronym": "TRE-PB",
        "nome": "Tribunal Regional Eleitoral da Paraíba",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-PB - Notícias",
                "url": "https://www.tre-pb.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-pb.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-PE
    {
        "acronym": "TRE-PE",
        "nome": "Tribunal Regional Eleitoral de Pernambuco",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-PE - Indisponibilidades PJe",
            "url": "https://www.tre-pe.jus.br/servicos-judiciais/processo-judicial-eletronico-pje/indisponibilidades-do-sistema-pje",
            "parser": "generic_news",
            "base_url": "https://www.tre-pe.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-PE - Notícias",
                "url": "https://www.tre-pe.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-pe.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-PI
    {
        "acronym": "TRE-PI",
        "nome": "Tribunal Regional Eleitoral do Piauí",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-PI - Indisponibilidades PJe",
            "url": "https://www.tre-pi.jus.br/servicos-judiciais/processo-judicial-eletronico-pje/indisponibilidades-do-sistema-pje",
            "parser": "generic_news",
            "base_url": "https://www.tre-pi.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-PI - Notícias",
                "url": "https://www.tre-pi.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-pi.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-PR
    {
        "acronym": "TRE-PR",
        "nome": "Tribunal Regional Eleitoral do Paraná",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-PR - Indisponibilidade PJe",
            "url": "https://www.tre-pr.jus.br/servicos-judiciais/processo-judicial-eletronico-pje/indisponibilidade-pje",
            "parser": "generic_news",
            "base_url": "https://www.tre-pr.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-PR - Notícias",
                "url": "https://www.tre-pr.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-pr.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-RJ
    {
        "acronym": "TRE-RJ",
        "nome": "Tribunal Regional Eleitoral do Rio de Janeiro",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-RJ - Notícias",
                "url": "https://www.tre-rj.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-rj.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-RN
    {
        "acronym": "TRE-RN",
        "nome": "Tribunal Regional Eleitoral do Rio Grande do Norte",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-RN - Notícias",
                "url": "https://www.tre-rn.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-rn.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-RO
    {
        "acronym": "TRE-RO",
        "nome": "Tribunal Regional Eleitoral de Rondônia",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-RO - Indisponibilidades PJe",
            "url": "https://www.tre-ro.jus.br/servicos-judiciais/processo-judicial-eletronico-pje/indisponibilidades-do-sistema-pje-tre-ro",
            "parser": "generic_news",
            "base_url": "https://www.tre-ro.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-RO - Notícias",
                "url": "https://www.tre-ro.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-ro.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-RR
    {
        "acronym": "TRE-RR",
        "nome": "Tribunal Regional Eleitoral de Roraima",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-RR - Notícias",
                "url": "https://www.tre-rr.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-rr.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-RS
    {
        "acronym": "TRE-RS",
        "nome": "Tribunal Regional Eleitoral do Rio Grande do Sul",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-RS - Notícias",
                "url": "https://www.tre-rs.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-rs.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-SC
    {
        "acronym": "TRE-SC",
        "nome": "Tribunal Regional Eleitoral de Santa Catarina",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-SC - Verificação de Indisponibilidade PJe",
            "url": "https://www.tre-sc.jus.br/servicos-judiciais/pje/verificacao-de-indisponibilidade",
            "parser": "generic_news",
            "base_url": "https://www.tre-sc.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-SC - Notícias",
                "url": "https://www.tre-sc.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-sc.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-SE
    {
        "acronym": "TRE-SE",
        "nome": "Tribunal Regional Eleitoral de Sergipe",
        "grupo": "TREs",
        "principal": False,
        "alertas": None,
        "noticias": [
            {
                "nome": "TRE-SE - Notícias",
                "url": "https://www.tre-se.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-se.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-SP
    {
        "acronym": "TRE-SP",
        "nome": "Tribunal Regional Eleitoral de São Paulo",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-SP - Indisponibilidade PJe",
            "url": "https://www.tre-sp.jus.br/servicos-judiciais/indisponibilidade-pje",
            "parser": "generic_table",
            "base_url": "https://www.tre-sp.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-SP - Notícias",
                "url": "https://www.tre-sp.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-sp.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
    # TRE-TO
    {
        "acronym": "TRE-TO",
        "nome": "Tribunal Regional Eleitoral do Tocantins",
        "grupo": "TREs",
        "principal": False,
        "alertas": {
            "nome": "TRE-TO - Indisponibilidade PJe",
            "url": "https://www.tre-to.jus.br/servicos-judiciais/processo-judicial-eletronico-pje/indisponibilidade-do-sistema-pje",
            "parser": "generic_news",
            "base_url": "https://www.tre-to.jus.br",
            "tipo": "Indisponibilidade",
        },
        "noticias": [
            {
                "nome": "TRE-TO - Notícias",
                "url": "https://www.tre-to.jus.br/comunicacao/noticias",
                "parser": "generic_news",
                "base_url": "https://www.tre-to.jus.br",
                "tipo": "Notícias",
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# Helpers para derivar as listas planas de cada pipeline
# ---------------------------------------------------------------------------

def _to_alertas_entry(f: dict) -> dict | None:
    """Constrói a entrada plana de alertas a partir de uma entrada do FONTES."""
    if not f.get("alertas"):
        return None
    a = f["alertas"].copy()
    a["acronym"] = f["acronym"]
    a.setdefault("nome",  f["nome"] + " — Indisponibilidade")
    a["grupo"]   = f["grupo"]
    a["fase"]    = "alertas"
    a.setdefault("tipo", "Indisponibilidade")
    a["principal"] = f.get("principal", False)
    return a


def _to_noticias_entries(f: dict) -> list[dict]:
    """Constrói a lista plana de entradas de notícias a partir de uma entrada do FONTES."""
    result = []
    for n in f.get("noticias") or []:
        item = n.copy()
        item.setdefault("acronym", f["acronym"])
        item.setdefault("grupo",   f["grupo"])
        item["fase"] = "noticias"
        item["principal"] = f.get("principal", False)
        result.append(item)
    return result


# Listas derivadas — usadas pelos dois pipelines e pelos testes
TRIBUNAIS_DIRETO = [e for f in FONTES if (e := _to_alertas_entry(f)) is not None]   # 61 fontes
FONTES_NOTICIAS  = [e for f in FONTES for e in _to_noticias_entries(f)]              # 104 fontes

# ---------------------------------------------------------------------------
# Camada de fetch (compartilhada pelos dois subsistemas)
# ---------------------------------------------------------------------------

def _fetch_requests(url: str):
    """Baixa página via requests. Retorna BeautifulSoup ou None.

    Tenta primeiro com verify=True (seguro). Se o tribunal tiver problema
    de certificado (SSLError), reexecuta com verify=False e registra aviso
    — mantendo segurança na maioria dos sites mas tolerando CAs antigas.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=True)
        resp.raise_for_status()
        if len(resp.text) < 400:
            return None
        return BeautifulSoup(resp.text, "lxml")
    except requests.exceptions.SSLError:
        log.warning("⚠️  Certificado SSL inválido em %s — retentando sem verificação.", url)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
            resp.raise_for_status()
            if len(resp.text) < 400:
                return None
            return BeautifulSoup(resp.text, "lxml")
        except Exception as exc:
            log.debug("requests falhou (sem SSL) para %s: %s", url, exc)
            return None
    except Exception as exc:
        log.debug("requests falhou para %s: %s", url, exc)
        return None


def _fetch_playwright(url: str, wait_selector: str = None, extra_wait: int = 3):
    """Renderiza a página com Playwright headless. Retorna BeautifulSoup ou None."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page(
                user_agent=HEADERS["User-Agent"],
                locale="pt-BR",
            )
            page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="networkidle")

            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10_000)
                except Exception:
                    pass  # continua mesmo sem o seletor aparecer

            if extra_wait:
                time.sleep(extra_wait)

            html = page.content()
            browser.close()

        return BeautifulSoup(html, "lxml")
    except Exception as exc:
        log.warning("Playwright falhou para %s: %s", url, exc)
        return None


def fetch_page(fonte: dict):
    """
    Orquestra a tentativa de fetch para qualquer dict de fonte.
    force_playwright=True → vai direto pro Playwright (SPA conhecida).
    parser="rss"          → faz requests com lxml-xml (nunca usa Playwright).
    skip_playwright=True  → usa apenas requests; não tenta Playwright como fallback.
    Caso contrário tenta requests; se retornar vazio, cai para Playwright.
    """
    url              = fonte["url"]
    force_playwright = fonte.get("force_playwright", False)
    wait_selector    = fonte.get("wait_selector")
    extra_wait       = fonte.get("extra_wait", 3)

    # Feeds RSS/XML — parser lxml-xml, nunca usa Playwright
    if fonte.get("parser") == "rss":
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=True)
            resp.raise_for_status()
            if len(resp.text) < 100:
                return None
            return BeautifulSoup(resp.text, "lxml-xml")
        except Exception as exc:
            log.debug("RSS fetch falhou para %s: %s", url, exc)
            return None

    if force_playwright:
        log.info("  → Playwright forçado (SPA).")
        return _fetch_playwright(url, wait_selector, extra_wait)

    soup = _fetch_requests(url)
    if soup:
        return soup

    if fonte.get("skip_playwright"):
        return None

    log.info("  → requests sem conteúdo útil, tentando Playwright...")
    return _fetch_playwright(url, wait_selector, extra_wait)

# ---------------------------------------------------------------------------
# Helpers de extração
# ---------------------------------------------------------------------------

def _txt(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def _abs(href: str, base_url: str) -> str:
    if not href or href.startswith("javascript"):
        return base_url
    if href.startswith("http"):
        return href
    return base_url.rstrip("/") + "/" + href.lstrip("/")

# ---------------------------------------------------------------------------
# Parsers — Subsistema 1 (indisponibilidades — originais)
# ---------------------------------------------------------------------------

def parse_generic_news(soup, acronym, base_url):
    """Páginas de notícias — suporta múltiplos CMS (Liferay, Drupal, WordPress, custom).

    Estratégias em cascata:
      1. <article> semântico
      2. Classes de lista de notícias (Drupal views, Liferay asset-entries, custom)
      3. Liferay asset-publisher / portlet-content
      4. h2/h3/h4 com link dentro da área de conteúdo
      5. Fallback: qualquer link com texto >= 25 chars na área de conteúdo

    Remove nav/footer/acessibilidade antes de processar.
    """
    # Remove elementos que nunca contêm notícias reais
    for tag in soup.select(_NAV_TAGS):
        tag.decompose()

    # Área de conteúdo principal — tenta do mais específico ao mais genérico
    area = soup.select_one(
        "main, #main, .main-content, #content, #main-content, "
        ".content-area, .portlet-body, .journal-content-article, "
        ".portlet-content, .lfr-portlet-body, .asset-publisher-content, "
        "#portal-content, .conteudo, #conteudo, .page-content"
    ) or soup

    # ── Estratégia 1: <article> semântico ────────────────────────────
    items = area.select("article")

    # ── Estratégia 2: classes de lista comuns ─────────────────────────
    if not items:
        items = area.select(
            # Drupal / views
            ".views-row, .item-list li, "
            # CMS genérico
            ".noticia-item, .asset-entry, .asset-abstract, "
            ".news-item, .news-list li, "
            ".lista-noticias li, .listing li, "
            # WordPress / Elementor / Gutenberg
            ".entry-title, .post-title, h2.entry-title, h3.entry-title, "
            ".ct-post-title, .jeg_post_title, .wp-block-post-title, "
            # Padrões por substring de classe
            "[class*='noticia']:not(nav), [class*='news-item']"
        )

    # ── Estratégia 3: Liferay asset-publisher ────────────────────────
    if not items:
        items = area.select(
            ".asset-entries .asset-title a, "
            ".portlet-asset-publisher .asset-title a, "
            ".lfr-asset-list-item, "
            ".search-results .portlet-title-text"
        )

    # ── Estratégia 4: headings com link direto ───────────────────────
    if not items:
        items = area.select("h2 a, h3 a, h4 a, .titulo a, .title a, .headline a")

    results = []
    for item in items[:MAX_ITEMS]:
        if item.name == "a":
            a      = item
            titulo = _limpar_data_titulo(_txt(a))
            link   = _abs(a.get("href", ""), base_url)
            parent = a.parent
            resumo = _txt(parent) if parent and parent.name not in ("html", "body", "nav") else ""
        else:
            a      = item.find("a")
            titulo = _limpar_data_titulo(
                _txt(a) if a else _txt(item.find(["h2", "h3", "h4"]) or item)
            )
            link   = _abs(a.get("href", "") if a else "", base_url)
            resumo_tag = item.find(["p", "span"], class_=lambda c: c and any(
                k in c.lower() for k in ("resumo", "desc", "summary", "intro", "lead", "abstract")
            )) if hasattr(item, "find") else None
            resumo = _txt(resumo_tag) if resumo_tag else ""

        if titulo and len(titulo) > 15 and not _RE_PURE_DATE.match(titulo.strip()):
            results.append({"titulo": titulo, "resumo": resumo, "link": link})

    # ── Estratégia 4b: headings sem link direto → busca link no pai ──
    # Cobre o padrão "<h3>Título</h3><a href='...'>Saiba mais</a>" muito comum
    # em portais de tribunais onde o texto do link é curto (< 25 chars).
    if not results:
        for h in area.select("h2, h3, h4"):
            titulo_h = _limpar_data_titulo(_txt(h))
            if len(titulo_h) < 15 or _RE_PURE_DATE.match(titulo_h.strip()):
                continue
            # Busca o link mais próximo: dentro do heading, no pai, ou no irmão seguinte
            a = (h.find("a")
                 or (h.parent.find("a") if h.parent else None)
                 or h.find_next_sibling("a"))
            if not a:
                continue
            href = a.get("href", "")
            if not href or href.startswith(("#", "javascript")):
                continue
            results.append({
                "titulo": titulo_h,
                "resumo": "",
                "link":   _abs(href, base_url),
            })
            if len(results) >= MAX_ITEMS:
                break

    # ── Estratégia 5: qualquer link substancial na área ───────────────
    if not results:
        for a in area.select("a[href]"):
            if len(results) >= MAX_ITEMS:
                break
            href   = a.get("href", "")
            titulo = _limpar_data_titulo(_txt(a))
            if (len(titulo) >= 25
                    and not href.startswith("#")
                    and "javascript" not in href):
                results.append({
                    "titulo": titulo,
                    "resumo": "",
                    "link":   _abs(href, base_url),
                })

    return results


def parse_generic_table(soup, acronym, base_url):
    """Páginas com tabela HTML de indisponibilidades.

    Melhorias em relação à versão original:
    - Se col[0] for apenas uma data/timestamp, trata como período e promove
      col[1] para título — evita usar "09/03/2026 das 06:00..." como título.
    - Fallback li/p: exclui nav/header/footer, exige min 40 chars,
      descarta itens que são só datas (acessibilidade, menus).
    """
    results = []
    HEADERS_SKIP = {"sistema", "data", "período", "status", "descrição", "n°", "nº"}

    tabelas = soup.select("table")
    if tabelas:
        for tabela in tabelas:
            for row in tabela.select("tr")[1:MAX_ITEMS + 1]:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue
                col0 = _txt(cells[0])
                if not col0 or col0.lower() in HEADERS_SKIP:
                    continue

                # Se col[0] é apenas data/período, promove col[1] como título
                if _RE_PURE_DATE.match(col0.strip()) and len(cells) > 1:
                    titulo  = _txt(cells[1])
                    periodo = col0
                    resumo  = periodo + " | " + (
                        " | ".join(_txt(c) for c in cells[2:4]) if len(cells) > 2 else ""
                    )
                else:
                    titulo = col0
                    resumo = " | ".join(_txt(c) for c in cells[1:3]) if len(cells) > 1 else ""
                    periodo = ""

                if not titulo or len(titulo) < 5:
                    continue

                a = row.find("a")
                link = _abs(a.get("href", "") if a else "", base_url)
                results.append({"titulo": titulo, "resumo": resumo, "link": link})
        return results

    # Fallback: li/p — remove navegação e exige conteúdo mínimo real
    for tag in soup.select(_NAV_TAGS):
        tag.decompose()

    for item in soup.select("li, p")[:MAX_ITEMS]:
        texto = _txt(item)
        # Exige 40+ chars e rejeita itens que são só uma data
        if len(texto) < 40 or _RE_PURE_DATE.match(texto.strip()):
            continue
        a = item.find("a")
        link = _abs(a.get("href", "") if a else "", base_url)
        results.append({"titulo": texto[:150], "resumo": texto, "link": link})
    return results


def parse_tjsp(soup, acronym, base_url):
    """
    TJSP — lista de comunicados com links diretos.
    Extrai data + título de cada linha da tabela de comunicados.
    """
    results = []
    # Tenta tabela de comunicados primeiro
    rows = soup.select("table tr")
    if rows:
        for row in rows[1:MAX_ITEMS + 1]:
            cells = row.find_all("td")
            if not cells:
                continue
            a = row.find("a")
            titulo = _txt(a) if a else _txt(cells[0])
            link   = _abs(a.get("href", "") if a else "", base_url)
            resumo = _txt(cells[1]) if len(cells) > 1 else ""
            if titulo and len(titulo) > 10:
                results.append({"titulo": titulo, "resumo": resumo, "link": link})
        if results:
            return results

    # Fallback: links com href contendo "Comunicado"
    for a in soup.select("a[href*='Comunicado'], a[href*='comunicado']")[:MAX_ITEMS]:
        titulo = _txt(a)
        link   = _abs(a.get("href", ""), base_url)
        parent = a.parent
        resumo = _txt(parent) if parent and parent.name not in ("html", "body", "nav") else ""
        if titulo and len(titulo) > 10:
            results.append({"titulo": titulo, "resumo": resumo, "link": link})
    return results


def parse_tjmg(soup, acronym, base_url):
    """
    TJMG — ignora menu de navegação (nav, header) e captura
    apenas o conteúdo da área principal da página.
    """
    results = []
    # Remove menus e cabeçalhos para evitar capturar itens de navegação
    for tag in soup.select("nav, header, footer, .menu, .navbar"):
        tag.decompose()

    # Tenta tabela da área de conteúdo principal
    main = soup.select_one("main, .main-content, #content, .content, article")
    area = main or soup

    tabelas = area.select("table")
    if tabelas:
        return parse_generic_table(area, acronym, base_url)

    # Tenta links dentro da área principal (ex: PDFs de certidões)
    for a in area.select("a[href]")[:MAX_ITEMS]:
        titulo = _txt(a)
        href   = a.get("href", "")
        # Ignora links de menu (javascript:, âncoras, itens muito curtos)
        if href.startswith("javascript") or href.startswith("#"):
            continue
        if len(titulo) < 10:
            continue
        link = _abs(href, base_url)
        results.append({"titulo": titulo, "resumo": "", "link": link})

    return results


def parse_trf1(soup, acronym, base_url):
    """
    TRF1 — SPA Angular renderizada via Playwright.
    Extrai APENAS linhas de tabela — ignora parágrafos instrucionais
    fixos da página (ex: "O QUE O RELATÓRIO EXIBE?...").
    Se não houver tabela renderizada, retorna vazio (sem fallback para <p>).
    """
    results = []
    # Remove menus e painéis laterais
    for tag in soup.select("nav, header, footer, mat-sidenav, mat-toolbar"):
        tag.decompose()

    tabelas = soup.select("table, mat-table")
    if not tabelas:
        # SPA ainda não renderizou — retorna vazio, sem capturar texto de página
        return results

    for tabela in tabelas:
        rows = tabela.select("tr, mat-row, .cdk-row")
        for row in rows[1:MAX_ITEMS + 1]:
            cells = row.find_all(["td", "mat-cell", "th"])
            if not cells:
                continue
            titulo = _txt(cells[0])
            # Ignora células vazias ou que sejam cabeçalho repetido
            if len(titulo) < 5:
                continue
            resumo = " | ".join(_txt(c) for c in cells[1:3]) if len(cells) > 1 else ""
            a = row.find("a")
            link = _abs(a.get("href", "") if a else "", base_url)
            results.append({"titulo": titulo, "resumo": resumo, "link": link})

    return results


def parse_trf5(soup, acronym, base_url):
    """
    TRF5 — extrai apenas linhas reais da tabela de indisponibilidades.
    Remove formulário, cabeçalho e mensagens de interface antes de parsear.
    Ignora linhas de UI como "0 resultados", "Pesquisar", "Mensagem".
    """
    results = []
    # Remove formulário de pesquisa, cabeçalho, rodapé e paginação
    for tag in soup.select("form, header, footer, nav, .pagination, .toolbar, .messages"):
        tag.decompose()

    # Frases características de texto de interface — nunca são notícias reais
    UI_SKIP = {
        "mensagem", "pesquisar", "observacao", "inativar",
        "nenhum", "resultados", "de:", "ate:", "numero de dias",
    }

    tabelas = soup.select("table")
    if not tabelas:
        return results

    for tabela in tabelas:
        rows = tabela.select("tr")[1:]
        for row in rows[:MAX_ITEMS]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            titulo = _txt(cells[0])
            titulo_lower = titulo.lower().strip()

            # Descarta linhas de UI
            if len(titulo) < 5 or any(skip in titulo_lower for skip in UI_SKIP):
                continue

            resumo = " | ".join(_txt(c) for c in cells[1:3])
            a = row.find("a")
            link = _abs(a.get("href", "") if a else "", base_url)
            results.append({"titulo": titulo, "resumo": resumo, "link": link})

    return results


def parse_tjpr(soup, acronym, base_url):
    """
    TJPR — captura apenas o conteúdo do asset_publisher (área de notícias),
    ignorando menus laterais, links de YouTube e seções institucionais.
    """
    results = []

    # Remove menus, rodapé, sidebar e qualquer link para YouTube/redes sociais
    for tag in soup.select("nav, header, footer, .portlet-navigation, "
                           ".lfr-nav, .taglib-navigation, aside, "
                           "a[href*='youtube'], a[href*='instagram']"):
        tag.decompose()

    # Foca na área do asset_publisher (conteúdo principal da página)
    area = (
        soup.select_one(".asset-publisher, .portlet-asset-publisher, "
                        "#content, .journal-content-article, main")
        or soup
    )

    # Captura links com texto relevante dentro da área de conteúdo
    SKIP_FRAGMENTS = {
        "tribunal do júri", "2º grau", "notas tjpr", "agenda institucional",
        "notas de falecimento", "youtube", "instagram", "facebook",
    }

    for a in area.select("a[href]")[:MAX_ITEMS]:
        titulo = _txt(a)
        titulo_lower = titulo.lower()
        href = a.get("href", "")

        if href.startswith("javascript") or href.startswith("#"):
            continue
        if len(titulo) < 15:
            continue
        if any(skip in titulo_lower for skip in SKIP_FRAGMENTS):
            continue

        link = _abs(href, base_url)
        results.append({"titulo": titulo, "resumo": "", "link": link})

    return results


# ---------------------------------------------------------------------------
# Parsers — Subsistema 2 (notícias expandidas — novos)
# ---------------------------------------------------------------------------

def parse_rss(soup, acronym, base_url):
    """
    Parser para feeds RSS/Atom (XML).
    Extrai título, link e resumo de cada <item>.
    Usar com parser="rss" no dict de fonte — fetch_page usa lxml-xml nesse caso.
    """
    results = []
    for item in soup.find_all("item")[:MAX_ITEMS]:
        titulo = _txt(item.find("title"))
        # <link> em RSS é texto direto; <guid> serve de fallback
        link_tag = item.find("link")
        link = (link_tag.get_text(strip=True) if link_tag else "").strip()
        if not link:
            guid_tag = item.find("guid")
            link = _txt(guid_tag) if guid_tag else _abs("", base_url)
        resumo_tag = item.find("description") or item.find("summary")
        resumo = _txt(resumo_tag) if resumo_tag else ""
        if titulo and len(titulo) > 10:
            results.append({"titulo": titulo, "resumo": resumo, "link": link or _abs("", base_url)})
    return results


def parse_telegram(soup, acronym, base_url):
    """
    Canal Telegram via preview web (t.me/s/channel).
    Extrai texto e link de cada mensagem do canal.
    Requer Playwright para renderização (JS obrigatório).

    Filtros aplicados:
    - Mensagens com menos de 80 chars são descartadas: cobrem apenas
      links de portais genéricos (ex: "Tribunal X - PJe"), que não
      trazem conteúdo de notícia real e geram entradas repetidas.
    - Mensagens que seguem o padrão "Tribunal * - <sistema>" sem verbo
      de ação são igualmente descartadas.
    """
    import re
    # Padrão de links genéricos de portal sem conteúdo real
    _PADRAO_PORTAL = re.compile(
        r"^tribunal\b.{0,60}\b[-–]\s*(pje|eproc|pdpj|saj)\s*$",
        re.IGNORECASE,
    )

    results = []
    # Cada mensagem fica em .tgme_widget_message_wrap
    messages = soup.select(".tgme_widget_message_wrap")
    if not messages:
        # Fallback: tenta qualquer elemento com texto substancial
        messages = soup.select(".tgme_widget_message")

    for msg in messages[:MAX_ITEMS]:
        text_el = msg.select_one(".tgme_widget_message_text")
        if not text_el:
            continue
        titulo = _txt(text_el)
        # Descarta mensagens muito curtas (links genéricos de portal)
        if len(titulo) < 80:
            continue
        # Descarta mensagens que são apenas "Tribunal X - PJe/eproc/..."
        if _PADRAO_PORTAL.match(titulo):
            continue
        # Link canônico da mensagem (botão de data/hora)
        a_date = msg.select_one("a.tgme_widget_message_date")
        link = _abs(a_date.get("href", "") if a_date else "", base_url)
        results.append({"titulo": titulo[:250], "resumo": "", "link": link})

    return results


# Regex de separação entre entradas do PROJUDI: "DD/MM/AAAA HH:MM" no início de linha
_RE_PROJUDI_ENTRY = re.compile(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})')


def parse_projudi(soup, acronym, base_url):
    """
    Parser para páginas PROJUDI (TJPR, TJRR) que exibem o histórico completo
    de indisponibilidades como um bloco de texto corrido.

    Estratégia:
    - Extrai o texto da área de conteúdo principal.
    - Divide por padrão "DD/MM/AAAA HH:MM" (início de cada entrada).
    - Para cada entrada, constrói: título = "DATA — DESCRIÇÃO", resumo = descrição.
    - Retorna no máximo MAX_ITEMS entradas mais recentes (topo da lista).
    """
    # Foca na área de conteúdo, removendo nav/menus
    for tag in soup.select(_NAV_TAGS):
        tag.decompose()
    area = soup.select_one(
        "main, .main-content, #content, .portlet-body, "
        ".journal-content-article, .asset-full-content, article"
    ) or soup

    texto = area.get_text(separator="\n", strip=True)
    partes = _RE_PROJUDI_ENTRY.split(texto)
    # partes = [texto_antes, data1, corpo1, data2, corpo2, ...]

    if len(partes) < 3:
        # Sem entradas detectadas — fallback ao parser genérico
        return parse_generic_table(soup, acronym, base_url)

    results = []
    i = 1  # índice da primeira data
    while i < len(partes) - 1 and len(results) < MAX_ITEMS:
        data_inicio = partes[i].strip()
        corpo       = partes[i + 1] if i + 1 < len(partes) else ""

        # Extrai a descrição: primeira linha não-vazia após a data-fim e o " - "
        descricao = ""
        for linha in corpo.split("\n"):
            linha = linha.strip()
            if not linha or linha == "a":
                continue
            if _RE_PROJUDI_ENTRY.match(linha):  # data-fim → pula
                continue
            if linha.startswith("- "):
                descricao = linha[2:].strip()
                break
            if len(linha) > 15:
                descricao = linha
                break

        if descricao:
            titulo = f"{data_inicio} — {descricao[:120]}"
            results.append({
                "titulo": titulo,
                "resumo": descricao,
                "link":   base_url,
            })
        i += 2

    return results


# ---------------------------------------------------------------------------
# Mapa unificado de parsers
# ---------------------------------------------------------------------------
PARSERS = {
    # Subsistema 1 — indisponibilidades
    "generic_news":  parse_generic_news,
    "generic_table": parse_generic_table,
    "projudi":       parse_projudi,
    "tjsp":          parse_tjsp,
    "tjmg":          parse_tjmg,
    "tjpr":          parse_tjpr,
    "trf1":          parse_trf1,
    "trf5":          parse_trf5,
    # Subsistema 2 — notícias expandidas
    "telegram":      parse_telegram,
    "rss":           parse_rss,
}

# ---------------------------------------------------------------------------
# Helpers de montagem de notícia
# ---------------------------------------------------------------------------

def _montar_noticia_bruta(item: dict, acronym: str, name: str, grupo: str = "") -> dict:
    """Formato padrão para o Subsistema 1 (indisponibilidades).
    Inclui grupo e tipo para permitir agrupamento unificado no e-mail.
    """
    return {
        "titulo":   item["titulo"],
        "resumo":   item.get("resumo", ""),
        "link":     item["link"],
        "data_obj": datetime.now(timezone.utc).replace(tzinfo=None),
        "fonte":    f"Scraper Direto — {acronym}",
        "grupo":    grupo,
        "tipo":     "Indisponibilidade",
    }


def _montar_noticia_fontes(item: dict, fonte: dict) -> dict:
    """Formato padrão para o Subsistema 2 (notícias expandidas).
    Inclui grupo e tipo para separação na saída do e-mail.
    """
    return {
        "titulo":   item["titulo"],
        "resumo":   item.get("resumo", ""),
        "link":     item["link"],
        "data_obj": datetime.now(timezone.utc).replace(tzinfo=None),
        "fonte":    f"Notícias — {fonte['acronym']}",
        "grupo":    fonte.get("grupo", ""),
        "tipo":     fonte.get("tipo", ""),
    }


# ===========================================================================
# Pipeline Subsistema 1 — buscar_noticias_direto()
# (lógica original preservada sem alterações)
# ===========================================================================

def buscar_noticias_direto(brutas: list | None = None) -> list:
    """
    Ponto de entrada público — chamado pelo main.py.

    Retorna lista de notícias novas no mesmo formato que
    buscar_noticias_semanais() do scraper RSS, pronta para
    ser concatenada e enviada no mesmo e-mail.

    brutas: lista opcional para acumular todos os itens brutos
            (antes do filtro) destinados ao Google Sheets.
    """
    todas_noticias = []
    links_ja_coletados = set()

    log.info("\n%s", "─" * 60)
    log.info("MAST — Motor Secundário: Scraper Direto dos Tribunais")
    log.info("%s", "─" * 60)

    for tribunal in TRIBUNAIS_DIRETO:
        acronym  = tribunal["acronym"]
        name     = tribunal["nome"]
        base_url = tribunal.get("base_url", tribunal["url"])
        parser_key = tribunal.get("parser", "generic_news")

        log.info("▶ [%s] %s", acronym, tribunal["url"])

        soup = fetch_page(tribunal)
        if not soup:
            log.info("  ✗ [%s] Sem conteúdo — ignorado.", acronym)
            continue

        parser_fn = PARSERS.get(parser_key, parse_generic_news)
        itens_brutos = parser_fn(soup, acronym, base_url)
        log.info("  ↳ %d itens brutos coletados.", len(itens_brutos))

        for item in itens_brutos:
            link = item.get("link", "")

            # Deduplica na sessão atual
            if link in links_ja_coletados:
                continue
            links_ja_coletados.add(link)

            noticia_bruta = _montar_noticia_bruta(item, acronym, name, grupo=tribunal.get("grupo", ""))

            # Coleta bruta para Google Sheets (antes do filtro e banco)
            if brutas is not None:
                brutas.append({**noticia_bruta, 'origem': 'Direto', 'termo_buscado': ''})

            # Chave normalizada para deduplicação por conteúdo (cross-run)
            titulo_chave = normalizar_titulo_chave(noticia_bruta["titulo"])

            # Deduplica contra o banco por link exato
            if verificar_status_noticia(link):
                salvar_auditoria(noticia_bruta, "repetido", "Já Existente", "N/A", "N/A", titulo_chave)
                continue

            # Bloqueia o mesmo conteúdo aprovado recentemente com URL diferente
            if titulo_chave and verificar_titulo_chave(titulo_chave, janela_dias=DIAS_JANELA + 1):
                log.debug("Dedup cross-run por título (Direto): '%s'", noticia_bruta["titulo"][:80])
                salvar_auditoria(noticia_bruta, "repetido", "Duplicata de Título (Cross-Run)", "N/A", "N/A", titulo_chave)
                continue

            # Avalia com o filter.py
            status, motivo, palavra, termo = avaliar_noticia(
                noticia_bruta["titulo"],
                noticia_bruta["resumo"],
            )

            # Persiste no banco incluindo titulo_chave para dedup cross-run futuro
            salvar_auditoria(noticia_bruta, status, motivo, palavra, termo, titulo_chave)

            if status == "novo":
                noticia_bruta["palavra_extraida"] = palavra
                noticia_bruta["termo_base"]       = termo
                todas_noticias.append(noticia_bruta)

    todas_noticias.sort(key=lambda x: x["data_obj"], reverse=True)
    log.info("\n✅ Scraper Direto finalizado — %d notícias novas aprovadas.", len(todas_noticias))
    return todas_noticias


# ===========================================================================
# Pipeline Subsistema 2 — buscar_noticias_fontes()
# (notícias expandidas — 34 fontes agrupadas por categoria)
# ===========================================================================

# Labels de exibição para cada grupo
_GRUPOS_LABEL = {
    "Sistemas-CNJ":        "Sistemas e CNJ",
    "Tribunais-Superiores": "Tribunais Superiores e Conselhos",
    "Tribunais-Estaduais":  "Tribunais de Justiça Estaduais",
    "TRFs":                 "Tribunais Regionais Federais",
    "TRTs":                 "Tribunais Regionais do Trabalho",
    "TREs":                 "Tribunais Regionais Eleitorais",
}


def buscar_noticias_fontes() -> dict[str, list]:
    """
    Ponto de entrada público — chamado pelo main.py para o Subsistema 2.

    Retorna um dicionário agrupado por categoria:
    {
        "Sistemas-CNJ":        [...],
        "Tribunais-Superiores": [...],
        "Tribunais-Estaduais":  [...],
        "TRFs":                 [...],
        "TRTs":                 [...],
        "TREs":                 [...],
    }

    Cada item da lista segue o formato padrão do MAST, com campos extras
    "grupo" e "tipo" para uso no template do e-mail.
    """
    # Inicializa grupos na ordem definida
    grupos: dict[str, list] = {g: [] for g in _GRUPOS_LABEL}
    links_ja_coletados: set[str] = set()

    total_fontes  = len(FONTES_NOTICIAS)
    total_puladas = 0

    log.info("\n%s", "═" * 60)
    log.info("MAST — Subsistema 2: Notícias Expandidas (%d fontes)", len(FONTES_NOTICIAS))
    log.info("%s", "═" * 60)

    grupo_atual = None
    for fonte in FONTES_NOTICIAS:
        acronym  = fonte["acronym"]
        grupo    = fonte.get("grupo", "")
        base_url = fonte.get("base_url", fonte["url"])
        parser_key = fonte.get("parser", "generic_news")

        # Imprime separador ao mudar de grupo
        if grupo != grupo_atual:
            grupo_atual = grupo
            label = _GRUPOS_LABEL.get(grupo, grupo)
            log.info("\n  ── %s ──", label)

        # Pula fontes que exigem VPN/rede interna ou estão marcadas como skip
        if fonte.get("vpn_required"):
            log.info("  ⚠️  [%s] Requer VPN/rede interna — ignorado.", acronym)
            total_puladas += 1
            continue
        if fonte.get("skip"):
            motivo = fonte.get("skip_reason", "marcado para pular")
            log.info("  ⏭️  [%s] Ignorado: %s", acronym, motivo)
            total_puladas += 1
            continue

        log.info("  ▶ [%s] %s", acronym, fonte["url"])

        soup = fetch_page(fonte)
        if not soup:
            log.info("     ✗ Sem conteúdo — ignorado.")
            continue

        parser_fn    = PARSERS.get(parser_key, parse_generic_news)
        itens_brutos = parser_fn(soup, acronym, base_url)
        log.info("     ↳ %d itens brutos.", len(itens_brutos))

        for item in itens_brutos:
            link = item.get("link", "")

            if link in links_ja_coletados:
                continue
            links_ja_coletados.add(link)

            noticia = _montar_noticia_fontes(item, fonte)
            titulo_chave = normalizar_titulo_chave(noticia["titulo"])

            # Dedup contra o banco (Fase 1/2) — não salva auditoria da Fase 3
            if verificar_status_noticia(link):
                continue

            if titulo_chave and verificar_titulo_chave(titulo_chave, janela_dias=DIAS_JANELA + 1):
                log.debug("Dedup cross-run (Fontes): '%s'", noticia["titulo"][:80])
                continue

            status, motivo, palavra, termo = avaliar_noticia(
                noticia["titulo"],
                noticia["resumo"],
            )

            # Fase 3 não grava no banco de auditoria — não deve aparecer no CSV/PDF
            if status == "novo":
                noticia["palavra_extraida"] = palavra
                noticia["termo_base"]       = termo
                grupos[grupo].append(noticia)

    # Ordena cada grupo por data decrescente
    for g in grupos:
        grupos[g].sort(key=lambda x: x["data_obj"], reverse=True)

    total_aprovadas = sum(len(v) for v in grupos.values())
    log.info("\n%s", "═" * 60)
    log.info("✅ Subsistema 2 finalizado — %d notícias novas aprovadas", total_aprovadas)
    log.info("   (%d fontes consultadas, %d puladas)", total_fontes - total_puladas, total_puladas)
    for g, label in _GRUPOS_LABEL.items():
        n = len(grupos[g])
        if n:
            log.info("   • %s: %d", label, n)
    log.info("%s", "═" * 60)

    return grupos
