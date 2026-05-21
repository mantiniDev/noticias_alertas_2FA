# core/scraper_direto_v2.py
"""
Scraper Direto do MAST v2 — varredura dos portais de indisponibilidade
dos 10 tribunais prioritários.

Diferenças em relação ao v1:
  - Sem filtro (avaliar_noticia), sem banco de dados.
  - Deduplicação apenas por link dentro da execução.
  - Campo 'origem' = "Direto" em todos os resultados.
  - Campo 'termo_buscado' = "" (scraper direto não usa termos de busca).
"""

import logging
import time
import warnings
from datetime import datetime, timezone

import requests
import urllib3
from bs4 import BeautifulSoup

from config.settings import REQUEST_TIMEOUT, PLAYWRIGHT_TIMEOUT, MAX_ITEMS

warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

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
        "extra_wait": 4,
    },
]

# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def _fetch_requests(url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=True)
        resp.raise_for_status()
        if len(resp.text) < 400:
            return None
        return BeautifulSoup(resp.text, "lxml")
    except requests.exceptions.SSLError:
        log.warning("SSL inválido em %s — retentando sem verificação.", url)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
            resp.raise_for_status()
            if len(resp.text) < 400:
                return None
            return BeautifulSoup(resp.text, "lxml")
        except Exception as exc:
            log.debug("requests falhou (sem SSL) %s: %s", url, exc)
            return None
    except Exception as exc:
        log.debug("requests falhou %s: %s", url, exc)
        return None


def _fetch_playwright(url: str, wait_selector: str = None, extra_wait: int = 3):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(user_agent=HEADERS["User-Agent"], locale="pt-BR")
            page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="networkidle")
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10_000)
                except Exception:
                    pass
            if extra_wait:
                time.sleep(extra_wait)
            html = page.content()
            browser.close()
        return BeautifulSoup(html, "lxml")
    except Exception as exc:
        log.warning("Playwright falhou para %s: %s", url, exc)
        return None


def fetch_page(tribunal: dict):
    url = tribunal["url"]
    force_playwright = tribunal.get("force_playwright", False)
    wait_selector = tribunal.get("wait_selector")
    extra_wait = tribunal.get("extra_wait", 3)

    if force_playwright:
        return _fetch_playwright(url, wait_selector, extra_wait)

    soup = _fetch_requests(url)
    if soup:
        return soup
    return _fetch_playwright(url, wait_selector, extra_wait)

# ---------------------------------------------------------------------------
# Helpers
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
# Parsers
# ---------------------------------------------------------------------------

def parse_generic_news(soup, acronym, base_url):
    items = (
        soup.select("article")
        or soup.select(".views-row, .item-list li, .noticia-item")
        or soup.select("h2 a, h3 a, h4 a")
    )
    results = []
    for item in items[:MAX_ITEMS]:
        a = item if item.name == "a" else item.find("a")
        titulo = _txt(a) if a else _txt(item.find(["h2", "h3", "h4"]) or item)
        link = _abs(a.get("href", "") if a else "", base_url)
        resumo_tag = item.find(["p", "span"], class_=lambda c: c and any(
            k in c.lower() for k in ("resumo", "desc", "summary", "intro", "lead")
        )) if hasattr(item, "find") else None
        resumo = _txt(resumo_tag) if resumo_tag else ""
        if titulo and len(titulo) > 10:
            results.append({"titulo": titulo, "resumo": resumo, "link": link})
    return results


def parse_generic_table(soup, acronym, base_url):
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
    for item in soup.select("li, p")[:MAX_ITEMS]:
        texto = _txt(item)
        if len(texto) > 20:
            a = item.find("a")
            link = _abs(a.get("href", "") if a else "", base_url)
            results.append({"titulo": texto[:150], "resumo": texto, "link": link})
    return results


def parse_tjsp(soup, acronym, base_url):
    results = []
    rows = soup.select("table tr")
    if rows:
        for row in rows[1:MAX_ITEMS + 1]:
            cells = row.find_all("td")
            if not cells:
                continue
            a = row.find("a")
            titulo = _txt(a) if a else _txt(cells[0])
            link = _abs(a.get("href", "") if a else "", base_url)
            resumo = _txt(cells[1]) if len(cells) > 1 else ""
            if titulo and len(titulo) > 10:
                results.append({"titulo": titulo, "resumo": resumo, "link": link})
        if results:
            return results
    for a in soup.select("a[href*='Comunicado'], a[href*='comunicado']")[:MAX_ITEMS]:
        titulo = _txt(a)
        link = _abs(a.get("href", ""), base_url)
        parent = a.parent
        resumo = _txt(parent) if parent and parent.name not in ("html", "body", "nav") else ""
        if titulo and len(titulo) > 10:
            results.append({"titulo": titulo, "resumo": resumo, "link": link})
    return results


def parse_tjmg(soup, acronym, base_url):
    results = []
    for tag in soup.select("nav, header, footer, .menu, .navbar"):
        tag.decompose()
    main = soup.select_one("main, .main-content, #content, .content, article")
    area = main or soup
    tabelas = area.select("table")
    if tabelas:
        return parse_generic_table(area, acronym, base_url)
    for a in area.select("a[href]")[:MAX_ITEMS]:
        titulo = _txt(a)
        href = a.get("href", "")
        if href.startswith("javascript") or href.startswith("#"):
            continue
        if len(titulo) < 10:
            continue
        results.append({"titulo": titulo, "resumo": "", "link": _abs(href, base_url)})
    return results


def parse_trf1(soup, acronym, base_url):
    results = []
    for tag in soup.select("nav, header, footer, mat-sidenav, mat-toolbar"):
        tag.decompose()
    tabelas = soup.select("table, mat-table")
    if not tabelas:
        return results
    for tabela in tabelas:
        rows = tabela.select("tr, mat-row, .cdk-row")
        for row in rows[1:MAX_ITEMS + 1]:
            cells = row.find_all(["td", "mat-cell", "th"])
            if not cells:
                continue
            titulo = _txt(cells[0])
            if len(titulo) < 5:
                continue
            resumo = " | ".join(_txt(c) for c in cells[1:3]) if len(cells) > 1 else ""
            a = row.find("a")
            link = _abs(a.get("href", "") if a else "", base_url)
            results.append({"titulo": titulo, "resumo": resumo, "link": link})
    return results


def parse_trf5(soup, acronym, base_url):
    results = []
    for tag in soup.select("form, header, footer, nav, .pagination, .toolbar, .messages"):
        tag.decompose()
    UI_SKIP = {"mensagem", "pesquisar", "observacao", "inativar", "nenhum", "resultados", "de:", "ate:", "numero de dias"}
    tabelas = soup.select("table")
    if not tabelas:
        return results
    for tabela in tabelas:
        for row in tabela.select("tr")[1:][:MAX_ITEMS]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            titulo = _txt(cells[0])
            titulo_lower = titulo.lower().strip()
            if len(titulo) < 5 or any(skip in titulo_lower for skip in UI_SKIP):
                continue
            resumo = " | ".join(_txt(c) for c in cells[1:3])
            a = row.find("a")
            link = _abs(a.get("href", "") if a else "", base_url)
            results.append({"titulo": titulo, "resumo": resumo, "link": link})
    return results


def parse_tjpr(soup, acronym, base_url):
    results = []
    for tag in soup.select("nav, header, footer, .portlet-navigation, .lfr-nav, .taglib-navigation, aside, "
                           "a[href*='youtube'], a[href*='instagram']"):
        tag.decompose()
    area = (
        soup.select_one(".asset-publisher, .portlet-asset-publisher, #content, .journal-content-article, main")
        or soup
    )
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
        results.append({"titulo": titulo, "resumo": "", "link": _abs(href, base_url)})
    return results


PARSERS = {
    "generic_news":  parse_generic_news,
    "generic_table": parse_generic_table,
    "tjsp":          parse_tjsp,
    "tjmg":          parse_tjmg,
    "tjpr":          parse_tjpr,
    "trf1":          parse_trf1,
    "trf5":          parse_trf5,
}

# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def buscar_noticias_direto() -> list[dict]:
    todas_noticias: list[dict] = []
    links_coletados: set[str] = set()

    log.info("Scraper Direto v2 iniciado — %d tribunais.", len(TRIBUNAIS_DIRETO))

    for tribunal in TRIBUNAIS_DIRETO:
        acronym = tribunal["acronym"]
        base_url = tribunal.get("base_url", tribunal["url"])
        parser_key = tribunal.get("parser", "generic_news")

        log.info("[%s] %s", acronym, tribunal["url"])

        soup = fetch_page(tribunal)
        if not soup:
            log.warning("[%s] Sem conteúdo — ignorado.", acronym)
            continue

        parser_fn = PARSERS.get(parser_key, parse_generic_news)
        itens_brutos = parser_fn(soup, acronym, base_url)
        log.info("[%s] %d itens brutos.", acronym, len(itens_brutos))

        for item in itens_brutos:
            link = item.get("link", "")
            if not link or link in links_coletados:
                continue
            links_coletados.add(link)

            todas_noticias.append({
                "titulo":        item["titulo"],
                "resumo":        item.get("resumo", ""),
                "link":          link,
                "data_obj":      datetime.now(timezone.utc).replace(tzinfo=None),
                "fonte":         f"Scraper Direto — {acronym}",
                "termo_buscado": "",
                "origem":        "Direto",
            })

    todas_noticias.sort(key=lambda x: x["data_obj"], reverse=True)
    log.info("Scraper Direto finalizado — %d itens coletados.", len(todas_noticias))
    return todas_noticias
