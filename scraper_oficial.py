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
    # --- 1. SISTEMAS E CNJ ---
    {"nome": "Telegram - PJe News", "url": "https://t.me/s/pjenews", "tipo": "Telegram"},
    {"nome": "PJe Legacy - Notas da Versão", "url": "https://docs.pje.jus.br/servicos-negociais/servico-pje-legacy/notas-da-versao", "tipo": "Web"},
    {"nome": "CNJ - Notícias PDPJ-Br", "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/plataforma-digital-do-poder-judiciario-brasileiro-pdpj-br/noticias/", "tipo": "Web"},
    {"nome": "CNJ - Notícias Justiça 4.0", "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/justica-4-0/noticias/", "tipo": "Web"},
    {"nome": "CNJ - Atos Normativos", "url": "https://www.cnj.jus.br/atos_normativos/", "tipo": "Web"},
    {"nome": "CNJ - Relatórios de Indisponibilidade", "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/justica-4-0/relatorios-de-indisponibilidade/", "tipo": "Web"},

    # --- 2. TRIBUNAIS SUPERIORES E CONSELHOS ---
    {"nome": "STF - Notícias", "url": "https://noticias.stf.jus.br/", "tipo": "Web"},
    {"nome": "STF - Indisponibilidade", "url": "https://portal.stf.jus.br/textos/verTexto.asp?servico=indispAplicacoes&pagina=principal", "tipo": "Web"},
    {"nome": "STJ - Últimas Notícias", "url": "https://www.stj.jus.br/sites/portalp/Comunicacao/Ultimas-noticias", "tipo": "Web"},
    {"nome": "STJ - Indisponibilidade", "url": "https://ri.web.stj.jus.br/registro-de-indisponibilidades/", "tipo": "Web"},
    {"nome": "TST - Notícias", "url": "https://www.tst.jus.br/noticias", "tipo": "Web"},
    {"nome": "CSJT - Normativos", "url": "https://www.csjt.jus.br/web/csjt/normativos", "tipo": "Web"},
    {"nome": "TSE - Situação Atual dos Sistemas", "url": "https://www.tse.jus.br/servicos-judiciais/processos/processo-judicial-eletronico/situacao-atual-dos-servicos-digitais-do-tse", "tipo": "Web"},

    # --- 3. TRIBUNAIS REGIONAIS FEDERAIS (TRFs) ---
    {"nome": "TRF1 - Notícias", "url": "https://www.trf1.jus.br/trf1/noticias/", "tipo": "Web"},
    {"nome": "TRF1 - Indisponibilidade", "url": "https://app.trf1.jus.br/indisponibilidades-relatorio/", "tipo": "Web"},
    {"nome": "TRF2 - Comunicação e Indisponibilidade", "url": "https://www.trf2.jus.br/trf2/comunicacao", "tipo": "Web"},
    {"nome": "TRF3 - Últimas Notícias", "url": "https://web.trf3.jus.br/noticias/Noticiar/ExibirUltimasNoticias", "tipo": "Web"},
    {"nome": "TRF3 - Status dos Sistemas", "url": "https://status.trf3.jus.br/", "tipo": "Web"},
    {"nome": "TRF4 - Notícias Portal", "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=noticia_portal", "tipo": "Web"},
    {"nome": "TRF4 - Indisponibilidade", "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=aviso_listar", "tipo": "Web"},
    {"nome": "TRF5 - Notícias", "url": "https://www.trf5.jus.br/index.php/noticias", "tipo": "Web"},
    {"nome": "TRF5 - Indisponibilidade", "url": "https://pje.trf5.jus.br/pje/IndisponibilidadeSistema/listView.seam?&Itemid=530", "tipo": "Web"},
    {"nome": "TRF6 - Notícias e Avisos", "url": "https://portal.trf6.jus.br/noticias/", "tipo": "Web"},

    # --- 4. TRIBUNAIS DE JUSTIÇA ESTADUAIS (TJs) ---
    {"nome": "TJSP - Notícias eproc", "url": "https://www.tjsp.jus.br/eproc/Noticias", "tipo": "Web"},
    {"nome": "TJSP - Indisponibilidade", "url": "https://www.tjsp.jus.br/Indisponibilidade/Comunicados", "tipo": "Web"},
    {"nome": "TJMG - Notícias", "url": "https://www.tjmg.jus.br/portal-tjmg/noticias/", "tipo": "Web"},
    {"nome": "TJMG - Indisponibilidade", "url": "https://www.tjmg.jus.br/pje/certidao-de-indisponibilidade/", "tipo": "Web"},
    {"nome": "TJRJ - Notícias", "url": "https://www.tjrj.jus.br/web/guest/noticias", "tipo": "Web"},
    {"nome": "TJRJ - Indisponibilidade", "url": "https://www3.tjrj.jus.br/portalservicos/#/modindpub-principal", "tipo": "Web"},
    {"nome": "TJPR - Notícias", "url": "https://www.tjpr.jus.br/noticias", "tipo": "Web"},
    {"nome": "TJPR - Indisponibilidade", "url": "https://www.tjpr.jus.br/home/-/asset_publisher/A2gt/content/id/5924367#5924367", "tipo": "Web"},
    {"nome": "TJRS - Notícias", "url": "https://www.tjrs.jus.br/novo/comunicacao/noticias-do-tjrs/noticias/", "tipo": "Web"},
    {"nome": "TJRS - Indisponibilidade", "url": "https://www.tjrs.jus.br/novo/processos-e-servicos/consultas-processuais/certidoes-indisponibilidade/", "tipo": "Web"},
    {"nome": "TJBA - Notícias e Indisponibilidade", "url": "https://www.tjba.jus.br/portal/aviso-indisponibilidade/", "tipo": "Web"},
    
    # Outros TJs - Indisponibilidade
    {"nome": "TJAC - Indisponibilidade 1G", "url": "https://www.tjac.jus.br/indisponibilidade/?tax=grau-1grau", "tipo": "Web"},
    {"nome": "TJAL - Indisponibilidades", "url": "https://www.tjal.jus.br/indisponibilidades", "tipo": "Web"},
    {"nome": "TJAP - Ocorrências Sistemas", "url": "https://sig.tjap.jus.br/deintel_grid_vw_ocorrencias_ext/deintel_grid_vw_ocorrencias_ext.php", "tipo": "Web"},
    {"nome": "TJAM - Certidões de Indisponibilidade", "url": "https://www.tjam.jus.br/index.php/certidoes-de-indisponibilidade", "tipo": "Web"},
    {"nome": "TJCE - Histórico e-SAJ", "url": "https://www.tjce.jus.br/historico-de-indisponibilidade-portal-e-saj/", "tipo": "Web"},
    {"nome": "TJDFT - PJe Indisponibilidade", "url": "https://pje-indisponibilidade.tjdft.jus.br/", "tipo": "Web"},
    {"nome": "TJES - Consulta Indisponibilidade", "url": "https://www.tjes.jus.br/pje/consulta-indisponibilidade/", "tipo": "Web"},
    {"nome": "TJGO - Notícias CCSE", "url": "https://www.tjgo.jus.br/index.php/agencia-de-noticias/noticias-ccse", "tipo": "Web"},
    {"nome": "TJMA - Atos e Avisos", "url": "https://www.tjma.jus.br/atos/tj/geral/0/120/o", "tipo": "Web"},
    {"nome": "TJMT - Notícias", "url": "https://www.tjmt.jus.br/noticias", "tipo": "Web"},
    {"nome": "TJMS - Monitoramento e-SAJ", "url": "https://www5.tjms.jus.br/monitoramentoEsaj/", "tipo": "Web"},
    {"nome": "TJPA - Documentos Oficiais", "url": "https://www.tjpa.jus.br/PortalExterno/indexBibliotecaDigital.xhtml#resultados=&categoria=353&biblioteca=Documentos+Oficiais", "tipo": "Web"},
    {"nome": "TJPB - Indisponibilidade PJe", "url": "https://www.tjpb.jus.br/pje/monitoramento/indicador-de-indisponibilidade-do-pje-1o-grau", "tipo": "Web"},
    {"nome": "TJPE - Indisponibilidade PJe", "url": "https://www.tjpe.jus.br/pje/indisponibilidade-do-pje", "tipo": "Web"},
    {"nome": "TJPI - Indisponibilidade do Sistema", "url": "https://www.tjpi.jus.br/portaltjpi/pje/indisponibilidade-do-sistema/", "tipo": "Web"},
    {"nome": "TJRN - Notícias", "url": "https://www.tjrn.jus.br/noticias/", "tipo": "Web"},
    {"nome": "TJRO - Eventos SCI", "url": "https://www.tjro.jus.br/sci/evento", "tipo": "Web"},
    {"nome": "TJRR - Indisponibilidades Projudi", "url": "https://projudi.tjrr.jus.br/projudi/indisponibilidades.jsp", "tipo": "Web"},
    {"nome": "TJSC - Indisponibilidade eproc", "url": "https://eproc1g.tjsc.jus.br/eproc/externo_controlador.php?acao=processo_disponibilidade_listagem", "tipo": "Web"},
    {"nome": "TJSE - Indisponibilidade de Sistemas", "url": "https://www.tjse.jus.br/portal/consultas/novo-cpc/indisponibilidade-de-sistemas", "tipo": "Web"},
    {"nome": "TJTO - Notícias", "url": "https://www.tjto.jus.br/comunicacao/noticias", "tipo": "Web"},

    # --- 5. TRIBUNAIS REGIONAIS DO TRABALHO (TRTs) ---
    {"nome": "TRT1 - Últimas Notícias e Indisponibilidade", "url": "https://trt1.jus.br/certidao-de-indisponibilidade", "tipo": "Web"},
    {"nome": "TRT2 - Indisponibilidade", "url": "https://aplicacoes8.trt2.jus.br/sis/indisponibilidade/consulta", "tipo": "Web"},
    {"nome": "TRT3 - Indisponibilidade", "url": "https://cinde.trt3.jus.br/cinde/certidao/listagem.htm?dswid=-6858", "tipo": "Web"},
    {"nome": "TRT4 - PJe Indisponibilidade", "url": "https://www.trt4.jus.br/portais/trt4/pje-indisponibilidade", "tipo": "Web"},
    {"nome": "TRT5 - PJe Indisponibilidades", "url": "https://portalpje.trt5.jus.br/pje-indisponibilidades", "tipo": "Web"},
    {"nome": "TRT6 - Notícias", "url": "https://www.trt6.jus.br/portal/noticias", "tipo": "Web"},
    {"nome": "TRT7 - Indisponibilidades PJe", "url": "https://www.trt7.jus.br/index.php/blog/200-servicos/227-pje/7512-indisponibilidades-do-pje?start=1", "tipo": "Web"},
    {"nome": "TRT8 - Indisponibilidade do Sistema", "url": "https://www.trt8.jus.br/pje/indisponibilidade-do-sistema", "tipo": "Web"},
    {"nome": "TRT9 - Destaques", "url": "https://www.trt9.jus.br/portal/destaques.xhtml", "tipo": "Web"},
    {"nome": "TRT10 - Indisponibilidade PJe", "url": "https://www.trt10.jus.br/servicos/?pagina=pje/indisponibilidade/index.php", "tipo": "Web"},
    {"nome": "TRT11 - Períodos de Indisponibilidade", "url": "https://portal.trt11.jus.br/index.php/advogados/pagina-pje/33-pje/365-periodos-de-indisponibilidade-do-pje-jt", "tipo": "Web"},
    {"nome": "TRT12 - Uso e Indisponibilidade PJe", "url": "https://portal.trt12.jus.br/pje/uso_indisponibilidade", "tipo": "Web"},
    {"nome": "TRT13 - Relatório de Indisponibilidade", "url": "https://www.trt13.jus.br/pje/relatorio-de-indisponibilidade-do-pje", "tipo": "Web"},
    {"nome": "TRT14 - Indisponibilidade PJe", "url": "https://portal.trt14.jus.br/portal/pje/indisponibilidade", "tipo": "Web"},
    {"nome": "TRT15 - Indisponibilidade PJe", "url": "https://trt15.jus.br/pje/indisponibilidade-pje", "tipo": "Web"},
    {"nome": "TRT16 - Calendário de Indisponibilidade", "url": "https://www.trt16.jus.br/servicos/outros-servicos/calendario-indisponibilidade", "tipo": "Web"},
    {"nome": "TRT17 - Indisponibilidade Sistema PJe", "url": "https://www.trt17.jus.br/web/servicos/w/indiponibilidade-sistema-pje", "tipo": "Web"},
    {"nome": "TRT18 - Indisponibilidades do PJe", "url": "https://www.trt18.jus.br/portal/servicos/pje/indisponibilidades-do-pje/", "tipo": "Web"},
    {"nome": "TRT19 - Períodos de Indisponibilidades", "url": "https://site.trt19.jus.br/pjePeridosIndisponibilidades", "tipo": "Web"},
    {"nome": "TRT20 - Indisponibilidade", "url": "https://www.trt20.jus.br/pje/indisponibilidade", "tipo": "Web"},
    {"nome": "TRT21 - Indisponibilidade do Sistema", "url": "https://www.trt21.jus.br/servicos/pje/indisponibilidade-sistema", "tipo": "Web"},
    {"nome": "TRT23 - Calendário de Indisponibilidade", "url": "https://portal.trt23.jus.br/portal/calendario-de-indisponibilidade-do-pje", "tipo": "Web"},
    {"nome": "TRT24 - Indisponibilidade do PJe", "url": "https://www.trt24.jus.br/indisponibilidade-do-pje", "tipo": "Web"},

    # --- 6. TRIBUNAIS REGIONAIS ELEITORAIS (TREs) ---
    {"nome": "TRE-SP - Indisponibilidade PJe", "url": "https://www.tre-sp.jus.br/servicos-judiciais/indisponibilidade-pje", "tipo": "Web"},
    {"nome": "TRE-RJ - Comunicados", "url": "https://www.tre-rj.jus.br/servicos-judiciais/comunicados/comunicados", "tipo": "Web"}
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
    """Busca links na página que contenham palavras-chave de alerta, ignorando menus."""
    alertas = []
    links_vistos = set()
    try:
        response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ==========================================================
        # FILTRO ANTI-MENU: Remove as partes do site que geram "ruído"
        # ==========================================================
        tags_para_remover = ["nav", "footer", "header", "aside"]
        for tag in soup(tags_para_remover):
            tag.decompose() # Apaga a tag do HTML lido
            
        # Remove também divs genéricas que costumam ser menus ou barras laterais
        for div in soup.find_all('div', class_=lambda c: c and any(x in c.lower() for x in ['menu', 'nav', 'sidebar', 'rodape', 'footer'])):
            div.decompose()
        # ==========================================================
        
        # Agora procura os links apenas no "miolo" (conteúdo real) da página
        for a_tag in soup.find_all('a', href=True):
            texto_link = a_tag.get_text(strip=True).lower()
            href = a_tag['href']
            
            # Aumentamos o limite para 20 caracteres para evitar links curtos e falsos positivos
            if len(texto_link) > 20 and any(termo in texto_link for termo in TERMOS_ALERTA):
                if href not in links_vistos:
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

    rodape = "\n---\nEste é um e-mail automático gerado pelo MAST(FO)."
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
    msg['Subject'] = f"MAST(FO) - Monitoramento Automatizado de Sistemas e Tribunais/Fontes Oficiais - {datetime.now().strftime('%d/%m/%Y')} ({total_alertas} alertas)"

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