import feedparser
import urllib.parse
from datetime import datetime, timedelta
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# ==============================================================================
# 1. CONSTANTES E CONFIGURAÇÕES DE BUSCA
# ==============================================================================

TRIBUNAIS = [
    # --- TRIBUNAIS SUPERIORES E FEDERAIS ---
    {"id": "1", "name": "Supremo Tribunal Federal", "acronym": "STF", "url": "https://portal.stf.jus.br/textos/verTexto.asp?servico=indispAplicacoes&pagina=principal"},
    {"id": "2", "name": "Superior Tribunal de Justiça", "acronym": "STJ", "url": "https://ri.web.stj.jus.br/registro-de-indisponibilidades/"},
    {"id": "3", "name": "Conselho Nacional de Justiça", "acronym": "CNJ", "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/justica-4-0/relatorios-de-indisponibilidade/"},
    {"id": "4", "name": "Tribunal Regional Federal da 1ª Região", "acronym": "TRF1", "url": "https://app.trf1.jus.br/indisponibilidades-relatorio/"},
    {"id": "5", "name": "Tribunal Regional Federal da 2ª Região", "acronym": "TRF2", "url": "https://www.trf2.jus.br/trf2/comunicacao"},
    {"id": "6", "name": "Tribunal Regional Federal da 3ª Região", "acronym": "TRF3", "url": "https://status.trf3.jus.br/"},
    {"id": "7", "name": "Tribunal Regional Federal da 4ª Região", "acronym": "TRF4", "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=aviso_listar"},
    {"id": "8", "name": "Tribunal Regional Federal da 5ª Região", "acronym": "TRF5", "url": "https://pje.trf5.jus.br/pje/IndisponibilidadeSistema/listView.seam?&Itemid=530"},
    {"id": "9", "name": "Tribunal Regional Federal da 6ª Região", "acronym": "TRF6", "url": "https://portal.trf6.jus.br/avisos/"},

    # --- TRIBUNAIS DE JUSTIÇA ESTADUAIS (27 TJs) ---
    {"id": "101", "name": "Tribunal de Justiça do Acre 1g", "acronym": "TJAC", "url": "https://www.tjac.jus.br/indisponibilidade/?tax=grau-1grau"},
    {"id": "102", "name": "Tribunal de Justiça de Acre 2G", "acronym": "TJAL", "url": "https://www.tjac.jus.br/indisponibilidade/?tax=grau-2grau"},
    {"id": "103", "name": "Tribunal de Justiça de Alagoas", "acronym": "TJAL", "url": "https://www.tjal.jus.br/indisponibilidades"},
    {"id": "104", "name": "Tribunal de Justiça do Amapá", "acronym": "TJAP", "url": "https://sig.tjap.jus.br/deintel_grid_vw_ocorrencias_ext/deintel_grid_vw_ocorrencias_ext.php"},
    {"id": "105", "name": "Tribunal de Justiça do Amazonas", "acronym": "TJAM", "url": "https://www.tjam.jus.br/index.php/certidoes-de-indisponibilidade"},
    {"id": "106", "name": "Tribunal de Justiça da Bahia", "acronym": "TJBA", "url": "https://www.tjba.jus.br/portal/aviso-indisponibilidade/"},
    {"id": "107", "name": "Tribunal de Justiça do Ceará", "acronym": "TJCE", "url": "https://www.tjce.jus.br/historico-de-indisponibilidade-portal-e-saj/"},
    {"id": "108", "name": "Tribunal de Justiça do Distrito Federal e Territórios", "acronym": "TJDFT", "url": "https://pje-indisponibilidade.tjdft.jus.br/"},
    {"id": "109", "name": "Tribunal de Justiça do Espírito Santo", "acronym": "TJES", "url": "https://www.tjes.jus.br/pje/consulta-indisponibilidade/"},
    {"id": "110", "name": "Tribunal de Justiça de Goiás", "acronym": "TJGO", "url": "https://www.tjgo.jus.br/index.php/agencia-de-noticias/noticias-ccse"},
    {"id": "111", "name": "Tribunal de Justiça do Maranhão", "acronym": "TJMA", "url": "https://www.tjma.jus.br/atos/tj/geral/0/120/o"},
    {"id": "112", "name": "Tribunal de Justiça do Mato Grosso", "acronym": "TJMT", "url": "https://www.tjmt.jus.br/noticias"},
    {"id": "113", "name": "Tribunal de Justiça do Mato Grosso do Sul", "acronym": "TJMS", "url": "https://www5.tjms.jus.br/monitoramentoEsaj/"},
    {"id": "114", "name": "Tribunal de Justiça de Minas Gerais", "acronym": "TJMG", "url": "https://www.tjmg.jus.br/pje/certidao-de-indisponibilidade/"},
    {"id": "115", "name": "Tribunal de Justiça de Minas GErais", "acronym": "TJMG", "url": "https://www.tjmg.jus.br/pje/atos-normativos/"},
    {"id": "116", "name": "Tribunal de Justiça do Pará", "acronym": "TJPA", "url": "https://www.tjpa.jus.br/PortalExterno/indexBibliotecaDigital.xhtml#resultados=&categoria=353&biblioteca=Documentos+Oficiais"},
    {"id": "117", "name": "Tribunal de Justiça da Paraíba 1G", "acronym": "TJPB", "url": "https://www.tjpb.jus.br/pje/monitoramento/indicador-de-indisponibilidade-do-pje-1o-grau"},
    {"id": "118", "name": "Tribunal de Justiça do Paraíba 2G", "acronym": "TJPR", "url": "https://www.tjpb.jus.br/pje/monitoramento/indicador-de-indisponibilidade-do-pje-2o-grau-e-turmas-recursais"},
    {"id": "119", "name": "Tribunal de Justiça do Paraná", "acronym": "TJPR", "url": "https://www.tjpr.jus.br/home/-/asset_publisher/A2gt/content/id/5924367#5924367"},
    {"id": "120", "name": "Tribunal de Justiça de Pernambuco", "acronym": "TJPE", "url": "https://www.tjpe.jus.br/pje/indisponibilidade-do-pje"},
    {"id": "121", "name": "Tribunal de Justiça do Piauí", "acronym": "TJPI", "url": "https://www.tjpi.jus.br/portaltjpi/pje/indisponibilidade-do-sistema/"},
    {"id": "122", "name": "Tribunal de Justiça do Rio de Janeiro", "acronym": "TJRJ", "url": "https://www3.tjrj.jus.br/portalservicos/#/modindpub-principal"},
    {"id": "123", "name": "Tribunal de Justiça do Rio Grande do Norte", "acronym": "TJRN", "url": "https://www.tjrn.jus.br/noticias/"},
    {"id": "124", "name": "Tribunal de Justiça do Rio Grande do Sul", "acronym": "TJRS", "url": "https://eproc1g.tjrs.jus.br/eproc/externo_controlador.php?acao=processo_disponibilidade_listagem"},
    {"id": "125", "name": "Tribunal de Justiça de Rondônia", "acronym": "TJRO", "url": "https://www.tjro.jus.br/pje/indisponibilidade-do-pje"},
    {"id": "126", "name": "Tribunal de Justiça de Roraima", "acronym": "TJRR", "url": "https://www.tjrr.jus.br/index.php/pje-indisponibilidade"},
    {"id": "127", "name": "Tribunal de Justiça de Santa Catarina", "acronym": "TJSC", "url": "https://eproc1g.tjsc.jus.br/eproc/externo_controlador.php?acao=processo_disponibilidade_listagem"},
    {"id": "128", "name": "Tribunal de Justiça de São Paulo", "acronym": "TJSP", "url": "https://www.tjsp.jus.br/Indisponibilidade/Comunicados"},
    {"id": "129", "name": "Tribunal de Justiça de Sergipe", "acronym": "TJSE", "url": "https://www.tjse.jus.br/pje/indisponibilidade-do-pje"},
    {"id": "130", "name": "Tribunal de Justiça do Tocantins", "acronym": "TJTO", "url": "https://eproc1g.tjto.jus.br/eprocv2_prod_1g/externo_controlador.php?acao=processo_disponibilidade_listagem"},

    # --- TRIBUNAIS REGIONAIS DO TRABALHO (24 TRTs) ---
    {"id": "201", "name": "TRT 1ª Região (RJ)", "acronym": "TRT1", "url": "https://www.trt1.jus.br/certidao-de-indisponibilidade"},
    {"id": "202", "name": "TRT 2ª Região (SP)", "acronym": "TRT2", "url": "https://ww2.trt2.jus.br/servicos/pje-processo-judicial-eletronico/indisponibilidade-do-pje/"},
    {"id": "203", "name": "TRT 3ª Região (MG)", "acronym": "TRT3", "url": "https://portal.trt3.jus.br/internet/servicos/pje/indisponibilidade-do-sistema"},
    {"id": "204", "name": "TRT 4ª Região (RS)", "acronym": "TRT4", "url": "https://www.trt4.jus.br/portais/trt4/pje-indisponibilidade"},
    {"id": "205", "name": "TRT 5ª Região (BA)", "acronym": "TRT5", "url": "https://portalpje.trt5.jus.br/pje-indisponibilidades"},
    {"id": "206", "name": "TRT 6ª Região (PE)", "acronym": "TRT6", "url": "https://www.trt6.jus.br/portal/pje/indisponibilidade-do-sistema"},
    {"id": "207", "name": "TRT 7ª Região (CE)", "acronym": "TRT7", "url": "https://www.trt7.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "208", "name": "TRT 8ª Região (PA/AP)", "acronym": "TRT8", "url": "https://www.trt8.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "209", "name": "TRT 9ª Região (PR)", "acronym": "TRT9", "url": "https://www.trt9.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "210", "name": "TRT 10ª Região (DF/TO)", "acronym": "TRT10", "url": "https://www.trt10.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "211", "name": "TRT 11ª Região (AM/RR)", "acronym": "TRT11", "url": "https://www.trt11.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "212", "name": "TRT 12ª Região (SC)", "acronym": "TRT12", "url": "https://trt12.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "213", "name": "TRT 13ª Região (PB)", "acronym": "TRT13", "url": "https://www.trt13.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "214", "name": "TRT 14ª Região (RO/AC)", "acronym": "TRT14", "url": "https://trt14.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "215", "name": "TRT 15ª Região (Campinas)", "acronym": "TRT15", "url": "https://trt15.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "216", "name": "TRT 16ª Região (MA)", "acronym": "TRT16", "url": "https://www.trt16.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "217", "name": "TRT 17ª Região (ES)", "acronym": "TRT17", "url": "https://www.trt17.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "218", "name": "TRT 18ª Região (GO)", "acronym": "TRT18", "url": "https://www.trt18.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "219", "name": "TRT 19ª Região (AL)", "acronym": "TRT19", "url": "https://www.trt19.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "220", "name": "TRT 20ª Região (SE)", "acronym": "TRT20", "url": "https://www.trt20.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "221", "name": "TRT 21ª Região (RN)", "acronym": "TRT21", "url": "https://www.trt21.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "222", "name": "TRT 22ª Região (PI)", "acronym": "TRT22", "url": "https://www.trt22.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "223", "name": "TRT 23ª Região (MT)", "acronym": "TRT23", "url": "https://portal.trt23.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "224", "name": "TRT 24ª Região (MS)", "acronym": "TRT24", "url": "https://www.trt24.jus.br/pje/indisponibilidade-do-sistema"},

    # --- TRIBUNAIS REGIONAIS ELEITORAIS (TREs selecionados) ---
    {"id": "300", "name": "TSE (Nacional)", "acronym": "TSE", "url": "https://www.tse.jus.br/servicos-judiciais/processos/processo-judicial-eletronico/situacao-atual-dos-servicos-digitais-do-tse"},
    {"id": "301", "name": "TRE São Paulo", "acronym": "TRE-SP", "url": "https://www.tre-sp.jus.br/servicos-judiciais/indisponibilidade-pje"},
    {"id": "302", "name": "TRE Minas Gerais", "acronym": "TRE-MG", "url": "https://www.tse.jus.br/servicos-judiciais/processos/processo-judicial-eletronico/situacao-atual-dos-servicos-digitais-do-tse"},
    {"id": "303", "name": "TRE Rio de Janeiro", "acronym": "TRE-RJ", "url": "https://www.tre-rj.jus.br/servicos-judiciais/pje/indisponibilidade-do-sistema-pje"}
]

TERMOS_ESPECIFICOS = [
    '"2FA PJE"', '"MFA PJE"', '"dois fatores PJE"', '"duplo fator PJE"', 
    '"duplo fator EPROC"', '"duplo fator ESAJ"', '"duplo fator PROJUDI"', 
    '"PDPJ"', '"novo sistema tribunal"', '"mudança sistema tribunal"', 
    '"migração sistema tribunal"', '"pje indisponibilidade"', '" pdpj indisponibilidade"', '"eproc indisponibilidade"', '"esaj indisponibilidade"',
    '"portaria CNJ 140/2024"', '"tribunal pdpj"', '"tribunal authenticator"', 
    '"2FA se tornou obrigatória"', '"golpe do advogado"', '"migração TJPR EPROC"', 
    '"Jus.br"', '"instabilidade pje "', '"instabilidade pdpj"', '"instabilidade eproc"', 
    '"instabilidade esaj"', '"instabilidade projudi"', '"instabilidade TRT"', 
    '"instabilidade dos principais tribunais EPROC"'
]

# ==============================================================================
# 2. MALHA FINA (Filtro rigoroso de Títulos em Python)
# ==============================================================================

TERMOS_FORTES_TI = [
    "pje", "eproc", "projudi", "esaj", "pdpj", "jus.br", 
    "2fa", "mfa", "duplo fator", "dois fatores", "multifator", "authenticator", 
    "sso", "single sign-on", "captcha", "waf", "token", "ciberataque", 
    "instabilidade", "indisponibilidade tribunais", "golpe do advogado",
    "portaria nº 140", "resolução nº 335", "certificado digital",
    "novo sistema", "migração", "descontinuado", "sistema próprio"
]

TERMOS_COMPOSTOS = [
    ["mudança", "sistema"],
    ["troca", "senha"],
    ["renovação", "senha"],
    ["redefinição", "senha"],
    ["código", "autenticação"],
    ["segurança", "digital"],
    ["credencial", "acesso"],
    ["código", "acesso"]
]

def validar_titulo_noticia(titulo):
    """Verifica se o título da notícia realmente fala sobre sistemas ou TI."""
    titulo_lower = titulo.lower()
    
    if any(termo in titulo_lower for termo in TERMOS_FORTES_TI):
        return True
        
    for par in TERMOS_COMPOSTOS:
        if par[0] in titulo_lower and par[1] in titulo_lower:
            return True
            
    return False

# ==============================================================================
# 3. MOTOR DE BUSCA E EXTRAÇÃO
# ==============================================================================

def extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias):
    """Lê o RSS, valida a data, a duplicidade e passa pelo filtro de título."""
    feed = feedparser.parse(url_rss)
    for entry in feed.entries:
        if hasattr(entry, 'published_parsed'):
            data_publicacao = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            
            # Condição tripla: Data Ok + Link Novo + Título Relevante
            if data_publicacao >= data_limite and entry.link not in links_ja_coletados:
                if validar_titulo_noticia(entry.title):
                    todas_noticias.append({
                        'titulo': entry.title,
                        'link': entry.link,
                        'data_obj': data_publicacao,
                        'fonte': entry.source.title if hasattr(entry, 'source') else "Google News"
                    })
                    links_ja_coletados.add(entry.link)

def buscar_noticias_semanais():
    todas_noticias = []
    links_ja_coletados = set()
    data_limite = datetime.now() - timedelta(days=7)

    # PARTE 1: Busca ampla no Google (o Python limpa o lixo depois)
    termos_base_google = '("PJE" OR "EPROC" OR "PROJUDI" OR "indisponibilidade" OR "sistema" OR "segurança" OR "autenticação")'
    
    siglas = [tribunal["acronym"] for tribunal in TRIBUNAIS]
    tamanho_lote = 10
    lotes_siglas = [siglas[i:i + tamanho_lote] for i in range(0, len(siglas), tamanho_lote)]
    
    print(f"Iniciando Fase 1: Varredura de {len(siglas)} Tribunais...")
    for i, lote in enumerate(lotes_siglas, 1):
        query_tribunais = "(" + " OR ".join(f'"{sigla}"' for sigla in lote) + ")"
        query_final = f"{termos_base_google} AND {query_tribunais}"
        query_codificada = urllib.parse.quote(query_final)
        
        url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias)
        time.sleep(1.5)

    # PARTE 2: Busca pelas frases exatas
    print("Iniciando Fase 2: Busca por frases exatas de TI e Segurança...")
    tamanho_lote_termos = 6
    lotes_termos = [TERMOS_ESPECIFICOS[i:i + tamanho_lote_termos] for i in range(0, len(TERMOS_ESPECIFICOS), tamanho_lote_termos)]
    
    for i, lote in enumerate(lotes_termos, 1):
        query_frases = "(" + " OR ".join(lote) + ")"
        query_codificada = urllib.parse.quote(query_frases)
        
        url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias)
        time.sleep(1.5)

    # Ordena cronologicamente
    todas_noticias.sort(key=lambda x: x['data_obj'], reverse=True)
    return todas_noticias

# ==============================================================================
# 4. GERAÇÃO DE E-MAIL (TEXTO E HTML) E ENVIO
# ==============================================================================

def gerar_corpos_email(noticias):
    """Gera duas versões do e-mail: Texto Puro (fallback) e HTML (bonito)."""
    hoje = datetime.now().strftime("%d/%m/%Y")
    uma_semana_atras = (datetime.now() - timedelta(days=7)).strftime("%d/%m/%Y")
    
    # 1. Versão Texto Puro
    texto_puro = f"MANST - Monitoramento Automatizado de Notícias de Sistemas e Tribunais ({uma_semana_atras} a {hoje})\n\n"
    
    # 2. Versão HTML
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #2c3e50;">Monitoramento Automatizado de Notícias de Sistemas e Tribunais</h2>
        <p>Período: <strong>{uma_semana_atras}</strong> até <strong>{hoje}</strong></p>
        <hr style="border: 1px solid #eee;">
    """

    if not noticias:
        msg_vazia = "Nenhuma notícia 100% relevante de TI/Sistemas encontrada nos últimos 7 dias."
        texto_puro += msg_vazia + "\n"
        html += f"<p>{msg_vazia}</p>"
    else:
        html += "<ul style='list-style-type: none; padding: 0;'>"
        for i, noticia in enumerate(noticias, 1):
            data_formatada = noticia['data_obj'].strftime("%d/%m/%Y às %H:%M")
            
            # Adiciona ao Texto Puro
            texto_puro += f"{i}. {noticia['titulo']}\n   Data: {data_formatada}\n   Link: {noticia['link']}\n\n"
            
            # Adiciona ao HTML
            html += f"""
            <li style="margin-bottom: 20px; padding: 15px; border-left: 4px solid #3498db; background-color: #f9f9f9;">
                <h3 style="margin: 0 0 10px 0;">
                    <a href="{noticia['link']}" style="color: #2980b9; text-decoration: none;">{noticia['titulo']}</a>
                </h3>
                <p style="margin: 0; font-size: 0.9em; color: #7f8c8d;">
                    📅 {data_formatada} &nbsp;|&nbsp; 📰 Fonte: {noticia['fonte']}
                </p>
            </li>
            """
        html += "</ul>"

    rodape = "\n---\nEste é um e-mail automático gerado pelo monitoramento automatizado de notícias de sistemas e tribunais."
    texto_puro += rodape
    html += f"""
        <hr style="border: 1px solid #eee;">
        <p style="font-size: 0.8em; color: #95a5a6;">Este é um e-mail automático gerado pelo monitoramento automatizado de notícias de sistemas e tribunais.</p>
      </body>
    </html>
    """
    
    return texto_puro, html

def enviar_email(texto_puro, html, total_noticias):
    remetente = os.environ.get('EMAIL_REMETENTE')
    senha = os.environ.get('EMAIL_SENHA')
    destinatario = os.environ.get('EMAIL_DESTINATARIO')

    if not remetente or not senha:
        print("Erro: Credenciais não configuradas no GitHub Secrets.")
        return

    # O MIMEMultipart('alternative') diz ao cliente de e-mail para tentar ler o HTML, 
    # e se não conseguir, usar o texto puro.
    msg = MIMEMultipart('alternative')
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = f"Monitor de Tribunais e Sistemas - {datetime.now().strftime('%d/%m/%Y')} ({total_noticias} alertas)"

    # Anexa as duas versões
    parte1 = MIMEText(texto_puro, 'plain', 'utf-8')
    parte2 = MIMEText(html, 'html', 'utf-8')
    msg.attach(parte1)
    msg.attach(parte2)

    try:
        print("Conectando ao servidor SMTP...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        print(f"E-mail HTML enviado com sucesso para {destinatario}! ({total_noticias} alertas)")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

if __name__ == "__main__":
    noticias_filtradas = buscar_noticias_semanais()
    texto, html = gerar_corpos_email(noticias_filtradas)
    
    # Exibe no log do GitHub Actions quantos itens passaram pela malha fina e o corpo do texto
    print(f"Total de notícias validadas pela malha fina: {len(noticias_filtradas)}\n")
    print("=== CORPO DO E-MAIL GERADO ===")
    print(texto)
    print("==============================")
    
    enviar_email(texto, html, len(noticias_filtradas))