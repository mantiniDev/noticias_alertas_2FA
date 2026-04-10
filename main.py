# main.py
from datetime import datetime, timedelta
from core.scraper import buscar_noticias_semanais
from core.notifier import gerar_corpos_email, enviar_email
from core.database import init_db, buscar_dados_para_csv
from core.csv_generator import gerar_csv_relatorio

if __name__ == "__main__":
    print("Iniciando o MAST - Monitoramento Automatizado...")

    # 0. Inicializa os Bancos de Dados de Scraper e Filtro
    init_db()

    # 1. Busca as notícias da rodada atual (scraper já arquiva tudo e devolve só as 'novas')
    noticias_filtradas = buscar_noticias_semanais()

    # 2. Lê os dados do banco APENAS da janela de 2 dias (alinhado com a rodada atual)
    #    e gera o CSV de Relatório
    data_limite = datetime.now() - timedelta(days=2)
    dados_banco = buscar_dados_para_csv(limite=100, desde=data_limite)
    caminho_do_csv = gerar_csv_relatorio(dados_banco)

    # 3. Exibe no log
    print(f"\nTotal de notícias validadas como 'NOVO': {len(noticias_filtradas)}\n")

    # 4. Só envia e-mail se houver alertas reais — evita spam diário sem conteúdo
    if noticias_filtradas:
        texto, html = gerar_corpos_email(noticias_filtradas)

        print("=== CORPO DO E-MAIL GERADO ===")
        print(texto)
        print("==============================\n")

        enviar_email(texto, html, len(noticias_filtradas), anexo_path=caminho_do_csv)
    else:
        print("Nenhuma notícia nova encontrada. E-mail não enviado.")