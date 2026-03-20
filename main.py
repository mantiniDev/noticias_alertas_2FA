# main.py
from core.scraper import buscar_noticias_semanais
from core.notifier import gerar_corpos_email, enviar_email
from core.database import init_db, buscar_dados_para_csv # Removido salvar_noticias (feito no scraper agora)
from core.csv_generator import gerar_csv_relatorio

if __name__ == "__main__":
    print("Iniciando o MAST - Monitoramento Automatizado...")
    
    # 0. Inicializa os Bancos de Dados de Scraper e Filtro
    init_db()
    
    # 1. Busca as notícias. Durante a busca, o scraper já arquiva tudo sozinho e devolve apenas as 'novas'
    noticias_filtradas = buscar_noticias_semanais()
    
    # 2. Lê os dados válidos do banco e gera o CSV de Relatório
    dados_banco = buscar_dados_para_csv(limite=100) # Pega os últimos 100 registros novos
    caminho_do_csv = gerar_csv_relatorio(dados_banco)

    # 3. Gera o corpo do e-mail
    texto, html = gerar_corpos_email(noticias_filtradas)

    # 4. Exibe no log
    print(f"\nTotal de notícias validadas como 'NOVO': {len(noticias_filtradas)}\n")
    print("=== CORPO DO E-MAIL GERADO ===")
    print(texto)
    print("==============================\n")

    # 5. Envia o e-mail passando o caminho do CSV gerado
    enviar_email(texto, html, len(noticias_filtradas), anexo_path=caminho_do_csv)