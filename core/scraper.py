# core/scraper.py
import feedparser
import urllib.parse
from datetime import datetime, timedelta
import time
from config.settings import TRIBUNAIS, FONTES_OFICIAIS, TERMOS_ESPECIFICOS
from core.filter import avaliar_noticia
from core.database import verificar_status_noticia, salvar_auditoria


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
            # ... dentro da função extrair_noticias_do_feed ...
            if data_publicacao >= data_limite and entry.link not in links_ja_coletados:
                link = entry.link
                titulo = entry.title
                resumo = entry.summary if hasattr(entry, 'summary') else ""
                fonte = entry.source.title if hasattr(entry, 'source') else "Google News"
                
                noticia_bruta = {
                    'titulo': titulo,
                    'resumo': resumo,
                    'link': link,
                    'data_obj': data_publicacao,
                    'fonte': fonte
                }
                
                # Se já existe no banco, arquiva como repetido e ignora
                if verificar_status_noticia(link):
                    salvar_auditoria(noticia_bruta, 'repetido', 'Já Existente', 'N/A', 'N/A')
                    links_ja_coletados.add(link)
                    continue
                
                # Desempacota as 4 variáveis do novo Filtro Profundo
                status, motivo, palavra_extraida, termo_base = avaliar_noticia(titulo, resumo)
                
                # Salva a auditoria completa no banco
                salvar_auditoria(noticia_bruta, status, motivo, palavra_extraida, termo_base)
                
                if status == 'novo':
                    noticia_bruta['palavra_extraida'] = palavra_extraida
                    noticia_bruta['termo_base'] = termo_base
                    todas_noticias.append(noticia_bruta)
                
                links_ja_coletados.add(link)


def buscar_noticias_semanais():
    todas_noticias = []
    links_ja_coletados = set()
    data_limite = datetime.now() - timedelta(days=2)

    lista_dominios = extrair_dominios_oficiais()
    tamanho_lote_dominios = 20
    lotes_dominios = [lista_dominios[i:i + tamanho_lote_dominios]
                      for i in range(0, len(lista_dominios), tamanho_lote_dominios)]

    termos_base_google = (
        '('
        # 1. Sistemas Judiciais Principais
        '"PJe" OR "eproc" OR "projudi" OR "e-SAJ" OR "PDPJ" OR "Plataforma Digital" OR "js.br" OR "Jus.br" OR "Codex" OR "Integração MNI" OR "API Unificada" OR "Tribunal de Justiça" OR "Tribunal Regional Federal" OR "Tribunal Regional do Trabalho" OR "Tribunal de Contas" OR "Tribunal Militar" OR "Tribunal Eleitoral" OR "Conselho Nacional de Justiça" OR "CNJ" OR "processo eletrônico" OR "sistema judicial" OR "sistema de justiça" OR "sistema de tribunais" OR "sistema de processos judiciais" OR "sistema de gestão judicial" OR "sistema de automação judicial" OR "sistema de tramitação processual" OR "sistema de acompanhamento processual" OR "sistema de consulta processual" OR "sistema de peticionamento eletrônico" OR "sistema de intimação eletrônica" OR "sistema de audiência virtual" OR "sistema de videoconferência judicial" OR "sistema de mediação online" OR "sistema de conciliação online" OR "sistema de arbitragem online" OR "sistema de jurisdição voluntária online" OR "sistema de execução online" OR "sistema de cumprimento online"'
        
        # 2. Incidentes, Quedas e Ameaças
        '"indisponibilidade" OR "instabilidade" OR "ciberataque" OR "ataque hacker" OR "vulnerabilidade" OR "erro de acesso" OR "incidente" OR "falso advogado" OR '
        
        # 3. Autenticação e Segurança (MFA/Identity)
        '"2FA" OR "MFA" OR "duplo fator" OR "SSO" OR "WebAuthn" OR "FIDO2" OR "Captcha" OR "WAF" OR "token" OR '
        
        # 4. Infraestrutura, Manutenção e Atualizações (DevOps/SRE)
        '"datacenter" OR "nuvem" OR "manutenção emergencial" OR "hotfix" OR "patch" OR "release notes" OR "API"'
        ')'
    ) 

    siglas = [tribunal["acronym"] for tribunal in TRIBUNAIS]
    tamanho_lote = 10
    lotes_siglas = [siglas[i:i + tamanho_lote]
                    for i in range(0, len(siglas), tamanho_lote)]

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
    lotes_termos = [TERMOS_ESPECIFICOS[i:i + tamanho_lote_termos]
                    for i in range(0, len(TERMOS_ESPECIFICOS), tamanho_lote_termos)]

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