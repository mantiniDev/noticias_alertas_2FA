# core/scraper_direto.py
"""
Motor secundário do MAST — dois subsistemas independentes de varredura direta.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Subsistema 1 — TRIBUNAIS_DIRETO  (10 fontes originais)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Varredura de páginas de INDISPONIBILIDADE dos 10 tribunais
  prioritários, com parsers especializados por tribunal.
  Função pública: buscar_noticias_direto()

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Subsistema 2 — FONTES_NOTICIAS  (34 fontes expandidas)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Varredura de páginas de NOTÍCIAS, NORMATIVOS e RELEASES de:
    • Sistemas / CNJ
    • Tribunais Superiores (STF, STJ, TST, CSJT)
    • Tribunais de Justiça Estaduais (TJEs)
    • Tribunais Regionais Federais (TRFs)
    • Tribunais Regionais do Trabalho (TRTs)
  Resultados agrupados por categoria.
  Função pública: buscar_noticias_fontes()

Integração:
  - Usa verificar_status_noticia() e salvar_auditoria() do database.py
    para deduplicação e persistência — mesma lógica do scraper RSS.
  - Usa avaliar_noticia() do filter.py para classificar cada item.
  - Ambas retornam listas no mesmo formato base, prontas para main.py.
"""

import logging
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
# SUBSISTEMA 1 — TRIBUNAIS_DIRETO (10 fontes originais — NÃO ALTERAR)
# Foco: páginas de indisponibilidade com parsers especializados por tribunal
# ===========================================================================
TRIBUNAIS_DIRETO = [
    {
        "acronym": "TJTO",
        "name": "Tribunal de Justiça do Tocantins",
        "url": "https://www.tjto.jus.br/comunicacao/noticias",
        "parser": "generic_news",
        "base_url": "https://www.tjto.jus.br",
    },
    {
        "acronym": "TJSP",
        "name": "Tribunal de Justiça de São Paulo",
        "url": "https://www.tjsp.jus.br/Indisponibilidade/Comunicados",
        "parser": "tjsp",
        "base_url": "https://www.tjsp.jus.br",
    },
    {
        "acronym": "TJRS",
        "name": "Tribunal de Justiça do Rio Grande do Sul",
        "url": "https://www.tjrs.jus.br/novo/processos-e-servicos/consultas-processuais/certidoes-indisponibilidade/",
        "parser": "generic_table",
        "base_url": "https://www.tjrs.jus.br",
    },
    {
        "acronym": "TJMG",
        "name": "Tribunal de Justiça de Minas Gerais",
        "url": "https://www.tjmg.jus.br/pje/certidao-de-indisponibilidade/",
        "parser": "tjmg",
        "base_url": "https://www.tjmg.jus.br",
    },
    {
        "acronym": "TRF1",
        "name": "Tribunal Regional Federal da 1ª Região",
        "url": "https://app.trf1.jus.br/indisponibilidades-relatorio/",
        "parser": "trf1",
        "base_url": "https://portal.trf1.jus.br",
        "force_playwright": True,
        "wait_selector": "table, .mat-row, .cdk-row",
    },
    {
        "acronym": "TJPR",
        "name": "Tribunal de Justiça do Paraná",
        "url": "https://www.tjpr.jus.br/noticias",
        "parser": "tjpr",
        "base_url": "https://www.tjpr.jus.br",
    },
    {
        "acronym": "TRF5",
        "name": "Tribunal Regional Federal da 5ª Região",
        "url": "https://pje.trf5.jus.br/pje/IndisponibilidadeSistema/listView.seam",
        "parser": "trf5",
        "base_url": "https://pje.trf5.jus.br",
    },
    {
        "acronym": "TRT15",
        "name": "TRT 15ª Região (Campinas)",
        "url": "https://trt15.jus.br/pje/indisponibilidade-pje",
        "parser": "generic_table",
        "base_url": "https://trt15.jus.br",
    },
    {
        "acronym": "TJPI",
        "name": "Tribunal de Justiça do Piauí",
        "url": "https://www.tjpi.jus.br/portaltjpi/pje/indisponibilidade-do-sistema/",
        "parser": "generic_news",
        "base_url": "https://www.tjpi.jus.br",
    },
    {
        "acronym": "TJRJ",
        "name": "Tribunal de Justiça do Rio de Janeiro",
        "url": "https://www3.tjrj.jus.br/portalservicos/#/modindpub-principal",
        "parser": "generic_table",
        "base_url": "https://www3.tjrj.jus.br",
        "force_playwright": True,
        "wait_selector": "table, .indisponibilidade, .card",
        "extra_wait": 4,     # segundos extras após networkidle (SPA lento)
    },
]

# ===========================================================================
# SUBSISTEMA 2 — FONTES_NOTICIAS (34 fontes expandidas)
# Foco: notícias institucionais, normativos e releases por categoria
#
# Campos obrigatórios: nome, acronym, url, tipo, grupo, parser, base_url
# Campos opcionais  : force_playwright, wait_selector, extra_wait, vpn_required
# ===========================================================================
FONTES_NOTICIAS = [

    # ── Sistemas e CNJ ──────────────────────────────────────────────────────
    {
        "nome": "Telegram - PJe News",
        "acronym": "PJeNews",
        "url": "https://t.me/s/pjenews",
        "tipo": "Notícias PJe",
        "grupo": "Sistemas-CNJ",
        "parser": "telegram",
        "base_url": "https://t.me",
        "force_playwright": True,
        "wait_selector": ".tgme_widget_message_wrap",
        "extra_wait": 3,
    },
    {
        "nome": "PJe Legacy - Notas da Versão",
        "acronym": "PJeDocs",
        "url": "https://docs.pje.jus.br/servicos-negociais/servico-pje-legacy/notas-da-versao",
        "tipo": "Release Notes",
        "grupo": "Sistemas-CNJ",
        "parser": "generic_news",
        "base_url": "https://docs.pje.jus.br",
    },
    {
        "nome": "CNJ - Notícias PDPJ-Br",
        "acronym": "CNJ-PDPJ",
        "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/plataforma-digital-do-poder-judiciario-brasileiro-pdpj-br/noticias/",
        "tipo": "Notícias",
        "grupo": "Sistemas-CNJ",
        "parser": "generic_news",
        "base_url": "https://www.cnj.jus.br",
    },
    {
        "nome": "CNJ - Notícias Justiça 4.0",
        "acronym": "CNJ-J40",
        "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/justica-4-0/noticias/",
        "tipo": "Notícias",
        "grupo": "Sistemas-CNJ",
        "parser": "generic_news",
        "base_url": "https://www.cnj.jus.br",
    },
    {
        "nome": "CNJ - Atos Normativos",
        "acronym": "CNJ-Norm",
        "url": "https://www.cnj.jus.br/atos_normativos/",
        "tipo": "Normativos",
        "grupo": "Sistemas-CNJ",
        "parser": "generic_news",
        "base_url": "https://www.cnj.jus.br",
    },

    # ── Tribunais Superiores e Conselhos ────────────────────────────────────
    {
        "nome": "STF - Notícias",
        "acronym": "STF",
        "url": "https://noticias.stf.jus.br/",
        "tipo": "Notícias",
        "grupo": "Tribunais-Superiores",
        "parser": "generic_news",
        "base_url": "https://noticias.stf.jus.br",
    },
    {
        "nome": "STJ - Últimas Notícias",
        "acronym": "STJ",
        "url": "https://www.stj.jus.br/sites/portalp/Comunicacao/Ultimas-noticias",
        "tipo": "Notícias",
        "grupo": "Tribunais-Superiores",
        "parser": "generic_news",
        "base_url": "https://www.stj.jus.br",
    },
    {
        "nome": "TST - Notícias",
        "acronym": "TST",
        "url": "https://www.tst.jus.br/noticias",
        "tipo": "Notícias",
        "grupo": "Tribunais-Superiores",
        "parser": "generic_news",
        "base_url": "https://www.tst.jus.br",
    },
    {
        "nome": "CSJT - Normativos",
        "acronym": "CSJT-Norm",
        "url": "https://www.csjt.jus.br/web/csjt/normativos",
        "tipo": "Normativos",
        "grupo": "Tribunais-Superiores",
        "parser": "generic_news",
        "base_url": "https://www.csjt.jus.br",
    },
    {
        "nome": "CSJT - Legislação e Atos",
        "acronym": "CSJT-Leg",
        "url": "https://www.csjt.jus.br/web/csjt/legislacao-atos",
        "tipo": "Normativos",
        "grupo": "Tribunais-Superiores",
        "parser": "generic_news",
        "base_url": "https://www.csjt.jus.br",
    },

    # ── Tribunais de Justiça Estaduais ──────────────────────────────────────
    {
        "nome": "TJSP - Notícias eproc",
        "acronym": "TJSP-Eproc",
        "url": "https://www.tjsp.jus.br/eproc/Noticias",
        "tipo": "Notícias eproc",
        "grupo": "Tribunais-Estaduais",
        "parser": "tjsp",
        "base_url": "https://www.tjsp.jus.br",
    },
    {
        "nome": "TJSP - Notícias Gerais",
        "acronym": "TJSP",
        "url": "https://www.tjsp.jus.br/Noticias",
        "tipo": "Notícias",
        "grupo": "Tribunais-Estaduais",
        "parser": "generic_news",
        "base_url": "https://www.tjsp.jus.br",
    },
    {
        "nome": "TJSP - Comunicados (Precatórios)",
        "acronym": "TJSP-Prec",
        "url": "https://www.tjsp.jus.br/Precatorios/Comunicados?tipoDestino=85",
        "tipo": "Comunicados",
        "grupo": "Tribunais-Estaduais",
        "parser": "tjsp",
        "base_url": "https://www.tjsp.jus.br",
    },
    {
        "nome": "TJMG - Notícias",
        "acronym": "TJMG",
        "url": "https://www.tjmg.jus.br/portal-tjmg/noticias/",
        "tipo": "Notícias",
        "grupo": "Tribunais-Estaduais",
        "parser": "generic_news",
        "base_url": "https://www.tjmg.jus.br",
    },
    {
        "nome": "TJMG - Atos Normativos",
        "acronym": "TJMG-Norm",
        "url": "https://www.tjmg.jus.br/portal-tjmg/atos-normativos/",
        "tipo": "Normativos",
        "grupo": "Tribunais-Estaduais",
        "parser": "tjmg",
        "base_url": "https://www.tjmg.jus.br",
    },
    {
        "nome": "TJRJ - Notícias",
        "acronym": "TJRJ",
        "url": "https://www.tjrj.jus.br/web/guest/noticias",
        "tipo": "Notícias",
        "grupo": "Tribunais-Estaduais",
        "parser": "generic_news",
        "base_url": "https://www.tjrj.jus.br",
    },
    {
        "nome": "TJPR - Notícias",
        "acronym": "TJPR",
        "url": "https://www.tjpr.jus.br/noticias",
        "tipo": "Notícias",
        "grupo": "Tribunais-Estaduais",
        "parser": "tjpr",
        "base_url": "https://www.tjpr.jus.br",
    },
    {
        "nome": "TJPR - Legislação e Atos Normativos",
        "acronym": "TJPR-Norm",
        "url": "https://www.tjpr.jus.br/legislacao-atos-normativos",
        "tipo": "Normativos",
        "grupo": "Tribunais-Estaduais",
        "parser": "generic_news",
        "base_url": "https://www.tjpr.jus.br",
    },
    {
        "nome": "TJRS - Notícias",
        "acronym": "TJRS",
        "url": "https://www.tjrs.jus.br/novo/comunicacao/noticias-do-tjrs/noticias/",
        "tipo": "Notícias",
        "grupo": "Tribunais-Estaduais",
        "parser": "generic_news",
        "base_url": "https://www.tjrs.jus.br",
    },
    {
        "nome": "TJRS - Publicações Administrativas",
        "acronym": "TJRS-Adm",
        "url": "https://www.tjrs.jus.br/novo/jurisprudencia-e-legislacao/publicacoes-administrativas-do-tjrs/",
        "tipo": "Normativos",
        "grupo": "Tribunais-Estaduais",
        "parser": "generic_news",
        "base_url": "https://www.tjrs.jus.br",
    },
    {
        "nome": "TJBA - Agência de Notícias",
        "acronym": "TJBA",
        "url": "https://www.tjba.jus.br/portal/agencia-de-noticias/",
        "tipo": "Notícias",
        "grupo": "Tribunais-Estaduais",
        "parser": "generic_news",
        "base_url": "https://www.tjba.jus.br",
    },

    # ── Tribunais Regionais Federais ─────────────────────────────────────────
    {
        "nome": "TRF1 - Notícias",
        "acronym": "TRF1",
        "url": "https://www.trf1.jus.br/trf1/noticias/",
        "tipo": "Notícias",
        "grupo": "TRFs",
        "parser": "generic_news",
        "base_url": "https://www.trf1.jus.br",
    },
    {
        "nome": "TRF2 - Portal",
        "acronym": "TRF2",
        "url": "https://www.trf2.jus.br/",
        "tipo": "Notícias",
        "grupo": "TRFs",
        "parser": "generic_news",
        "base_url": "https://www.trf2.jus.br",
    },
    {
        "nome": "TRF3 - Últimas Notícias",
        "acronym": "TRF3",
        "url": "https://web.trf3.jus.br/noticias/Noticiar/ExibirUltimasNoticias",
        "tipo": "Notícias",
        "grupo": "TRFs",
        "parser": "generic_news",
        "base_url": "https://web.trf3.jus.br",
    },
    {
        "nome": "TRF4 - Notícias",
        "acronym": "TRF4",
        "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=noticia_portal",
        "tipo": "Notícias",
        "grupo": "TRFs",
        "parser": "generic_news",
        "base_url": "https://www.trf4.jus.br",
    },
    {
        "nome": "TRF4 - Atos Normativos",
        "acronym": "TRF4-Norm",
        "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=ato_normativo_pesquisar",
        "tipo": "Normativos",
        "grupo": "TRFs",
        "parser": "generic_news",
        "base_url": "https://www.trf4.jus.br",
    },
    {
        "nome": "TRF5 - Notícias",
        "acronym": "TRF5",
        "url": "https://www.trf5.jus.br/index.php/noticias",
        "tipo": "Notícias",
        "grupo": "TRFs",
        "parser": "generic_news",
        "base_url": "https://www.trf5.jus.br",
    },
    {
        "nome": "TRF6 - Notícias",
        "acronym": "TRF6",
        "url": "https://portal.trf6.jus.br/noticias/",
        "tipo": "Notícias",
        "grupo": "TRFs",
        "parser": "generic_news",
        "base_url": "https://portal.trf6.jus.br",
    },
    {
        "nome": "TRF6 - Atos Normativos",
        "acronym": "TRF6-Norm",
        "url": "https://portal.trf6.jus.br/atos-normativos/",
        "tipo": "Normativos",
        "grupo": "TRFs",
        "parser": "generic_news",
        "base_url": "https://portal.trf6.jus.br",
    },

    # ── Tribunais Regionais do Trabalho ──────────────────────────────────────
    {
        "nome": "TRT1 - Últimas Notícias",
        "acronym": "TRT1",
        "url": "https://www.trt1.jus.br/ultimas-noticias",
        "tipo": "Notícias",
        "grupo": "TRTs",
        "parser": "generic_news",
        "base_url": "https://www.trt1.jus.br",
    },
    {
        "nome": "TRT1 - Biblioteca Digital (Atos)",
        "acronym": "TRT1-Bib",
        "url": "https://bibliotecadigital.trt1.jus.br/jspui/handle/1001/6",
        "tipo": "Normativos",
        "grupo": "TRTs",
        "parser": "generic_table",
        "base_url": "https://bibliotecadigital.trt1.jus.br",
    },
    {
        "nome": "TRT2 - Notícias",
        "acronym": "TRT2",
        "url": "https://ww2.trt2.jus.br/noticias/noticias",
        "tipo": "Notícias",
        "grupo": "TRTs",
        "parser": "generic_news",
        "base_url": "https://ww2.trt2.jus.br",
    },
    {
        "nome": "TRT3 - Notícias Institucionais",
        "acronym": "TRT3",
        "url": "https://portal.trt3.jus.br/internet/conheca-o-trt/comunicacao/noticias-institucionais",
        "tipo": "Notícias",
        "grupo": "TRTs",
        "parser": "generic_news",
        "base_url": "https://portal.trt3.jus.br",
    },
    {
        "nome": "TRT4 - Notícias",
        "acronym": "TRT4",
        "url": "https://www.trt4.jus.br/portais/trt4/modulos/noticias/todas/0",
        "tipo": "Notícias",
        "grupo": "TRTs",
        "parser": "generic_news",
        "base_url": "https://www.trt4.jus.br",
    },
]

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
    Caso contrário tenta requests; se retornar vazio, cai para Playwright.
    """
    url              = fonte["url"]
    force_playwright = fonte.get("force_playwright", False)
    wait_selector    = fonte.get("wait_selector")
    extra_wait       = fonte.get("extra_wait", 3)

    if force_playwright:
        log.info("  → Playwright forçado (SPA).")
        return _fetch_playwright(url, wait_selector, extra_wait)

    soup = _fetch_requests(url)
    if soup:
        return soup

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
    """Páginas de notícias com articles / h2-h3 links."""
    items = (
        soup.select("article")
        or soup.select(".views-row, .item-list li, .noticia-item")
        or soup.select("h2 a, h3 a, h4 a")
    )
    results = []
    for item in items[:MAX_ITEMS]:
        a = item if item.name == "a" else item.find("a")
        titulo = _txt(a) if a else _txt(item.find(["h2", "h3", "h4"]) or item)
        link   = _abs(a.get("href", "") if a else "", base_url)
        resumo_tag = item.find(["p", "span"], class_=lambda c: c and any(
            k in c.lower() for k in ("resumo", "desc", "summary", "intro", "lead")
        )) if hasattr(item, "find") else None
        resumo = _txt(resumo_tag) if resumo_tag else ""
        if titulo and len(titulo) > 10:
            results.append({"titulo": titulo, "resumo": resumo, "link": link})
    return results


def parse_generic_table(soup, acronym, base_url):
    """Páginas com tabela HTML de indisponibilidades."""
    results = []
    tabelas = soup.select("table")
    if tabelas:
        HEADERS_SKIP = {"sistema", "data", "período", "status", "descrição", "n°", "nº"}
        for tabela in tabelas:
            for row in tabela.select("tr")[1:MAX_ITEMS + 1]:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue
                titulo = _txt(cells[0])
                if not titulo or titulo.lower() in HEADERS_SKIP or len(titulo) < 5:
                    continue
                resumo = " | ".join(_txt(c) for c in cells[1:3]) if len(cells) > 1 else ""
                a = row.find("a")
                link = _abs(a.get("href", "") if a else "", base_url)
                results.append({"titulo": titulo, "resumo": resumo, "link": link})
        return results
    # Fallback: lista de parágrafos
    for item in soup.select("li, p")[:MAX_ITEMS]:
        texto = _txt(item)
        if len(texto) > 20:
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

def parse_telegram(soup, acronym, base_url):
    """
    Canal Telegram via preview web (t.me/s/channel).
    Extrai texto e link de cada mensagem do canal.
    Requer Playwright para renderização (JS obrigatório).
    """
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
        if len(titulo) < 20:
            continue
        # Link canônico da mensagem (botão de data/hora)
        a_date = msg.select_one("a.tgme_widget_message_date")
        link = _abs(a_date.get("href", "") if a_date else "", base_url)
        results.append({"titulo": titulo[:250], "resumo": "", "link": link})

    return results


# ---------------------------------------------------------------------------
# Mapa unificado de parsers
# ---------------------------------------------------------------------------
PARSERS = {
    # Subsistema 1 — indisponibilidades
    "generic_news":  parse_generic_news,
    "generic_table": parse_generic_table,
    "tjsp":          parse_tjsp,
    "tjmg":          parse_tjmg,
    "tjpr":          parse_tjpr,
    "trf1":          parse_trf1,
    "trf5":          parse_trf5,
    # Subsistema 2 — notícias expandidas
    "telegram":      parse_telegram,
}

# ---------------------------------------------------------------------------
# Helpers de montagem de notícia
# ---------------------------------------------------------------------------

def _montar_noticia_bruta(item: dict, acronym: str, name: str) -> dict:
    """Formato padrão para o Subsistema 1 (indisponibilidades)."""
    return {
        "titulo":   item["titulo"],
        "resumo":   item.get("resumo", ""),
        "link":     item["link"],
        "data_obj": datetime.now(timezone.utc).replace(tzinfo=None),
        "fonte":    f"Scraper Direto — {acronym}",
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

def buscar_noticias_direto() -> list:
    """
    Ponto de entrada público — chamado pelo main.py.

    Retorna lista de notícias novas no mesmo formato que
    buscar_noticias_semanais() do scraper RSS, pronta para
    ser concatenada e enviada no mesmo e-mail.
    """
    todas_noticias = []
    links_ja_coletados = set()

    print(f"\n{'─'*60}")
    print("MAST — Motor Secundário: Scraper Direto dos Tribunais")
    print(f"{'─'*60}")

    for tribunal in TRIBUNAIS_DIRETO:
        acronym  = tribunal["acronym"]
        name     = tribunal["name"]
        base_url = tribunal.get("base_url", tribunal["url"])
        parser_key = tribunal.get("parser", "generic_news")

        print(f"▶ [{acronym}] {tribunal['url']}")

        soup = fetch_page(tribunal)
        if not soup:
            print(f"  ✗ [{acronym}] Sem conteúdo — ignorado.")
            continue

        parser_fn = PARSERS.get(parser_key, parse_generic_news)
        itens_brutos = parser_fn(soup, acronym, base_url)
        print(f"  ↳ {len(itens_brutos)} itens brutos coletados.")

        for item in itens_brutos:
            link = item.get("link", "")

            # Deduplica na sessão atual
            if link in links_ja_coletados:
                continue
            links_ja_coletados.add(link)

            noticia_bruta = _montar_noticia_bruta(item, acronym, name)

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
    print(f"\n✅ Scraper Direto finalizado — {len(todas_noticias)} notícias novas aprovadas.")
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
    }

    Cada item da lista segue o formato padrão do MAST, com campos extras
    "grupo" e "tipo" para uso no template do e-mail.
    """
    # Inicializa grupos na ordem definida
    grupos: dict[str, list] = {g: [] for g in _GRUPOS_LABEL}
    links_ja_coletados: set[str] = set()

    total_fontes  = len(FONTES_NOTICIAS)
    total_puladas = 0

    print(f"\n{'═'*60}")
    print("MAST — Subsistema 2: Notícias Expandidas (34 fontes)")
    print(f"{'═'*60}")

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
            print(f"\n  ── {label} ──")

        # Pula fontes que exigem VPN/rede interna
        if fonte.get("vpn_required"):
            print(f"  ⚠️  [{acronym}] Requer VPN/rede interna — ignorado.")
            total_puladas += 1
            continue

        print(f"  ▶ [{acronym}] {fonte['url']}")

        soup = fetch_page(fonte)
        if not soup:
            print(f"     ✗ Sem conteúdo — ignorado.")
            continue

        parser_fn    = PARSERS.get(parser_key, parse_generic_news)
        itens_brutos = parser_fn(soup, acronym, base_url)
        print(f"     ↳ {len(itens_brutos)} itens brutos.")

        for item in itens_brutos:
            link = item.get("link", "")

            if link in links_ja_coletados:
                continue
            links_ja_coletados.add(link)

            noticia = _montar_noticia_fontes(item, fonte)
            titulo_chave = normalizar_titulo_chave(noticia["titulo"])

            if verificar_status_noticia(link):
                salvar_auditoria(noticia, "repetido", "Já Existente", "N/A", "N/A", titulo_chave)
                continue

            if titulo_chave and verificar_titulo_chave(titulo_chave, janela_dias=DIAS_JANELA + 1):
                log.debug("Dedup cross-run (Fontes): '%s'", noticia["titulo"][:80])
                salvar_auditoria(noticia, "repetido", "Duplicata de Título (Cross-Run)", "N/A", "N/A", titulo_chave)
                continue

            status, motivo, palavra, termo = avaliar_noticia(
                noticia["titulo"],
                noticia["resumo"],
            )
            salvar_auditoria(noticia, status, motivo, palavra, termo, titulo_chave)

            if status == "novo":
                noticia["palavra_extraida"] = palavra
                noticia["termo_base"]       = termo
                grupos[grupo].append(noticia)

    # Ordena cada grupo por data decrescente
    for g in grupos:
        grupos[g].sort(key=lambda x: x["data_obj"], reverse=True)

    total_aprovadas = sum(len(v) for v in grupos.values())
    print(f"\n{'═'*60}")
    print(f"✅ Subsistema 2 finalizado — {total_aprovadas} notícias novas aprovadas")
    print(f"   ({total_fontes - total_puladas} fontes consultadas, {total_puladas} puladas)")
    for g, label in _GRUPOS_LABEL.items():
        n = len(grupos[g])
        if n:
            print(f"   • {label}: {n}")
    print(f"{'═'*60}")

    return grupos
