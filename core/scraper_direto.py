# core/scraper_direto.py
"""
Motor secundário do MAST — varredura direta das páginas de indisponibilidade
dos 10 tribunais prioritários, sem depender de indexadores de busca.

Estratégia de coleta:
  1. requests + BeautifulSoup  (rápido, sem overhead)
  2. Playwright headless        (fallback automático para SPAs com JS)

Integração:
  - Usa verificar_status_noticia() e salvar_auditoria() do database.py
    para deduplicação e persistência — mesma lógica do scraper RSS.
  - Usa avaliar_noticia() do filter.py para classificar cada item.
  - Retorna lista no mesmo formato que buscar_noticias_semanais(),
    permitindo que main.py una os resultados sem distinção.
"""

import logging
import time
import warnings
from datetime import datetime, timezone

import requests
import urllib3
from bs4 import BeautifulSoup

from core.filter import avaliar_noticia
from core.database import verificar_status_noticia, salvar_auditoria

warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT  = 15
PLAYWRIGHT_TIMEOUT = 25_000   # ms — aumentado para sites lentos (TJRJ)
MAX_ITEMS        = 30         # máx de itens brutos por tribunal

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ---------------------------------------------------------------------------
# Tribunais-alvo com estratégias de parse
# ---------------------------------------------------------------------------
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
        "url": "https://www.tjpr.jus.br/home/-/asset_publisher/A2gt/content/id/5924367",
        "parser": "generic_news",
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

# ---------------------------------------------------------------------------
# Camada de fetch
# ---------------------------------------------------------------------------

def _fetch_requests(url: str):
    """Baixa página via requests. Retorna BeautifulSoup ou None."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
        resp.raise_for_status()
        if len(resp.text) < 400:
            return None
        return BeautifulSoup(resp.text, "lxml")
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


def fetch_page(tribunal: dict):
    """
    Orquestra a tentativa de fetch.
    force_playwright=True → vai direto pro Playwright (SPA conhecida).
    Caso contrário tenta requests; se retornar vazio, cai para Playwright.
    """
    url             = tribunal["url"]
    force_playwright = tribunal.get("force_playwright", False)
    wait_selector   = tribunal.get("wait_selector")
    extra_wait      = tribunal.get("extra_wait", 3)

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
# Parsers por tribunal
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
    Após renderização, extrai texto da área de relatório
    (parágrafo descritivo + tabela de registros).
    """
    results = []
    # Remove menus
    for tag in soup.select("nav, header, footer, mat-sidenav"):
        tag.decompose()

    tabelas = soup.select("table, mat-table")
    if tabelas:
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
        if results:
            return results

    # Fallback: captura blocos de texto relevantes (descrição da página)
    for p in soup.select("p, li")[:MAX_ITEMS]:
        texto = _txt(p)
        if len(texto) > 30:
            a = p.find("a")
            link = _abs(a.get("href", "") if a else "", base_url)
            results.append({"titulo": texto[:150], "resumo": texto, "link": link})
    return results


def parse_trf5(soup, acronym, base_url):
    """
    TRF5 — extrai apenas linhas da tabela de indisponibilidades,
    ignorando o formulário de pesquisa e mensagens de interface.
    """
    results = []
    # Remove cabeçalho, formulário e paginação
    for tag in soup.select("form, header, footer, nav, .pagination, .toolbar"):
        tag.decompose()

    tabelas = soup.select("table")
    if tabelas:
        for tabela in tabelas:
            rows = tabela.select("tr")[1:]
            for row in rows[:MAX_ITEMS]:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                # Colunas típicas: [número/data, sistema, descrição, período]
                titulo = _txt(cells[0])
                resumo = " | ".join(_txt(c) for c in cells[1:3])
                # Ignora linhas que são só UI (ex: mensagem de "Nenhum registro")
                if len(titulo) < 5 or "nenhum" in titulo.lower():
                    continue
                a = row.find("a")
                link = _abs(a.get("href", "") if a else "", base_url)
                results.append({"titulo": titulo, "resumo": resumo, "link": link})
    return results


# Mapa de parsers
PARSERS = {
    "generic_news":  parse_generic_news,
    "generic_table": parse_generic_table,
    "tjsp":          parse_tjsp,
    "tjmg":          parse_tjmg,
    "trf1":          parse_trf1,
    "trf5":          parse_trf5,
}

# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def _montar_noticia_bruta(item: dict, acronym: str, name: str) -> dict:
    """Converte o dict cru do parser para o formato padrão do MAST."""
    return {
        "titulo":   item["titulo"],
        "resumo":   item.get("resumo", ""),
        "link":     item["link"],
        "data_obj": datetime.now(timezone.utc).replace(tzinfo=None),
        "fonte":    f"Scraper Direto — {acronym}",
    }


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

            # Deduplica contra o banco persistente
            if verificar_status_noticia(link):
                salvar_auditoria(noticia_bruta, "repetido", "Já Existente", "N/A", "N/A")
                continue

            # Avalia com o filter.py
            status, motivo, palavra, termo = avaliar_noticia(
                noticia_bruta["titulo"],
                noticia_bruta["resumo"],
            )

            # Persiste no banco (mesma estrutura que o scraper RSS)
            salvar_auditoria(noticia_bruta, status, motivo, palavra, termo)

            if status == "novo":
                noticia_bruta["palavra_extraida"] = palavra
                noticia_bruta["termo_base"]       = termo
                todas_noticias.append(noticia_bruta)

    todas_noticias.sort(key=lambda x: x["data_obj"], reverse=True)
    print(f"\n✅ Scraper Direto finalizado — {len(todas_noticias)} notícias novas aprovadas.")
    return todas_noticias