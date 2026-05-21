# core/scraper_v2.py
"""
Scraper RSS do MAST v2.

Diferenças em relação ao v1:
  - Sem filtro (avaliar_noticia), sem banco de dados.
  - Deduplicação apenas por link dentro da mesma execução.
  - Campo 'termo_buscado' preenchido com o grupo/termo da query.
  - Campo 'origem' = "RSS".
"""

import feedparser
import re
import urllib.parse
from datetime import datetime, timedelta
import logging
import time

from config.settings import (
    TRIBUNAIS, FONTES_OFICIAIS,
    TERMOS_ESPECIFICOS, TERMOS_FORTES_TI,
    DIAS_JANELA, LOTE_DOMINIOS, LOTE_SIGLAS, LOTE_TERMOS, TITULO_MIN_CHARS,
    TITULOS_PAGINAS_GENERICAS,
)

_RE_FONTE_DOMINIO = re.compile(r'^[\w][\w.-]+\.[a-z]{2,6}(\.[a-z]{2})?$', re.IGNORECASE)
_RE_TITULO_SISTEMA = re.compile(
    "(" + "|".join(TITULOS_PAGINAS_GENERICAS) + ")",
    re.IGNORECASE,
)

log = logging.getLogger(__name__)

GRUPOS_TERMOS_FORTES = {
    "sistemas_judiciais": [
        '"PJe"', '"eproc"', '"projudi"', '"eSAJ"', '"PDPJ"',
    ],
    "autenticacao_seguranca": [
        '"2FA"', '"MFA"', '"duplo fator"', '"dois fatores"',
        '"multifator"', '"authenticator"', '"SSO"', '"captcha"',
        '"WAF"', '"token"',
    ],
    "incidentes": [
        '"ciberataque"', '"ataque hacker"', '"ransomware"',
        '"instabilidade"', '"indisponibilidade"', '"fora do ar"',
    ],
    "normativos": [
        '"portaria nº 140"', '"resolução nº 335"',
        '"certificado digital"', '"golpe do advogado"',
        '"TOTP"', '"WebAuthn"', '"FIDO2"',
    ],
}

EXCLUSOES_GOOGLE = [
    '-"processo seletivo"',
    '-"concurso"',
    '-"receita federal"',
    '-"imposto de renda"',
    '-"indisponibilidade de bens"',
    '-"bloqueio de bens"',
    '-"local de votação"',
    '-"semana da mulher"',
    '-"semana da justiça"',
]
EXCLUSOES_STR = " ".join(EXCLUSOES_GOOGLE)


def _remover_acentos(texto: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("ascii")


def extrair_dominios_oficiais() -> list[str]:
    dominios = set()
    for item in TRIBUNAIS + FONTES_OFICIAIS:
        url = item.get("url", "")
        netloc = urllib.parse.urlparse(url).netloc
        if not netloc or "google" in netloc or "t.me" in netloc:
            continue
        partes = netloc.split(".")
        if len(partes) >= 3 and partes[-1] == "br" and partes[-2] == "jus":
            dominios.add(f"{partes[-3]}.jus.br")
        else:
            dominios.add(netloc)
    return list(dominios)


def _construir_url_rss(query_final: str, data_limite: datetime) -> str:
    after_str = data_limite.strftime("%Y-%m-%d")
    query_com_data = f"{query_final} {EXCLUSOES_STR} after:{after_str} when:2d"
    query_codificada = urllib.parse.quote(query_com_data)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )
    if len(url) > 2000:
        log.warning("URL longa (%d chars) — reduza o lote.", len(url))
    return url


def _parse_feed_com_retry(url: str, tentativas: int = 3) -> feedparser.FeedParserDict:
    for tentativa in range(1, tentativas + 1):
        try:
            feed = feedparser.parse(url)
            if feed.get("bozo") and not feed.entries:
                raise ValueError(f"Feed inválido: {feed.get('bozo_exception')}")
            return feed
        except Exception as exc:
            if tentativa == tentativas:
                log.warning("Feed falhou após %d tentativas: %s", tentativas, exc)
                return feedparser.FeedParserDict(entries=[])
            time.sleep(2 ** tentativa)
    return feedparser.FeedParserDict(entries=[])


def _extrair_noticias_do_feed(
    url_rss: str,
    data_limite: datetime,
    links_coletados: set,
    todas_noticias: list,
    termo_buscado: str,
) -> None:
    feed = _parse_feed_com_retry(url_rss)
    for entry in feed.entries:
        published = getattr(entry, "published_parsed", None)
        try:
            data_pub = datetime.fromtimestamp(time.mktime(published)) if published else datetime.now()
        except (TypeError, OverflowError, OSError):
            data_pub = datetime.now()

        if data_pub < data_limite:
            continue

        link = getattr(entry, "link", "")
        if not link or link in links_coletados:
            continue

        titulo = getattr(entry, "title", "").strip()
        resumo = getattr(entry, "summary", "") if hasattr(entry, "summary") else ""
        fonte = entry.source.title if hasattr(entry, "source") else "Google News"

        titulo_util = titulo.replace(f"- {fonte}", "").replace(fonte, "").strip(" -–")
        if len(titulo_util) < TITULO_MIN_CHARS:
            links_coletados.add(link)
            continue

        titulo_norm = _remover_acentos(titulo_util.lower())
        if _RE_FONTE_DOMINIO.match(fonte) and _RE_TITULO_SISTEMA.search(titulo_norm):
            links_coletados.add(link)
            continue

        links_coletados.add(link)
        todas_noticias.append({
            "titulo":        titulo,
            "resumo":        resumo,
            "link":          link,
            "data_obj":      data_pub,
            "fonte":         fonte,
            "termo_buscado": termo_buscado,
            "origem":        "RSS",
        })


def buscar_noticias_rss() -> list[dict]:
    todas_noticias: list[dict] = []
    links_coletados: set[str] = set()
    data_limite = datetime.now() - timedelta(days=DIAS_JANELA)

    lista_dominios = extrair_dominios_oficiais()
    lotes_dominios = [lista_dominios[i:i + LOTE_DOMINIOS] for i in range(0, len(lista_dominios), LOTE_DOMINIOS)]

    siglas = [t["acronym"] for t in TRIBUNAIS]
    lotes_siglas = [siglas[i:i + LOTE_SIGLAS] for i in range(0, len(siglas), LOTE_SIGLAS)]

    # Fase 1: grupos temáticos × siglas × domínios
    log.info("RSS Fase 1: %d grupos x %d lotes siglas x %d lotes domínios",
             len(GRUPOS_TERMOS_FORTES), len(lotes_siglas), len(lotes_dominios))

    for nome_grupo, termos in GRUPOS_TERMOS_FORTES.items():
        log.info("  Grupo: %s", nome_grupo)
        query_termos = "(" + " OR ".join(termos) + ")"
        for lote_siglas in lotes_siglas:
            query_tribunais = "(" + " OR ".join(f'"{s}"' for s in lote_siglas) + ")"
            for lote_dom in lotes_dominios:
                filtro_dominio = "(" + " OR ".join(f"site:{d}" for d in lote_dom) + ")"
                query_final = f"{query_termos} AND {query_tribunais} AND {filtro_dominio}"
                url_rss = _construir_url_rss(query_final, data_limite)
                _extrair_noticias_do_feed(url_rss, data_limite, links_coletados, todas_noticias, nome_grupo)
                time.sleep(1.5)

    # Fase 2: termos específicos (frases exatas) × domínios
    log.info("RSS Fase 2: frases exatas x domínios")
    lotes_termos = [TERMOS_ESPECIFICOS[i:i + LOTE_TERMOS] for i in range(0, len(TERMOS_ESPECIFICOS), LOTE_TERMOS)]
    for lote_termos in lotes_termos:
        query_frases = "(" + " OR ".join(lote_termos) + ")"
        for lote_dom in lotes_dominios:
            filtro_dominio = "(" + " OR ".join(f"site:{d}" for d in lote_dom) + ")"
            query_final = f"{query_frases} AND {filtro_dominio}"
            url_rss = _construir_url_rss(query_final, data_limite)
            termo_repr = " | ".join(t.strip('"') for t in lote_termos[:2])
            _extrair_noticias_do_feed(url_rss, data_limite, links_coletados, todas_noticias, f"especifico: {termo_repr}")
            time.sleep(1.5)

    # Fase 3: termos fortes sem filtro de domínio (busca aberta)
    log.info("RSS Fase 3: termos fortes sem domínio")
    lotes_fortes = [TERMOS_FORTES_TI[i:i + LOTE_TERMOS] for i in range(0, len(TERMOS_FORTES_TI), LOTE_TERMOS)]
    for lote_fortes in lotes_fortes:
        query_fortes = "(" + " OR ".join(f'"{t}"' for t in lote_fortes) + ")"
        for lote_siglas in lotes_siglas:
            query_tribunais = "(" + " OR ".join(f'"{s}"' for s in lote_siglas) + ")"
            query_final = f"{query_fortes} AND {query_tribunais}"
            url_rss = _construir_url_rss(query_final, data_limite)
            termo_repr = " | ".join(lote_fortes[:2])
            _extrair_noticias_do_feed(url_rss, data_limite, links_coletados, todas_noticias, f"forte: {termo_repr}")
            time.sleep(1.5)

    todas_noticias.sort(key=lambda x: x["data_obj"], reverse=True)
    log.info("RSS finalizado — %d notícias coletadas.", len(todas_noticias))
    return todas_noticias
