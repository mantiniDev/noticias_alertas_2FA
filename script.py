import feedparser
import urllib.parse
from datetime import datetime, timedelta
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# --- CONSTANTE DE TRIBUNAIS (Convertida para Python) ---
TRIBUNAIS = [
    # Superiores e Federais
    {"id": "1", "name": "Supremo Tribunal Federal", "acronym": "STF", "url": "https://portal.stf.jus.br/..."},
    {"id": "2", "name": "Superior Tribunal de Justiça", "acronym": "STJ", "url": "..."},
    {"id": "3", "name": "TRF 1ª Região", "acronym": "TRF1", "url": "..."},
    {"id": "4", "name": "TRF 2ª Região", "acronym": "TRF2", "url": "..."},
    {"id": "5", "name": "TRF 3ª Região", "acronym": "TRF3", "url": "..."},
    {"id": "6", "name": "TRF 4ª Região", "acronym": "TRF4", "url": "..."},
    {"id": "7", "name": "TRF 5ª Região", "acronym": "TRF5", "url": "..."},
    {"id": "8", "name": "TRF 6ª Região", "acronym": "TRF6", "url": "..."},
    # TJs Estaduais (Exemplos, você pode colar a lista completa aqui)
    {"id": "101", "name": "TJ Acre", "acronym": "TJAC", "url": "..."},
    {"id": "105", "name": "TJ Bahia", "acronym": "TJBA", "url": "..."},
    {"id": "119", "name": "TJ Rio de Janeiro", "acronym": "TJRJ", "url": "..."},
    {"id": "125", "name": "TJ São Paulo", "acronym": "TJSP", "url": "..."},
    # TRTs e TREs (Exemplos)
    {"id": "202", "name": "TRT 2ª Região", "acronym": "TRT2", "url": "..."},
    {"id": "300", "name": "TSE (Nacional)", "acronym": "TSE", "url": "..."}
    # NOTA: Cole todos os seus dicionários aqui seguindo esse formato {"chave": "valor"}
]

def buscar_noticias_semanais():
    # Termos técnicos que obrigam a notícia a ser sobre sistemas/segurança
    termos_sistemas = '("PJE" OR "PDPJ" OR "EPROC" OR "PROJUDI" OR "autenticação" OR "certificado digital" OR "indisponibilidade" OR "ciberataque")'
    
    # Extrai apenas as siglas da lista de tribunais
    siglas = [tribunal["acronym"] for tribunal in TRIBUNAIS]
    
    # Divide as siglas em lotes de 10 para não estourar o limite de caracteres da URL do Google
    tamanho_lote = 10
    lotes_siglas = [siglas[i:i + tamanho_lote] for i in range(0, len(siglas), tamanho_lote)]
    
    todas_noticias = []
    links_ja_coletados = set() # Evita notícias duplicadas se o Google retornar a mesma em lotes diferentes
    
    data_limite = datetime.now() - timedelta(days=100)

    for i, lote in enumerate(lotes_siglas, 1):
        print(f"Buscando lote {i}/{len(lotes_siglas)} de tribunais...")
        
        # Monta a parte da query com os tribunais (Ex: "STF" OR "STJ" OR "TRF1"...)
        query_tribunais = "(" + " OR ".join(f'"{sigla}"' for sigla in lote) + ")"
        
        # Junta os sistemas com os tribunais (Ex: (Sistemas) AND (Tribunais))
        query_final = f"{termos_sistemas} AND {query_tribunais}"
        query_codificada = urllib.parse.quote(query_final)
        
        url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        feed = feedparser.parse(url_rss)

        for entry in feed.entries:
            if hasattr(entry, 'published_parsed'):
                data_publicacao = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                
                # Verifica a data E se o link já não foi adicionado antes
                if data_publicacao >= data_limite and entry.link not in links_ja_coletados:
                    todas_noticias.append({
                        'titulo': entry.title,
                        'link': entry.link,
                        'data_obj': data_publicacao
                    })
                    links_ja_coletados.add(entry.link)
        
        # Pequena pausa para evitar bloqueio do Google (Rate Limit)
        time.sleep(1)

    # Ordena da mais recente para a mais antiga
    todas_noticias.sort(key=lambda x: x['data_obj'], reverse=True)
    return todas_noticias

def gerar_texto_email(noticias):
    hoje = datetime.now().strftime("%d/%m/%Y")
    uma_semana_atras = (datetime.now() - timedelta(days=7)).strftime("%d/%m/%Y")
    
    texto = f"Olá,\n\nResumo de notícias OSINT ({uma_semana_atras} até {hoje}) para Tribunais e Sistemas:\n\n"
    
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
        print("Erro: Credenciais não configuradas.")
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
        print(f"E-mail enviado com sucesso! ({total_noticias} notícias)")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

if __name__ == "__main__":
    noticias = buscar_noticias_semanais()
    texto = gerar_texto_email(noticias)
    print(texto)
    enviar_email(texto, len(noticias))