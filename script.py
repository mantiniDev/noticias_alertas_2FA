import feedparser
import urllib.parse
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

def buscar_e_filtrar_noticias():
    query_base = '("PJE" OR "PDPJ" OR "EPROC" OR "PROJUDI" OR "CNJ" OR "autenticação" OR "certificado digital")'
    query_codificada = urllib.parse.quote(query_base)
    url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    
    print("Buscando notícias no Google News...")
    feed = feedparser.parse(url_rss)
    
    termos_auth_seguranca = [
        "2fa", "mfa", "duplo fator", "dois fatores", "autenticação", "multifator", 
        "authenticator", "código de autenticação", "single sign-on", "sso", "segurança digital",
        "captcha", "waf", "token", "certificate", "certificado digital"
    ]
    termos_normas = [
        "portaria nº 140/2024", "portaria cnj nº 140", "resolução nº 335/2020", "resolução cnj nº 335"
    ]
    termos_sistemas_mudancas = [
        "novo sistema", "migração", "descontinuado", "deprecado", "descontinuar", "mudança",
        "pje", "pdpj", "eproc", "esaj", "projudi", "sistema próprio", "jus.br",
        "renovação", "senha", "credencial", "acesso", "redefinição", "troca", "código"
    ]
    filtro_especifico = ["processo judicial", "justiça digital", "certificado digital", "certificados digitais"]

    noticias_filtradas = []

    for entry in feed.entries:
        titulo = entry.title.lower()
        
        passou_filtro_especifico = any(termo in titulo for termo in filtro_especifico)
        tem_auth = any(termo in titulo for termo in termos_auth_seguranca)
        tem_sistema = any(termo in titulo for termo in termos_sistemas_mudancas)
        tem_norma = any(termo in titulo for termo in termos_normas)

        if passou_filtro_especifico and (tem_auth or tem_sistema or tem_norma):
            noticias_filtradas.append({
                'titulo': entry.title,
                'link': entry.link,
                'data': entry.published
            })

    return noticias_filtradas

def gerar_texto_email(noticias):
    hoje = datetime.now().strftime("%d/%m/%Y")
    texto = f"Olá,\n\nAqui está o seu resumo de notícias sobre Justiça Digital e Segurança ({hoje}):\n\n"
    
    if not noticias:
        texto += "Nenhuma notícia relevante encontrada para os filtros de hoje.\n"
        return texto

    for i, noticia in enumerate(noticias, 1):
        texto += f"{i}. {noticia['titulo']}\n"
        texto += f"   Data: {noticia['data']}\n"
        texto += f"   Link: {noticia['link']}\n\n"
        
    texto += "---\nEste é um e-mail automático gerado pelo seu monitor de OSINT no GitHub Actions."
    return texto

def enviar_email(corpo_email):
    # Pega as credenciais escondidas no GitHub Secrets
    remetente = os.environ.get('EMAIL_REMETENTE')
    senha = os.environ.get('EMAIL_SENHA')
    destinatario = os.environ.get('EMAIL_DESTINATARIO') # Pode ser o mesmo que o remetente

    if not remetente or not senha:
        print("Erro: Credenciais de e-mail não encontradas nas variáveis de ambiente.")
        return

    # Configuração da mensagem
    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = f"Notícias OSINT: Justiça Digital e Segurança - {datetime.now().strftime('%d/%m/%Y')}"
    msg.attach(MIMEText(corpo_email, 'plain'))

    try:
        # Conectando ao servidor do Gmail
        print("Conectando ao servidor de e-mail...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() # Inicia a criptografia
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        print("E-mail enviado com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

if __name__ == "__main__":
    noticias = buscar_e_filtrar_noticias()
    texto = gerar_texto_email(noticias)
    
    # Exibe no log do GitHub (para você poder conferir se quiser)
    print(texto)
    
    # Dispara o e-mail
    enviar_email(texto)