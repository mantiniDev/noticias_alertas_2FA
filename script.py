import feedparser
import urllib.parse
from datetime import datetime

def buscar_e_filtrar_noticias():
    # 1. Busca ampla no Google News RSS (focada no ecossistema e segurança)
    # Mantemos a busca do Google mais enxuta para evitar erros na URL
    query_base = '("PJE" OR "PDPJ" OR "EPROC" OR "PROJUDI" OR "CNJ" OR "autenticação" OR "certificado digital")'
    query_codificada = urllib.parse.quote(query_base)
    url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    
    print("Buscando notícias no Google News...")
    feed = feedparser.parse(url_rss)
    
    # 2. Definindo as palavras-chave para o filtro local rigoroso
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
    
    # Filtro final exigido (deve conter pelo menos um destes para ser aprovado)
    filtro_especifico = ["processo judicial", "justiça digital", "certificado digital", "certificados digitais", "2FA"]

    noticias_filtradas = []

    # 3. Analisando e filtrando as notícias
    for entry in feed.entries:
        titulo = entry.title.lower()
        # O Google News RSS geralmente não traz um sumário longo, então focamos no título
        
        # Verifica se atende ao filtro específico final
        passou_filtro_especifico = any(termo in titulo for termo in filtro_especifico)
        
        # Verifica se tem relevância com os outros grupos (opcional, mas recomendado para refinar)
        tem_auth = any(termo in titulo for termo in termos_auth_seguranca)
        tem_sistema = any(termo in titulo for termo in termos_sistemas_mudancas)
        tem_norma = any(termo in titulo for termo in termos_normas)

        # Lógica: Se passou no filtro específico E tem a ver com auth/sistemas/normas
        if passou_filtro_especifico and (tem_auth or tem_sistema or tem_norma):
            noticias_filtradas.append({
                'titulo': entry.title,
                'link': entry.link,
                'data': entry.published
            })

    return noticias_filtradas

def gerar_texto_email(noticias):
    # 4. Formatação do texto para o e-mail
    hoje = datetime.now().strftime("%d/%m/%Y")
    texto = f"Olá,\n\nAqui está o seu resumo diário de notícias sobre Justiça Digital e Segurança ({hoje}):\n\n"
    
    if not noticias:
        texto += "Nenhuma notícia relevante encontrada para os filtros de hoje.\n"
        return texto

    for i, noticia in enumerate(noticias, 1):
        texto += f"{i}. {noticia['titulo']}\n"
        texto += f"   Data: {noticia['data']}\n"
        texto += f"   Link: {noticia['link']}\n\n"
        
    texto += "---\nEste é um e-mail automático gerado pelo seu monitor de OSINT."
    return texto

# Execução do script
if __name__ == "__main__":
    noticias_encontradas = buscar_e_filtrar_noticias()
    corpo_email = gerar_texto_email(noticias_encontradas)
    
    print("\n--- RESULTADO PARA O E-MAIL ---\n")
    print(corpo_email)