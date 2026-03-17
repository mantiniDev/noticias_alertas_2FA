# main.py
from core.scraper import buscar_noticias_semanais
from core.notifier import gerar_corpos_email, enviar_email

if __name__ == "__main__":
    print("Iniciando o MAST - Monitoramento Automatizado...")
    
    # 1. Busca e filtra as notícias
    noticias_filtradas = buscar_noticias_semanais()
    
    # 2. Gera o corpo do e-mail
    texto, html = gerar_corpos_email(noticias_filtradas)

    # 3. Exibe no log
    print(f"\nTotal de notícias validadas pela malha fina: {len(noticias_filtradas)}\n")
    print("=== CORPO DO E-MAIL GERADO ===")
    print(texto)
    print("==============================\n")

    # 4. Envia o e-mail
    enviar_email(texto, html, len(noticias_filtradas))