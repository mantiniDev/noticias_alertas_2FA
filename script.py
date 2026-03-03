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
    {"id": "1", "name": "Supremo Tribunal Federal", "acronym": "STF"},
    {"id": "2", "name": "Superior Tribunal de Justiça", "acronym": "STJ"},
    {"id": "3", "name": "Tribunal Regional Federal da 1ª Região", "acronym": "TRF1"},
    {"id": "4", "name": "Tribunal Regional Federal da 2ª Região", "acronym": "TRF2"},
    {"id": "5", "name": "Tribunal Regional Federal da 3ª Região", "acronym": "TRF3"},
    {"id": "6", "name": "Tribunal Regional Federal da 4ª Região", "acronym": "TRF4"},
    {"id": "7", "name": "Tribunal Regional Federal da 5ª Região", "acronym": "TRF5"},
    {"id": "8", "name": "Tribunal Regional Federal da 6ª Região", "acronym": "TRF6"},

    # --- TRIBUNAIS DE JUSTIÇA ESTADUAIS (27 TJs) ---
    {"id": "101", "name": "Tribunal de Justiça do Acre", "acronym": "TJAC"},
    {"id": "102", "name": "Tribunal de Justiça de Alagoas", "acronym": "TJAL"},
    {"id": "103", "name": "Tribunal de Justiça do Amapá", "acronym": "TJAP"},
    {"id": "104", "name": "Tribunal de Justiça do Amazonas", "acronym": "TJAM"},
    {"id": "105", "name": "Tribunal de Justiça da Bahia", "acronym": "TJBA"},
    {"id": "106", "name": "Tribunal de Justiça do Ceará", "acronym": "TJCE"},
    {"id": "107", "name": "Tribunal de Justiça do Distrito Federal e Territórios", "acronym": "TJDFT"},
    {"id": "108", "name": "Tribunal de Justiça do Espírito Santo", "acronym": "TJES"},
    {"id": "109", "name": "Tribunal de Justiça de Goiás", "acronym": "TJGO"},
    {"id": "110", "name": "Tribunal de Justiça do Maranhão", "acronym": "TJMA"},
    {"id": "111", "name": "Tribunal de Justiça do Mato Grosso", "acronym": "TJMT"},
    {"id": "112", "name": "Tribunal de Justiça do Mato Grosso do Sul", "acronym": "TJMS"},
    {"id": "113", "name": "Tribunal de Justiça de Minas Gerais", "acronym": "TJMG"},
    {"id": "114", "name": "Tribunal de Justiça do Pará", "acronym": "TJPA"},
    {"id": "115", "name": "Tribunal de Justiça da Paraíba", "acronym": "TJPB"},
    {"id": "116", "name": "Tribunal de Justiça do Paraná", "acronym": "TJPR"},
    {"id": "117", "name": "Tribunal de Justiça de Pernambuco", "acronym": "TJPE"},
    {"id": "118", "name": "Tribunal de Justiça do Piauí", "acronym": "TJPI"},
    {"id": "119", "name": "Tribunal de Justiça do Rio de Janeiro", "acronym": "TJRJ"},
    {"id": "120", "name": "Tribunal de Justiça do Rio Grande do Norte", "acronym": "TJRN"},
    {"id": "121", "name": "Tribunal de Justiça do Rio Grande do Sul", "acronym": "TJRS"},
    {"id": "122", "name": "Tribunal de Justiça de Rondônia", "acronym": "TJRO"},
    {"id": "123", "name": "Tribunal de Justiça de Roraima", "acronym": "TJRR"},
    {"id": "124", "name": "Tribunal de Justiça de Santa Catarina", "acronym": "TJSC"},
    {"id": "125", "name": "Tribunal de Justiça de São Paulo", "acronym": "TJSP"},
    {"id": "126", "name": "Tribunal de Justiça de Sergipe", "acronym": "TJSE"},
    {"id": "127", "name": "Tribunal de Justiça do Tocantins", "acronym": "TJTO"},

    # --- TRIBUNAIS REGIONAIS DO TRABALHO (24 TRTs) ---
    {"id": "201", "name": "TRT 1ª Região (RJ)", "acronym": "TRT1"},
    {"id": "202", "name": "TRT 2ª Região (SP)", "acronym": "TRT2"},
    {"id": "203", "name": "TRT 3ª Região (MG)", "acronym": "TRT3"},
    {"id": "204", "name": "TRT 4ª Região (RS)", "acronym": "TRT4"},
    {"id": "205", "name": "TRT 5ª Região (BA)", "acronym": "TRT5"},
    {"id": "206", "name": "TRT 6ª Região (PE)", "acronym": "TRT6"},
    {"id": "207", "name": "TRT 7ª Região (CE)", "acronym": "TRT7"},
    {"id": "208", "name": "TRT 8ª Região (PA/AP)", "acronym": "TRT8"},
    {"id": "209", "name": "TRT 9ª Região (PR)", "acronym": "TRT9"},
    {"id": "210", "name": "TRT 10ª Região (DF/TO)", "acronym": "TRT10"},
    {"id": "211", "name": "TRT 11ª Região (AM/RR)", "acronym": "TRT11"},
    {"id": "212", "name": "TRT 12ª Região (SC)", "acronym": "TRT12"},
    {"id": "213", "name": "TRT 13ª Região (PB)", "acronym": "TRT13"},
    {"id": "214", "name": "TRT 14ª Região (RO/AC)", "acronym": "TRT14"},
    {"id": "215", "name": "TRT 15ª Região (Campinas)", "acronym": "TRT15"},
    {"id": "216", "name": "TRT 16ª Região (MA)", "acronym": "TRT16"},
    {"id": "217", "name": "TRT 17ª Região (ES)", "acronym": "TRT17"},
    {"id": "218", "name": "TRT 18ª Região (GO)", "acronym": "TRT18"},
    {"id": "219", "name": "TRT 19ª Região (AL)", "acronym": "TRT19"},
    {"id": "220", "name": "TRT 20ª Região (SE)", "acronym": "TRT20"},
    {"id": "221", "name": "TRT 21ª Região (RN)", "acronym": "TRT21"},
    {"id": "222", "name": "TRT 22ª Região (PI)", "acronym": "TRT22"},
    {"id": "223", "name": "TRT 23ª Região (MT)", "acronym": "TRT23"},
    {"id": "224", "name": "TRT 24ª Região (MS)", "acronym": "TRT24"},

    # --- TRIBUNAIS REGIONAIS ELEITORAIS (TREs selecionados) ---
    {"id": "300", "name": "TSE (Nacional)", "acronym": "TSE"},
    {"id": "301", "name": "TRE São Paulo", "acronym": "TRE-SP"},
    {"id": "302", "name": "TRE Minas Gerais", "acronym": "TRE-MG"},
    {"id": "303", "name": "TRE Rio de Janeiro", "acronym": "TRE-RJ"}
]

TERMOS_ESPECIFICOS = [
    '"2FA PJE"', '"MFA PJE"', '"dois fatores PJE"', '"duplo fator PJE"', 
    '"duplo fator EPROC"', '"duplo fator ESAJ"', '"duplo fator PROJUDI"', 
    '"PDPJ"', '"novo sistema tribunal"', '"mudança sistema tribunal"', 
    '"migração sistema tribunal"', '"PJE indisponibilidade"', 
    '"portaria CNJ 140/2024"', '"tribunal pdpj"', '"tribunal authenticator"', 
    '"2FA se tornou obrigatória"', '"golpe do advogado"', '"migração TJPR EPROC"', 
    '"Jus.br"', '"instabilidade PJE"', '"instabilidade pdpj"', '"instabilidade eproc"', 
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
    "instabilidade PJE", "instabilidade pdpj", "instabilidade eproc", "golpe do advogado",
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
    texto_puro = f"Resumo de OSINT: Sistemas e Tribunais ({uma_semana_atras} a {hoje})\n\n"
    
    # 2. Versão HTML
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #2c3e50;">Resumo de OSINT: Sistemas e Tribunais</h2>
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

    rodape = "\n---\nEste é um e-mail automático gerado pelo seu monitor no GitHub Actions."
    texto_puro += rodape
    html += f"""
        <hr style="border: 1px solid #eee;">
        <p style="font-size: 0.8em; color: #95a5a6;">Este é um e-mail automático gerado pelo seu monitor no GitHub Actions.</p>
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
        print(f"E-mail HTML enviado com sucesso! ({total_noticias} notícias 100% relevantes)")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

if __name__ == "__main__":
    noticias_filtradas = buscar_noticias_semanais()
    
    # A função agora devolve as duas versões (Texto e HTML)
    texto, html = gerar_corpos_email(noticias_filtradas)
    
    # VOLTOU: Exibe o corpo do e-mail no log (ecrã) para você poder conferir
    print("=== CORPO DO E-MAIL GERADO ===")
    print(texto)
    print("==============================")
    
    # Dispara o e-mail com as duas versões anexadas
    enviar_email(texto, html, len(noticias_filtradas))