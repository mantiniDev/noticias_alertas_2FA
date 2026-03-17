# core/scraper.py
import feedparser
import urllib.parse
from datetime import datetime, timedelta
import time
from config.settings import TRIBUNAIS, FONTES_OFICIAIS, TERMOS_ESPECIFICOS
from core.filter import avaliar_noticia

def extrair_dominios_oficiais():
    dominios = set()
    for item in TRIBUNAIS + FONTES_OFICIAIS:
        url = item.get("url", "")
        netloc = urllib.parse.urlparse(url).netloc
        if not netloc or "google" in netloc:
            continue
        partes = netloc.split('.')
        if len(partes) >= 3 and partes[-1] == 'br' and partes[-2] == 'jus':
            dominio_base = f"{partes[-3]}.jus.br"
            dominios.add(dominio_base)
        else:
            dominios.add(netloc)
    return list(dominios)

def extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias):
    feed = feedparser.parse(url_rss)
    for entry in feed.entries:
        if hasattr(entry, 'published_parsed'):
            data_publicacao = datetime.fromtimestamp(time.mktime(entry.published_parsed))

            if data_publicacao >= data_limite and entry.link not in links_ja_coletados:
                titulo = entry.title
                resumo = entry.summary if hasattr(entry, 'summary') else ""
                
                if avaliar_noticia(titulo, resumo):
                    todas_noticias.append({
                        'titulo': titulo,
                        'resumo': resumo,
                        'link': entry.link,
                        'data_obj': data_publicacao,
                        'fonte': entry.source.title if hasattr(entry, 'source') else "Google News"
                    })
                    links_ja_coletados.add(entry.link)

def buscar_noticias_semanais():
    todas_noticias = []
    links_ja_coletados = set()
    data_limite = datetime.now() - timedelta(days=5)

    lista_dominios = extrair_dominios_oficiais()
    tamanho_lote_dominios = 20
    lotes_dominios = [lista_dominios[i:i + tamanho_lote_dominios] for i in range(0, len(lista_dominios), tamanho_lote_dominios)]

    termos_base_google = (
        '('
        '"PJe" OR "eproc" OR "projudi" OR "e-SAJ" OR "PDPJ" OR '
        '"indisponibilidade" OR "instabilidade" OR "manutenção" OR "fora do ar" OR "lentidão" OR '
        '"2FA" OR "MFA" OR "SSO" OR "ciberataque" OR "hacker" OR "vulnerabilidade" OR "token" OR '
        '"migração" OR "atualização" OR "versão" OR "API" OR "nuvem" OR "datacenter"'
        ')'
    )

    siglas = [tribunal["acronym"] for tribunal in TRIBUNAIS]
    tamanho_lote = 10
    lotes_siglas = [siglas[i:i + tamanho_lote] for i in range(0, len(siglas), tamanho_lote)]

    print(f"Iniciando Fase 1: Varredura de Tribunais diretamente em {len(lista_dominios)} domínios oficiais...")
    for lote_siglas in lotes_siglas:
        query_tribunais = "(" + " OR ".join(f'"{sigla}"' for sigla in lote_siglas) + ")"
        for lote_dom in lotes_dominios:
            filtro_dominio = "(" + " OR ".join(f"site:{d}" for d in lote_dom) + ")"
            query_final = f"{termos_base_google} AND {query_tribunais} AND {filtro_dominio}"
            query_codificada = urllib.parse.quote(query_final)
            url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
            extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias)
            time.sleep(1.5)

    print("Iniciando Fase 2: Busca por frases exatas de TI e Segurança...")
    tamanho_lote_termos = 6
    lotes_termos = [TERMOS_ESPECIFICOS[i:i + tamanho_lote_termos] for i in range(0, len(TERMOS_ESPECIFICOS), tamanho_lote_termos)]

    for lote_termos in lotes_termos:
        query_frases = "(" + " OR ".join(lote_termos) + ")"
        for lote_dom in lotes_dominios:
            filtro_dominio = "(" + " OR ".join(f"site:{d}" for d in lote_dom) + ")"
            query_final = f"{query_frases} AND {filtro_dominio}"
            query_codificada = urllib.parse.quote(query_final)
            url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
            extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias)
            time.sleep(1.5)

    todas_noticias.sort(key=lambda x: x['data_obj'], reverse=True)
    return todas_noticias