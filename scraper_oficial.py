import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import urllib3
import time

# Desativa avisos de certificado SSL (Muitos sites .jus.br têm problemas de certificado)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
# 1. CONSTANTES E CONFIGURAÇÕES
# ==============================================================================

FONTES_OFICIAIS = [
    # --- Sistemas e CNJ ---
    {"nome": "Telegram - PJe News", "url": "https://t.me/s/pjenews", "tipo": "Telegram"},
    {"nome": "PJe Legacy - Notas da Versão", "url": "https://docs.pje.jus.br/servicos-negociais/servico-pje-legacy/notas-da-versao", "tipo": "Web"},
    {"nome": "CNJ - Notícias PDPJ-Br", "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/plataforma-digital-do-poder-judiciario-brasileiro-pdpj-br/noticias/", "tipo": "Web"},
    {"nome": "CNJ - Notícias Justiça 4.0", "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/justica-4-0/noticias/", "tipo": "Web"},
    {"nome": "CNJ - Atos Normativos", "url": "https://www.cnj.jus.br/atos_normativos/", "tipo": "Web"},

    # --- Tribunais Superiores e Conselhos ---
    {"nome": "STF - Notícias", "url": "https://noticias.stf.jus.br/", "tipo": "Web"},
    {"nome": "STJ - Últimas Notícias", "url": "https://www.stj.jus.br/sites/portalp/Comunicacao/Ultimas-noticias", "tipo": "Web"},
    {"nome": "TST - Notícias", "url": "https://www.tst.jus.br/noticias", "tipo": "Web"},
    {"nome": "CSJT - Normativos", "url": "https://www.csjt.jus.br/web/csjt/normativos", "tipo": "Web"},
    {"nome": "CSJT - Legislação e Atos", "url": "https://www.csjt.jus.br/web/csjt/legislacao-atos", "tipo": "Web"},

    # --- Tribunais de Justiça Estaduais (TJs) ---
    {"nome": "TJSP - Notícias eproc", "url": "https://www.tjsp.jus.br/eproc/Noticias", "tipo": "Web"},
    {"nome": "TJSP - Notícias Gerais", "url": "https://www.tjsp.jus.br/Noticias", "tipo": "Web"},
    {"nome": "TJSP - Comunicados (Precatórios)", "url": "https://www.tjsp.jus.br/Precatorios/Comunicados?tipoDestino=85", "tipo": "Web"},
    {"nome": "TJMG - Notícias", "url": "https://www.tjmg.jus.br/portal-tjmg/noticias/", "tipo": "Web"},
    {"nome": "TJMG - Atos Normativos", "url": "https://www.tjmg.jus.br/portal-tjmg/atos-normativos/", "tipo": "Web"},
    {"nome": "TJRJ - Notícias", "url": "https://www.tjrj.jus.br/web/guest/noticias", "tipo": "Web"},
    {"nome": "TJPR - Notícias", "url": "https://www.tjpr.jus.br/noticias", "tipo": "Web"},
    {"nome": "TJPR - Legislação e Atos Normativos", "url": "https://www.tjpr.jus.br/legislacao-atos-normativos", "tipo": "Web"},
    {"nome": "TJRS - Notícias", "url": "https://www.tjrs.jus.br/novo/comunicacao/noticias-do-tjrs/noticias/", "tipo": "Web"},
    {"nome": "TJRS - Publicações Administrativas", "url": "https://www.tjrs.jus.br/novo/jurisprudencia-e-legislacao/publicacoes-administrativas-do-tjrs/", "tipo": "Web"},
    {"nome": "TJBA - Agência de Notícias", "url": "https://www.tjba.jus.br/portal/agencia-de-noticias/", "tipo": "Web"},

    # --- Tribunais Regionais Federais (TRFs) ---
    {"nome": "TRF1 - Notícias", "url": "https://www.trf1.jus.br/trf1/noticias/", "tipo": "Web"},
    {"nome": "TRF2 - Portal Notícias", "url": "https://www.trf2.jus.br/", "tipo": "Web"},
    {"nome": "TRF3 - Últimas Notícias", "url": "https://web.trf3.jus.br/noticias/Noticiar/ExibirUltimasNoticias", "tipo": "Web"},
    {"nome": "TRF4 - Notícias Portal", "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=noticia_portal", "tipo": "Web"},
    {"nome": "TRF4 - Atos Normativos", "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=ato_normativo_pesquisar", "tipo": "Web"},
    {"nome": "TRF5 - Notícias", "url": "https://www.trf5.jus.br/index.php/noticias", "tipo": "Web"},
    {"nome": "TRF6 - Notícias", "url": "https://portal.trf6.jus.br/noticias/", "tipo": "Web"},
    {"nome": "TRF6 - Atos Normativos", "url": "https://portal.trf6.jus.br/atos-normativos/", "tipo": "Web"},

    # --- Tribunais Regionais do Trabalho (TRTs) ---
    {"nome": "TRT1 - Últimas Notícias", "url": "https://www.trt1.jus.br/ultimas-noticias", "tipo": "Web"},
    {"nome": "TRT1 - Biblioteca Digital (Atos)", "url": "https://bibliotecadigital.trt1.jus.br/jspui/handle/1001/6", "tipo": "Web"},
    {"nome": "TRT2 - Notícias", "url": "https://ww2.trt2.jus.br/noticias/noticias", "tipo": "Web"},
    {"nome": "TRT3 - Notícias Institucionais", "url": "https://portal.trt3.jus.br/internet/conheca-o-trt/comunicacao/noticias-institucionais", "tipo": "Web"},
    {"nome": "TRT4 - Notícias", "url": "https://www.trt4.jus.br/portais/trt4/modulos/noticias/todas/0", "tipo": "Web"},
    {"nome": "TRT15 - Notícias", "url": "https://trt15.jus.br/noticias/maisnoticias", "tipo": "Web"},
    
    # --- TRIBUNAIS SUPERIORES E FEDERAIS ---
    {"nome": "STF - Supremo Tribunal Federal", "url": "https://portal.stf.jus.br/textos/verTexto.asp?servico=indispAplicacoes&pagina=principal", "tipo": "Web"},
    {"nome": "STJ - Superior Tribunal de Justiça", "url": "https://ri.web.stj.jus.br/registro-de-indisponibilidades/", "tipo": "Web"},
    {"nome": "CNJ - Conselho Nacional de Justiça", "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/justica-4-0/relatorios-de-indisponibilidade/", "tipo": "Web"},
    {"nome": "TRF1 - Tribunal Regional Federal da 1ª Região", "url": "https://app.trf1.jus.br/indisponibilidades-relatorio/", "tipo": "Web"},
    {"nome": "TRF2 - Tribunal Regional Federal da 2ª Região", "url": "https://www.trf2.jus.br/trf2/comunicacao", "tipo": "Web"},
    {"nome": "TRF3 - Tribunal Regional Federal da 3ª Região", "url": "https://status.trf3.jus.br/", "tipo": "Web"},
    {"nome": "TRF4 - Tribunal Regional Federal da 4ª Região", "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=aviso_listar", "tipo": "Web"},
    {"nome": "TRF5 - Tribunal Regional Federal da 5ª Região", "url": "https://pje.trf5.jus.br/pje/IndisponibilidadeSistema/listView.seam?&Itemid=530", "tipo": "Web"},
    {"nome": "TRF6 - Tribunal Regional Federal da 6ª Região", "url": "https://portal.trf6.jus.br/avisos/", "tipo": "Web"},

    # --- TRIBUNAIS DE JUSTIÇA ESTADUAIS (27 TJs) ---
    {"nome": "TJAC - Tribunal de Justiça do Acre 1g", "url": "https://www.tjac.jus.br/indisponibilidade/?tax=grau-1grau", "tipo": "Web"},
    {"nome": "TJAL - Tribunal de Justiça de Acre 2G", "url": "https://www.tjac.jus.br/indisponibilidade/?tax=grau-2grau", "tipo": "Web"},
    {"nome": "TJAL - Tribunal de Justiça de Alagoas", "url": "https://www.tjal.jus.br/indisponibilidades", "tipo": "Web"},
    {"nome": "TJAP - Tribunal de Justiça do Amapá", "url": "https://sig.tjap.jus.br/deintel_grid_vw_ocorrencias_ext/deintel_grid_vw_ocorrencias_ext.php", "tipo": "Web"},
    {"nome": "TJAM - Tribunal de Justiça do Amazonas", "url": "https://www.tjam.jus.br/index.php/certidoes-de-indisponibilidade", "tipo": "Web"},
    {"nome": "TJBA - Tribunal de Justiça da Bahia", "url": "https://www.tjba.jus.br/portal/aviso-indisponibilidade/", "tipo": "Web"},
    {"nome": "TJCE - Tribunal de Justiça do Ceará", "url": "https://www.tjce.jus.br/historico-de-indisponibilidade-portal-e-saj/", "tipo": "Web"},
    {"nome": "TJDFT - Tribunal de Justiça do Distrito Federal e Territórios", "url": "https://pje-indisponibilidade.tjdft.jus.br/", "tipo": "Web"},
    {"nome": "TJES - Tribunal de Justiça do Espírito Santo", "url": "https://www.tjes.jus.br/pje/consulta-indisponibilidade/", "tipo": "Web"},
    {"nome": "TJGO - Tribunal de Justiça de Goiás", "url": "https://www.tjgo.jus.br/index.php/agencia-de-noticias/noticias-ccse", "tipo": "Web"},
    {"nome": "TJMA - Tribunal de Justiça do Maranhão", "url": "https://www.tjma.jus.br/atos/tj/geral/0/120/o", "tipo": "Web"},
    {"nome": "TJMT - Tribunal de Justiça do Mato Grosso", "url": "https://www.tjmt.jus.br/noticias", "tipo": "Web"},
    {"nome": "TJMS - Tribunal de Justiça do Mato Grosso do Sul", "url": "https://www5.tjms.jus.br/monitoramentoEsaj/", "tipo": "Web"},
    {"nome": "TJMG - Tribunal de Justiça de Minas Gerais", "url": "https://www.tjmg.jus.br/pje/certidao-de-indisponibilidade/", "tipo": "Web"},
    {"nome": "TJMG - Tribunal de Justiça de Minas GErais (Atos)", "url": "https://www.tjmg.jus.br/pje/atos-normativos/", "tipo": "Web"},
    {"nome": "TJPA - Tribunal de Justiça do Pará", "url": "https://www.tjpa.jus.br/PortalExterno/indexBibliotecaDigital.xhtml#resultados=&categoria=353&biblioteca=Documentos+Oficiais", "tipo": "Web"},
    {"nome": "TJPB - Tribunal de Justiça da Paraíba 1G", "url": "https://www.tjpb.jus.br/pje/monitoramento/indicador-de-indisponibilidade-do-pje-1o-grau", "tipo": "Web"},
    {"nome": "TJPR - Tribunal de Justiça do Paraíba 2G", "url": "https://www.tjpb.jus.br/pje/monitoramento/indicador-de-indisponibilidade-do-pje-2o-grau-e-turmas-recursais", "tipo": "Web"},
    {"nome": "TJPR - Tribunal de Justiça do Paraná", "url": "https://www.tjpr.jus.br/home/-/asset_publisher/A2gt/content/id/5924367#5924367", "tipo": "Web"},
    {"nome": "TJPE - Tribunal de Justiça de Pernambuco", "url": "https://www.tjpe.jus.br/pje/indisponibilidade-do-pje", "tipo": "Web"},
    {"nome": "TJPI - Tribunal de Justiça do Piauí", "url": "https://www.tjpi.jus.br/portaltjpi/pje/indisponibilidade-do-sistema/", "tipo": "Web"},
    {"nome": "TJRJ - Tribunal de Justiça do Rio de Janeiro", "url": "https://www3.tjrj.jus.br/portalservicos/#/modindpub-principal", "tipo": "Web"},
    {"nome": "TJRN - Tribunal de Justiça do Rio Grande do Norte", "url": "https://www.tjrn.jus.br/noticias/", "tipo": "Web"},
    {"nome": "TJRS - Tribunal de Justiça do Rio Grande do Sul", "url": "https://www.tjrs.jus.br/novo/processos-e-servicos/consultas-processuais/certidoes-indisponibilidade/", "tipo": "Web"},
    {"nome": "TJRO - Tribunal de Justiça de Rondônia", "url": "https://www.tjro.jus.br/sci/evento", "tipo": "Web"},
    {"nome": "TJRR - Tribunal de Justiça de Roraima", "url": "https://projudi.tjrr.jus.br/projudi/indisponibilidades.jsp", "tipo": "Web"},
    {"nome": "TJSC - Tribunal de Justiça de Santa Catarina", "url": "https://eproc1g.tjsc.jus.br/eproc/externo_controlador.php?acao=processo_disponibilidade_listagem", "tipo": "Web"},
    {"nome": "TJSP - Tribunal de Justiça de São Paulo", "url": "https://www.tjsp.jus.br/Indisponibilidade/Comunicados", "tipo": "Web"},
    {"nome": "TJSE - Tribunal de Justiça de Sergipe", "url": "https://www.tjse.jus.br/portal/consultas/novo-cpc/indisponibilidade-de-sistemas", "tipo": "Web"},
    {"nome": "TJTO - Tribunal de Justiça do Tocantins", "url": "https://www.tjto.jus.br/comunicacao/noticias", "tipo": "Web"},

    # --- TRIBUNAIS REGIONAIS DO TRABALHO (24 TRTs) ---
    {"nome": "TRT1 - TRT 1ª Região (RJ)", "url": "https://trt1.jus.br/certidao-de-indisponibilidade", "tipo": "Web"},
    {"nome": "TRT2 - TRT 2ª Região (SP)", "url": "https://aplicacoes8.trt2.jus.br/sis/indisponibilidade/consulta", "tipo": "Web"},
    {"nome": "TRT3 - TRT 3ª Região (MG)", "url": "https://cinde.trt3.jus.br/cinde/certidao/listagem.htm?dswid=-6858", "tipo": "Web"},
    {"nome": "TRT4 - TRT 4ª Região (RS)", "url": "https://www.trt4.jus.br/portais/trt4/pje-indisponibilidade", "tipo": "Web"},
    {"nome": "TRT5 - TRT 5ª Região (BA)", "url": "https://portalpje.trt5.jus.br/pje-indisponibilidades", "tipo": "Web"},
    {"nome": "TRT6 - TRT 6ª Região (PE)", "url": "https://www.trt6.jus.br/portal/noticias", "tipo": "Web"},
    {"nome": "TRT7 - TRT 7ª Região (CE)", "url": "https://www.trt7.jus.br/index.php/blog/200-servicos/227-pje/7512-indisponibilidades-do-pje?start=1", "tipo": "Web"},
    {"nome": "TRT8 - TRT 8ª Região (PA/AP)", "url": "https://www.trt8.jus.br/pje/indisponibilidade-do-sistema", "tipo": "Web"},
    {"nome": "TRT9 - TRT 9ª Região (PR)", "url": "https://www.trt9.jus.br/portal/destaques.xhtml", "tipo": "Web"},
    {"nome": "TRT10 - TRT 10ª Região (DF/TO)", "url": "https://www.trt10.jus.br/servicos/?pagina=pje/indisponibilidade/index.php", "tipo": "Web"},
    {"nome": "TRT11 - TRT 11ª Região (AM/RR)", "url": "https://portal.trt11.jus.br/index.php/advogados/pagina-pje/33-pje/365-periodos-de-indisponibilidade-do-pje-jt", "tipo": "Web"},
    {"nome": "TRT12 - TRT 12ª Região (SC)", "url": "https://portal.trt12.jus.br/pje/uso_indisponibilidade", "tipo": "Web"},
    {"nome": "TRT13 - TRT 13ª Região (PB)", "url": "https://www.trt13.jus.br/pje/relatorio-de-indisponibilidade-do-pje", "tipo": "Web"},
    {"nome": "TRT14 - TRT 14ª Região (RO/AC)", "url": "https://portal.trt14.jus.br/portal/pje/indisponibilidade", "tipo": "Web"},
    {"nome": "TRT15 - TRT 15ª Região (Campinas)", "url": "https://trt15.jus.br/pje/indisponibilidade-pje", "tipo": "Web"},
    {"nome": "TRT16 - TRT 16ª Região (MA)", "url": "https://www.trt16.jus.br/servicos/outros-servicos/calendario-indisponibilidade", "tipo": "Web"},
    {"nome": "TRT17 - TRT 17ª Região (ES)", "url": "https://www.trt17.jus.br/web/servicos/w/indiponibilidade-sistema-pje", "tipo": "Web"},
    {"nome": "TRT18 - TRT 18ª Região (GO)", "url": "https://www.trt18.jus.br/portal/servicos/pje/indisponibilidades-do-pje/", "tipo": "Web"},
    {"nome": "TRT19 - TRT 19ª Região (AL)", "url": "https://site.trt19.jus.br/pjePeridosIndisponibilidades", "tipo": "Web"},
    {"nome": "TRT20 - TRT 20ª Região (SE)", "url": "https://www.trt20.jus.br/pje/indisponibilidade", "tipo": "Web"},
    {"nome": "TRT21 - TRT 21ª Região (RN)", "url": "https://www.trt21.jus.br/servicos/pje/indisponibilidade-sistema", "tipo": "Web"},
    {"nome": "TRT22 - TRT 22ª Região (PI)", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT1ihmu1f1FyY-MGX2fo5ikUpRwf2QVq7KSZSANyf-r0deXMtoMM2L-pw_kFR6nFXXrdd4mdrFNKJ3F/pubhtml?gid=0&single=true", "tipo": "Web"},
    {"nome": "TRT23 - TRT 23ª Região (MT)", "url": "https://portal.trt23.jus.br/portal/calendario-de-indisponibilidade-do-pje", "tipo": "Web"},
    {"nome": "TRT24 - TRT 24ª Região (MS)", "url": "https://www.trt24.jus.br/indisponibilidade-do-pje", "tipo": "Web"},

    # --- TRIBUNAIS REGIONAIS ELEITORAIS (TREs selecionados) ---
    {"nome": "TSE - TSE (Nacional)", "url": "https://www.tse.jus.br/servicos-judiciais/processos/processo-judicial-eletronico/situacao-atual-dos-servicos-digitais-do-tse", "tipo": "Web"},
    {"nome": "TRE-SP - TRE São Paulo", "url": "https://www.tre-sp.jus.br/servicos-judiciais/indisponibilidade-pje", "tipo": "Web"},
    {"nome": "TRE-MG - TRE Minas Gerais", "url": "https://www.tse.jus.br/servicos-judiciais/processos/processo-judicial-eletronico/situacao-atual-dos-servicos-digitais-do-tse", "tipo": "Web"},
    {"nome": "TRE-RJ - TRE Rio de Janeiro", "url": "https://www.tre-rj.jus.br/servicos-judiciais/comunicados/comunicados", "tipo": "Web"}
]

TERMOS_ALERTA = [
    "pje", "eproc", "projudi", "esaj", "pdpj", "jus.br", 
    "2fa", "mfa", "duplo fator", "dois fatores", "multifator", "authenticator", 
    "sso", "single sign-on", "captcha", "waf", "token", "ciberataque", 
    "instabilidade", "indisponibilidade nos tribunais", "golpe do advogado",
    "portaria nº 140", "resolução nº 335", "certificado digital",
    "novo sistema", "migração", "descontinuado", "sistema próprio",
    "ransomware", "ataque hacker", "manutenção programada", "fora do ar"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ==============================================================================
# 2. FUNÇÕES DE RASPAGEM (SCRAPING)
# ==============================================================================

def scrape_telegram(url):
    """Extrai mensagens do canal público do Telegram postadas nos últimos 7 dias."""
    alertas = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        mensagens = soup.find_all('div', class_='tgme_widget_message_wrap')
        # ALTERADO AQUI: Passa a olhar para os últimos 7 dias
        limite_tempo = datetime.now() - timedelta(days=7)
        
        for msg in mensagens:
            time_tag = msg.find('time')
            text_tag = msg.find('div', class_='tgme_widget_message_text')
            
            if time_tag and text_tag:
                data_str = time_tag.get('datetime').split('+')[0] 
                data_msg = datetime.strptime(data_str, "%Y-%m-%dT%H:%M:%S")
                
                if data_msg >= limite_tempo:
                    texto = text_tag.get_text(separator=" ", strip=True)
                    alertas.append({
                        "texto": texto[:150] + "...", 
                        "link": url
                    })
    except Exception as e:
        print(f"Erro ao ler Telegram ({url}): {e}")
        
    return alertas

def scrape_web_generico(url):
    """Busca links na página que contenham palavras-chave de alerta."""
    alertas = []
    links_vistos = set()
    try:
        # verify=False ajuda a contornar erros de SSL em sites do governo
        response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for a_tag in soup.find_all('a', href=True):
            texto_link = a_tag.get_text(strip=True).lower()
            href = a_tag['href']
            
            # Se o link tiver texto suficiente e contiver algum termo de alerta
            if len(texto_link) > 15 and any(termo in texto_link for termo in TERMOS_ALERTA):
                if href not in links_vistos:
                    # Resolve links relativos (ex: /noticias/123 -> https://site.jus.br/noticias/123)
                    link_completo = href if href.startswith('http') else url.rstrip('/') + '/' + href.lstrip('/')
                    
                    alertas.append({
                        "texto": a_tag.get_text(strip=True),
                        "link": link_completo
                    })
                    links_vistos.add(href)
    except Exception as e:
        print(f"Erro ao ler {url}: {e}")
        
    return alertas

def executar_varredura():
    resultados_finais = []
    
    for fonte in FONTES_OFICIAIS:
        print(f"Inspecionando: {fonte['nome']}...")
        alertas = []
        
        if fonte['tipo'] == "Telegram":
            alertas = scrape_telegram(fonte['url'])
        else:
            alertas = scrape_web_generico(fonte['url'])
            
        if alertas:
            resultados_finais.append({
                "fonte": fonte['nome'],
                "url_fonte": fonte['url'],
                "alertas": alertas
            })
        time.sleep(2) # Pausa amigável entre os sites
        
    return resultados_finais

# ==============================================================================
# 3. GERAÇÃO DE E-MAIL (TEXTO E HTML) E ENVIO
# ==============================================================================

def gerar_corpos_email(resultados):
    hoje = datetime.now().strftime("%d/%m/%Y às %H:%M")
    
    # 1. Versão Texto Puro
    texto_puro = f"MAST(FO) - Monitoramento Automatizado de Sistemas e Tribunais/Fontes Oficiais\nData da varredura: {hoje}\n\n"
    
    # 2. Versão HTML (Com um design levemente diferente em vermelho para indicar Alerta do Scraper)
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #c0392b;">🚨 MAST(FO)</h2>
        <p>Varredura realizada nos painéis e sites oficiais em: <strong>{hoje}</strong></p>
        <hr style="border: 1px solid #eee;">
    """

    total_alertas = 0

    if not resultados:
        msg_vazia = "Nenhum alerta novo encontrado nas fontes oficiais mapeadas nas últimas 24 horas."
        texto_puro += msg_vazia + "\n"
        html += f"<p>{msg_vazia}</p>"
    else:
        # Conta o total real de links encontrados
        total_alertas = sum(len(bloco['alertas']) for bloco in resultados)
        
        html += "<ul style='list-style-type: none; padding: 0;'>"
        for bloco in resultados:
            fonte_nome = bloco['fonte']
            fonte_url = bloco['url_fonte']
            
            # Adiciona ao Texto Puro
            texto_puro += f"📌 FONTE: {fonte_nome}\n   Página: {fonte_url}\n"
            
            # Adiciona ao HTML (Caixa para cada Tribunal/Fonte)
            html += f"""
            <li style="margin-bottom: 25px; padding: 15px; border-left: 4px solid #c0392b; background-color: #fdfaf9;">
                <h3 style="margin: 0 0 5px 0; color: #2c3e50;">📌 {fonte_nome}</h3>
                <p style="margin: 0 0 15px 0; font-size: 0.85em;">
                    <a href="{fonte_url}" style="color: #7f8c8d; text-decoration: none;">Acessar página fonte original</a>
                </p>
                <ul style="padding-left: 20px;">
            """
            
            for alerta in bloco['alertas']:
                # Texto Puro
                texto_puro += f"   - {alerta['texto']}\n     Link: {alerta['link']}\n"
                
                # HTML (Links encontrados)
                html += f"""
                    <li style="margin-bottom: 8px;">
                        <a href="{alerta['link']}" style="color: #2980b9; text-decoration: none; font-weight: bold;">
                            {alerta['texto']}
                        </a>
                    </li>
                """
            
            texto_puro += "\n"
            html += "</ul></li>"
            
        html += "</ul>"

    rodape = "\n---\nEste é um e-mail automático gerado pelo Scraper do MAST no GitHub Actions."
    texto_puro += rodape
    html += f"""
        <hr style="border: 1px solid #eee;">
        <p style="font-size: 0.8em; color: #95a5a6;">Este é um e-mail automático gerado pelo MAST(FO).</p>
      </body>
    </html>
    """
    
    return texto_puro, html, total_alertas

def enviar_email(texto_puro, html, total_alertas):
    remetente = os.environ.get('EMAIL_REMETENTE')
    senha = os.environ.get('EMAIL_SENHA')
    destinatario = os.environ.get('EMAIL_DESTINATARIO')

    if not remetente or not senha:
        print("Aviso: Credenciais de e-mail não configuradas no ambiente. O e-mail não será enviado.")
        return

    msg = MIMEMultipart('alternative')
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = f"MAST Scraper - {datetime.now().strftime('%d/%m/%Y')} ({total_alertas} alertas)"

    # Anexa as versões
    msg.attach(MIMEText(texto_puro, 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    try:
        print("\nConectando ao servidor SMTP para enviar e-mail...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        print(f"E-mail HTML enviado com sucesso para {destinatario}! ({total_alertas} alertas processados)")
    except Exception as e:
        print(f"Erro crítico ao enviar e-mail: {e}")

# ==============================================================================
# 4. EXECUÇÃO PRINCIPAL
# ==============================================================================

if __name__ == "__main__":
    print("Iniciando varredura nas FONTES OFICIAIS...")
    resultados = executar_varredura()
    
    texto, html, total = gerar_corpos_email(resultados)
    
    print(f"\nTotal de alertas individuais encontrados: {total}\n")
    print("=== CORPO DO E-MAIL GERADO ===")
    print(texto)
    print("==============================")
    
    enviar_email(texto, html, total)