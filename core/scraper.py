# core/scraper.py
import feedparser
import urllib.parse
from datetime import datetime, timedelta
import logging
import time
from config.settings import (
    TRIBUNAIS, FONTES_OFICIAIS,
    TERMOS_ESPECIFICOS, TERMOS_FORTES_TI, TERMOS_BLOQUEADOS,
    DIAS_JANELA, LOTE_DOMINIOS, LOTE_SIGLAS, LOTE_TERMOS, TITULO_MIN_CHARS,
)
from core.filter import avaliar_noticia
from core.database import verificar_status_noticia, salvar_auditoria

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Grupos temáticos extraídos de TERMOS_FORTES_TI (curtos, sem aspas duplas,
# ideais para combinar com site: e siglas sem estourar o limite da URL).
# Cada grupo vira uma query separada para evitar truncamento silencioso.
# ──────────────────────────────────────────────────────────────────────────────
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
    ],
}

# Termos negativos derivados de TERMOS_BLOQUEADOS que fazem sentido como
# exclusão direta na query do Google (operador -"termo").
# Usamos apenas os mais impactantes para não estourar o tamanho da URL.
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


def extrair_dominios_oficiais():
    dominios = set()
    for item in TRIBUNAIS + FONTES_OFICIAIS:
        url = item.get("url", "")
        netloc = urllib.parse.urlparse(url).netloc
        if not netloc or "google" in netloc or "t.me" in netloc:
            continue
        partes = netloc.split('.')
        if len(partes) >= 3 and partes[-1] == 'br' and partes[-2] == 'jus':
            dominio_base = f"{partes[-3]}.jus.br"
            dominios.add(dominio_base)
        else:
            dominios.add(netloc)
    return list(dominios)


def construir_url_rss(query_final: str, data_limite: datetime) -> str:
    """
    Monta a URL do RSS com filtros de data duplos:
      - after:YYYY-MM-DD  → data exata como âncora
      - when:2d           → janela relativa como reforço
    O Google aplica o mais restritivo dos dois.
    Também injeta as exclusões de termos bloqueados diretamente na query.
    """
    after_str = data_limite.strftime("%Y-%m-%d")
    query_com_data = f"{query_final} {EXCLUSOES_STR} after:{after_str} when:2d"
    query_codificada = urllib.parse.quote(query_com_data)

    url = (
        f"https://news.google.com/rss/search"
        f"?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )

    # Alerta se a URL estiver perto do limite de truncamento do Google (~2000 chars)
    if len(url) > 2000:
        log.warning("URL longa (%d chars) — reduza o lote de termos ou domínios.", len(url))

    return url


def _parse_feed_com_retry(url: str, tentativas: int = 3) -> feedparser.FeedParserDict:
    """Faz o parse do feed RSS com backoff exponencial em caso de falha."""
    for tentativa in range(1, tentativas + 1):
        try:
            feed = feedparser.parse(url)
            # bozo=True com entries vazia indica falha real (ex: timeout, HTML em vez de XML)
            if feed.get('bozo') and not feed.entries:
                raise ValueError(f"Feed inválido: {feed.get('bozo_exception')}")
            return feed
        except Exception as exc:
            if tentativa == tentativas:
                log.warning("Feed falhou após %d tentativas: %s", tentativas, exc)
                return feedparser.FeedParserDict(entries=[])
            espera = 2 ** tentativa
            log.debug("Tentativa %d/%d falhou (%s) — aguardando %ds...", tentativa, tentativas, exc, espera)
            time.sleep(espera)
    return feedparser.FeedParserDict(entries=[])


def extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias):
    feed = _parse_feed_com_retry(url_rss)
    for entry in feed.entries:

        # ── Extração robusta da data de publicação ────────────────────
        published = getattr(entry, 'published_parsed', None)
        if published:
            try:
                data_publicacao = datetime.fromtimestamp(time.mktime(published))
            except (TypeError, OverflowError, OSError):
                # Data corrompida: assume agora para não perder a entrada
                data_publicacao = datetime.now()
        else:
            # Sem campo de data: o filtro when:2d no Google já garante recência
            data_publicacao = datetime.now()

        # ── Filtro de data local (segunda barreira, redundante mas seguro) ──
        if data_publicacao < data_limite:
            continue

        if entry.link in links_ja_coletados:
            continue

        link = entry.link
        titulo = entry.title
        resumo = entry.summary if hasattr(entry, 'summary') else ""
        fonte = entry.source.title if hasattr(entry, 'source') else "Google News"

        # Descarta entradas cujo título é apenas o nome do domínio/fonte (RSS sem conteúdo real).
        # Ex: "- tjrj.jus.br" ou "tjsp.jus.br" — menos de 15 chars úteis após remover a fonte.
        titulo_util = titulo.replace(f"- {fonte}", "").replace(fonte, "").strip(" -–")
        if len(titulo_util) < TITULO_MIN_CHARS:
            links_ja_coletados.add(link)
            continue

        noticia_bruta = {
            'titulo': titulo,
            'resumo': resumo,
            'link': link,
            'data_obj': data_publicacao,
            'fonte': fonte,
        }

        # Se já existe no banco, arquiva como repetido e ignora
        if verificar_status_noticia(link):
            salvar_auditoria(noticia_bruta, 'repetido', 'Já Existente', 'N/A', 'N/A')
            links_ja_coletados.add(link)
            continue

        # Desempacota as 4 variáveis do Filtro Profundo
        status, motivo, palavra_extraida, termo_base = avaliar_noticia(titulo, resumo)

        # Salva auditoria completa no banco
        salvar_auditoria(noticia_bruta, status, motivo, palavra_extraida, termo_base)

        if status == 'novo':
            noticia_bruta['palavra_extraida'] = palavra_extraida
            noticia_bruta['termo_base'] = termo_base
            todas_noticias.append(noticia_bruta)

        links_ja_coletados.add(link)


def buscar_noticias_semanais() -> list[dict]:
    todas_noticias: list[dict] = []
    links_ja_coletados: set[str] = set()
    data_limite = datetime.now() - timedelta(days=DIAS_JANELA)

    lista_dominios = extrair_dominios_oficiais()

    lotes_dominios = [
        lista_dominios[i:i + LOTE_DOMINIOS]
        for i in range(0, len(lista_dominios), LOTE_DOMINIOS)
    ]

    siglas = [t["acronym"] for t in TRIBUNAIS]
    lotes_siglas = [
        siglas[i:i + LOTE_SIGLAS]
        for i in range(0, len(siglas), LOTE_SIGLAS)
    ]

    # ── FASE 1: Grupos temáticos × siglas × domínios ─────────────────
    # Cada grupo é uma query pequena e focada, evitando truncamento.
    log.info("Iniciando Fase 1: %d grupos temáticos x %d lotes de siglas x %d lotes de domínios...",
             len(GRUPOS_TERMOS_FORTES), len(lotes_siglas), len(lotes_dominios))

    for nome_grupo, termos in GRUPOS_TERMOS_FORTES.items():
        log.info("  -> Grupo: %s", nome_grupo)
        query_termos = "(" + " OR ".join(termos) + ")"

        for lote_siglas in lotes_siglas:
            query_tribunais = "(" + " OR ".join(f'"{s}"' for s in lote_siglas) + ")"

            for lote_dom in lotes_dominios:
                filtro_dominio = "(" + " OR ".join(f"site:{d}" for d in lote_dom) + ")"
                query_final = f"{query_termos} AND {query_tribunais} AND {filtro_dominio}"
                url_rss = construir_url_rss(query_final, data_limite)
                extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias)
                time.sleep(1.5)

    # ── FASE 2: TERMOS_ESPECIFICOS (frases exatas) × domínios ────────
    # Não combinamos com siglas aqui — as frases já são específicas o suficiente.
    log.info("Iniciando Fase 2: Frases exatas de TERMOS_ESPECIFICOS x domínios...")

    lotes_termos = [
        TERMOS_ESPECIFICOS[i:i + LOTE_TERMOS]
        for i in range(0, len(TERMOS_ESPECIFICOS), LOTE_TERMOS)
    ]

    for lote_termos in lotes_termos:
        query_frases = "(" + " OR ".join(lote_termos) + ")"

        for lote_dom in lotes_dominios:
            filtro_dominio = "(" + " OR ".join(f"site:{d}" for d in lote_dom) + ")"
            query_final = f"{query_frases} AND {filtro_dominio}"
            url_rss = construir_url_rss(query_final, data_limite)
            extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias)
            time.sleep(1.5)

    # ── FASE 3: TERMOS_FORTES_TI sem filtro de domínio ───────────────
    # Busca aberta na web (sem site:), útil para pegar noticias em portais
    # especializados que nao estao na lista de dominios oficiais.
    log.info("Iniciando Fase 3: TERMOS_FORTES_TI sem filtro de domínio (busca aberta)...")

    lotes_fortes = [
        TERMOS_FORTES_TI[i:i + LOTE_TERMOS]
        for i in range(0, len(TERMOS_FORTES_TI), tamanho_lote_fortes)
    ]

    for lote_fortes in lotes_fortes:
        # Termos fortes sao strings simples (sem aspas) — adicionamos aspas aqui
        query_fortes = "(" + " OR ".join(f'"{t}"' for t in lote_fortes) + ")"

        for lote_siglas in lotes_siglas:
            query_tribunais = "(" + " OR ".join(f'"{s}"' for s in lote_siglas) + ")"
            query_final = f"{query_fortes} AND {query_tribunais}"
            url_rss = construir_url_rss(query_final, data_limite)
            extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias)
            time.sleep(1.5)

    todas_noticias.sort(key=lambda x: x['data_obj'], reverse=True)
    log.info("Coleta RSS finalizada. %d notícias novas encontradas.", len(todas_noticias))
    return todas_noticias