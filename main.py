# main.py
from datetime import datetime, timedelta
from core.scraper import buscar_noticias_semanais
from core.notifier import gerar_corpos_email, enviar_email
from core.database import init_db, buscar_dados_para_csv
from core.csv_generator import gerar_csv_relatorio

if __name__ == "__main__":
    print("Iniciando o MAST - Monitoramento Automatizado...")

    # 0. Inicializa os Bancos de Dados
    init_db()

    # 1. Busca as notícias da rodada atual
    noticias_filtradas = buscar_noticias_semanais()

    # 2. Gera o CSV com registros apenas da janela de 2 dias
    data_limite = datetime.now() - timedelta(days=2)
    dados_banco = buscar_dados_para_csv(limite=100, desde=data_limite)
    caminho_do_csv = gerar_csv_relatorio(dados_banco)

    # 3. Gera o corpo do e-mail
    texto, html = gerar_corpos_email(noticias_filtradas)

    # 4. Exibe no log
    print(f"\nTotal de notícias validadas como 'NOVO': {len(noticias_filtradas)}\n")
    print("=== CORPO DO E-MAIL GERADO ===")
    print(texto)
    print("==============================\n")

    # 5. Envia sempre — com alertas ou com mensagem de "sem novidades"
    enviar_email(texto, html, len(noticias_filtradas), anexo_path=caminho_do_csv)