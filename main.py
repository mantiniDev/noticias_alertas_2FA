# main.py
from core.scraper import buscar_noticias_semanais
from core.notifier import gerar_corpos_email, enviar_email
from core.database import init_db, salvar_noticias, buscar_dados_para_pdf
from core.pdf_generator import gerar_pdf_relatorio

if __name__ == "__main__":
    print("Iniciando o MAST - Monitoramento Automatizado...")
    
    # 0. Inicializa o Banco de Dados
    init_db()
    
    # 1. Busca e filtra as notícias
    noticias_filtradas = buscar_noticias_semanais()
    
    # 2. Guarda no Banco de Dados SQLite
    salvar_noticias(noticias_filtradas)
    
    # 3. Lê os dados recém-salvos e gera o PDF de Relatório
    dados_banco = buscar_dados_para_pdf(limite=100) # Pega os últimos 100 registros
    caminho_do_pdf = gerar_pdf_relatorio(dados_banco)

    # 4. Gera o corpo do e-mail
    texto, html = gerar_corpos_email(noticias_filtradas)

    # 5. Exibe no log
    print(f"\nTotal de notícias validadas pela malha fina: {len(noticias_filtradas)}\n")
    print("=== CORPO DO E-MAIL GERADO ===")
    print(texto)
    print("==============================\n")

    # 6. Envia o e-mail passando o caminho do PDF gerado
    enviar_email(texto, html, len(noticias_filtradas), anexo_pdf=caminho_do_pdf)