# core/csv_generator.py
import os
import csv

def gerar_csv_relatorio(dados):
    """Gera um arquivo CSV com os dados históricos dos dois bancos (Scraper + Filter) e retorna o caminho."""
    
    # O CSV será salvo temporariamente na raiz do projeto
    caminho_csv = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Histórico.csv'))
    
    # utf-8-sig ajuda o Excel a ler os acentos corretamente
    with open(caminho_csv, mode='w', newline='', encoding='utf-8-sig') as arquivo_csv:
        writer = csv.writer(arquivo_csv, delimiter=';') 
        
        # CABEÇALHO AUDITORIA PROFUNDA
        writer.writerow(['Data da Notícia', 'Nome da Fonte', 'Título', 'Status', 'Motivo da Decisão', 'Lista do Gatilho', 'Palavra Capturada', 'Link da Notícia'])
        
        if dados:
            for row in dados:
                # row agora contém 7 itens: data, fonte, palavra, termo, titulo, link, status
                writer.writerow(row)
                
    print(f"📊 CSV de Auditoria Gerado com sucesso: {caminho_csv}")
    return caminho_csv