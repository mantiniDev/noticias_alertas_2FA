import feedparser
import urllib.parse
from datetime import datetime, timedelta
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# --- CONSTANTE DE TRIBUNAIS COMPLETOS ---
TRIBUNAIS = [
    # --- TRIBUNAIS SUPERIORES E FEDERAIS ---
    {"id": "1", "name": "Supremo Tribunal Federal", "acronym": "STF", "url": "https://portal.stf.jus.br/servicos/peticionamento/consultarIndisponibilidade.asp"},
    {"id": "2", "name": "Superior Tribunal de Justiça", "acronym": "STJ", "url": "https://www.stj.jus.br/sites/portalp/Servicos/Comunicacoes-e-indisponibilidade"},
    {"id": "3", "name": "Tribunal Regional Federal da 1ª Região", "acronym": "TRF1", "url": "https://portal.trf1.jus.br/Servicos/PJe/"},
    {"id": "4", "name": "Tribunal Regional Federal da 2ª Região", "acronym": "TRF2", "url": "https://eproc.trf2.jus.br/eproc/externo_controlador.php?acao=processo_disponibilidade_listagem"},
    {"id": "5", "name": "Tribunal Regional Federal da 3ª Região", "acronym": "TRF3", "url": "https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam"},
    {"id": "6", "name": "Tribunal Regional Federal da 4ª Região", "acronym": "TRF4", "url": "https://eproc.trf4.jus.br/eproc2trf4/externo_controlador.php?acao=processo_disponibilidade_listagem"},
    {"id": "7", "name": "Tribunal Regional Federal da 5ª Região", "acronym": "TRF5", "url": "https://pje.trf5.jus.br/pje/ConsultaPublica/listView.seam"},
    {"id": "8", "name": "Tribunal Regional Federal da 6ª Região", "acronym": "TRF6", "url": "https://eproc.trf6.jus.br/eproc/externo_controlador.php?acao=processo_disponibilidade_listagem"},

    # --- TRIBUNAIS DE JUSTIÇA ESTADUAIS (27 TJs) ---
    {"id": "101", "name": "Tribunal de Justiça do Acre", "acronym": "TJAC", "url": "https://pje.tjac.jus.br/pje/ConsultaPublica/listView.seam"},
    {"id": "102", "name": "Tribunal de Justiça de Alagoas", "acronym": "TJAL", "url": "https://www.tjal.jus.br/corregedoria/?pag=indisponibilidade"},
    {"id": "103", "name": "Tribunal de Justiça do Amapá", "acronym": "TJAP", "url": "https://tucujuris.tjap.jus.br/tucujuris/paginas/consultas/indisponibilidade.html"},
    {"id": "104", "name": "Tribunal de Justiça do Amazonas", "acronym": "TJAM", "url": "https://www.tjam.jus.br/index.php/pje-indisponibilidade"},
    {"id": "105", "name": "Tribunal de Justiça da Bahia", "acronym": "TJBA", "url": "http://pje.tjba.jus.br/pje/ConsultaPublica/listView.seam"},
    {"id": "106", "name": "Tribunal de Justiça do Ceará", "acronym": "TJCE", "url": "https://www.tjce.jus.br/pje/indisponibilidade-dos-sistemas-pje/"},
    {"id": "107", "name": "Tribunal de Justiça do Distrito Federal e Territórios", "acronym": "TJDFT", "url": "https://www.tjdft.jus.br/servicos/pje/indisponibilidade-do-pje"},
    {"id": "108", "name": "Tribunal de Justiça do Espírito Santo", "acronym": "TJES", "url": "https://www.tjes.jus.br/pje/indisponibilidade-do-pje/"},
    {"id": "109", "name": "Tribunal de Justiça de Goiás", "acronym": "TJGO", "url": "https://www.tjgo.jus.br/index.php/pje/indisponibilidade"},
    {"id": "110", "name": "Tribunal de Justiça do Maranhão", "acronym": "TJMA", "url": "https://www.tjma.jus.br/pje/indisponibilidade-do-pje"},
    {"id": "111", "name": "Tribunal de Justiça do Mato Grosso", "acronym": "TJMT", "url": "https://pje.tjmt.jus.br/pje/ConsultaPublica/listView.seam"},
    {"id": "112", "name": "Tribunal de Justiça do Mato Grosso do Sul", "acronym": "TJMS", "url": "https://www.tjms.jus.br/esaj/indisponibilidade/"},
    {"id": "113", "name": "Tribunal de Justiça de Minas Gerais", "acronym": "TJMG", "url": "https://pje.tjmg.jus.br/pje/ConsultaPublica/listView.seam"},
    {"id": "114", "name": "Tribunal de Justiça do Pará", "acronym": "TJPA", "url": "https://www.tjpa.jus.br/PortalExterno/servicos/PJE/1199-Indisponibilidade-do-Sistema.xhtml"},
    {"id": "115", "name": "Tribunal de Justiça da Paraíba", "acronym": "TJPB", "url": "https://www.tjpb.jus.br/pje/indisponibilidade-do-pje"},
    {"id": "116", "name": "Tribunal de Justiça do Paraná", "acronym": "TJPR", "url": "https://www.tjpr.jus.br/indisponibilidade-de-sistemas"},
    {"id": "117", "name": "Tribunal de Justiça de Pernambuco", "acronym": "TJPE", "url": "https://www.tjpe.jus.br/pje/indisponibilidade-do-pje"},
    {"id": "118", "name": "Tribunal de Justiça do Piauí", "acronym": "TJPI", "url": "https://www.tjpi.jus.br/pje/indisponibilidade-do-pje"},
    {"id": "119", "name": "Tribunal de Justiça do Rio de Janeiro", "acronym": "TJRJ", "url": "https://www.tjrj.jus.br/web/guest/servicos/pje"},
    {"id": "120", "name": "Tribunal de Justiça do Rio Grande do Norte", "acronym": "TJRN", "url": "https://www.tjrn.jus.br/pje/indisponibilidade-pje/"},
    {"id": "121", "name": "Tribunal de Justiça do Rio Grande do Sul", "acronym": "TJRS", "url": "https://eproc1g.tjrs.jus.br/eproc/externo_controlador.php?acao=processo_disponibilidade_listagem"},
    {"id": "122", "name": "Tribunal de Justiça de Rondônia", "acronym": "TJRO", "url": "https://www.tjro.jus.br/pje/indisponibilidade-do-pje"},
    {"id": "123", "name": "Tribunal de Justiça de Roraima", "acronym": "TJRR", "url": "https://www.tjrr.jus.br/index.php/pje-indisponibilidade"},
    {"id": "124", "name": "Tribunal de Justiça de Santa Catarina", "acronym": "TJSC", "url": "https://eproc1g.tjsc.jus.br/eproc/externo_controlador.php?acao=processo_disponibilidade_listagem"},
    {"id": "125", "name": "Tribunal de Justiça de São Paulo", "acronym": "TJSP", "url": "https://www.tjsp.jus.br/Indisponibilidade/Comunicados"},
    {"id": "126", "name": "Tribunal de Justiça de Sergipe", "acronym": "TJSE", "url": "https://www.tjse.jus.br/pje/indisponibilidade-do-pje"},
    {"id": "127", "name": "Tribunal de Justiça do Tocantins", "acronym": "TJTO", "url": "https://eproc1g.tjto.jus.br/eprocv2_prod_1g/externo_controlador.php?acao=processo_disponibilidade_listagem"},

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
    {"id": "302", "name": "TRE Minas Gerais", "acronym": "TRE-MG", "url": "https://www.tre-mg.jus.br/servicos-judiciais/processo-judicial-eletronico-pje/indisponibilidade-do-sistema-pje"},
    {"id": "303", "name": "TRE Rio de Janeiro", "acronym": "TRE-RJ", "url": "https://www.tre-rj.jus.br/servicos-judiciais/pje/indisponibilidade-do-sistema-pje"}
]

# --- NOVAS PALAVRAS E FRASES ESPECÍFICAS ---
TERMOS_ESPECIFICOS = [
    '"2FA PJE"', '"MFA PJE"', '"dois fatores PJE"', '"duplo fator PJE"', 
    '"duplo fator EPROC"', '"duplo fator ESAJ"', '"duplo fator PROJUDI"', 
    '"PDPJ"', '"sistema tribunal"', 
    '"migração sistema tribunal"', '"PJE indisponibilidade"', 
    '"portaria CNJ 140/2024"', '"tribunal pdpj"', '"tribunal authenticator"', 
    '"2FA obrigatória"', '"golpe do advogado"', '"migração TJPR EPROC"', 
    '"Jus.br"', '"instabilidade PJE"', '"instabilidade pdpj"', '"instabilidade eproc"', 
    '"instabilidade esaj"', '"instabilidade projudi"', '"instabilidade TRT"', 
    '"instabilidade dos principais tribunais EPROC"'
]

def extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias):
    """Lê o RSS e adiciona à lista de notícias, evitando duplicatas"""
    feed = feedparser.parse(url_rss)
    for entry in feed.entries:
        if hasattr(entry, 'published_parsed'):
            data_publicacao = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            
            if data_publicacao >= data_limite and entry.link not in links_ja_coletados:
                todas_noticias.append({
                    'titulo': entry.title,
                    'link': entry.link,
                    'data_obj': data_publicacao
                })
                links_ja_coletados.add(entry.link)

def buscar_noticias_semanais():
    todas_noticias = []
    links_ja_coletados = set()
    data_limite = datetime.now() - timedelta(days=7)

    # =====================================================================
    # PARTE 1: BUSCA CRUZADA OTIMIZADA (TRIBUNAIS + BLOCOS TEMÁTICOS)
    # =====================================================================
    # Dividimos os seus termos em blocos para não estourar o limite do Google
    # e evitamos palavras soltas (ex: apenas "acesso") para reduzir o ruído.
    blocos_tematicos = [
        # 1. Nomes dos Sistemas
        '("PJE" OR "PDPJ" OR "EPROC" OR "ESAJ" OR "PROJUDI" OR "Jus.br" OR "sistema próprio")',
        
        # 2. Segurança e Autenticação
        '("2FA" OR "MFA" OR "duplo fator" OR "dois fatores" OR "autenticação" OR "multifator" OR "authenticator" OR "código de autenticação" OR "Single Sign-On" OR "SSO" OR "segurança digital")',
        
        # 3. Infraestrutura e Chaves
        '("captcha" OR "WAF" OR "token" OR "certificate" OR "certificado digital")',
        
        # 4. Status e Eventos de TI
        '("novo sistema" OR "migração" OR "descontinuado" OR "deprecado" OR "descontinuar" OR "instabilidade PJE" OR "indisponibilidade" OR "ciberataque")',
        
        # 5. Acessos e Credenciais (Agrupados para dar contexto e evitar falsos positivos)
        '("renovação de senha" OR "redefinição de senha" OR "credencial" OR "troca de senha" OR "código de acesso")',
        
        # 6. Legislação Específica
        '("portaria nº 140/2024" OR "portaria CNJ nº 140" OR "resolução nº 335/2020" OR "resolução CNJ nº 335/2020")'
    ]

    siglas = [tribunal["acronym"] for tribunal in TRIBUNAIS]
    tamanho_lote_tribunais = 10
    lotes_siglas = [siglas[i:i + tamanho_lote_tribunais] for i in range(0, len(siglas), tamanho_lote_tribunais)]
    
    print(f"Iniciando Fase 1: Cruzando {len(siglas)} Tribunais com {len(blocos_tematicos)} blocos temáticos de TI...")
    
    for i, lote in enumerate(lotes_siglas, 1):
        query_tribunais = "(" + " OR ".join(f'"{sigla}"' for sigla in lote) + ")"
        
        # Roda a busca dos tribunais contra CADA bloco temático separadamente
        for bloco in blocos_tematicos:
            query_final = f"{bloco} AND {query_tribunais}"
            query_codificada = urllib.parse.quote(query_final)
            
            url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
            extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias)
            time.sleep(1.5) # Pausa obrigatória para o Google não bloquear o script

    # =====================================================================
    # PARTE 2: BUSCA PELAS FRASES ESPECÍFICAS EXATAS
    # =====================================================================
    print("Iniciando Fase 2: Busca pelas frases e ocorrências específicas...")
    tamanho_lote_termos = 6
    lotes_termos = [TERMOS_ESPECIFICOS[i:i + tamanho_lote_termos] for i in range(0, len(TERMOS_ESPECIFICOS), tamanho_lote_termos)]
    
    for i, lote in enumerate(lotes_termos, 1):
        query_frases = "(" + " OR ".join(lote) + ")"
        query_codificada = urllib.parse.quote(query_frases)
        
        url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias)
        time.sleep(1.5)

    # Ordena o resultado final cronologicamente (da mais recente para a mais antiga)
    todas_noticias.sort(key=lambda x: x['data_obj'], reverse=True)
    return todas_noticias

def gerar_texto_email(noticias):
    hoje = datetime.now().strftime("%d/%m/%Y")
    uma_semana_atras = (datetime.now() - timedelta(days=7)).strftime("%d/%m/%Y")
    
    texto = f"Olá,\n\nResumo de notícias OSINT ({uma_semana_atras} até {hoje}) sobre Sistemas e Tribunais:\n\n"
    
    if not noticias:
        texto += "Nenhuma notícia encontrada nos últimos 7 dias.\n"
        return texto

    for i, noticia in enumerate(noticias, 1):
        data_formatada = noticia['data_obj'].strftime("%d/%m/%Y às %H:%M")
        texto += f"{i}. {noticia['titulo']}\n"
        texto += f"   Publicado em: {data_formatada}\n"
        texto += f"   Link: {noticia['link']}\n\n"
        
    texto += "---\nEste é um e-mail automático gerado pelo seu monitor no GitHub Actions."
    return texto

def enviar_email(corpo_email, total_noticias):
    remetente = os.environ.get('EMAIL_REMETENTE')
    senha = os.environ.get('EMAIL_SENHA')
    destinatario = os.environ.get('EMAIL_DESTINATARIO')

    if not remetente or not senha:
        print("Erro: Credenciais não configuradas no GitHub Secrets.")
        return

    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = f"Monitor de Tribunais e Sistemas - {datetime.now().strftime('%d/%m/%Y')}"
    msg.attach(MIMEText(corpo_email, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        print(f"E-mail enviado com sucesso! ({total_noticias} notícias mapeadas)")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

if __name__ == "__main__":
    noticias = buscar_noticias_semanais()
    texto = gerar_texto_email(noticias)
    print(texto)
    enviar_email(texto, len(noticias))