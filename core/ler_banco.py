# core/ler_banco.py
import sqlite3
import os

# Força o Python a voltar uma pasta (..) para encontrar a raiz do projeto
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'mast_dados.db')

def ler_dados(limite=20):
    """Lê os últimos N registros do banco de dados unidos (Scraper + Filter) e exibe no terminal."""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ O banco de dados não foi encontrado em: {DB_PATH}")
        print("Certifique-se de já ter rodado o 'main.py' pelo menos uma vez para criar o arquivo.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Busca os registros fazendo o JOIN entre a tabela bruta e a tabela de filtro
        cursor.execute('''
            SELECT s.id, s.data_noticia, s.nome_fonte, f.palavra_filtrada, f.termo_base, s.titulo_noticia, f.status
            FROM banco_scraper s
            INNER JOIN banco_filter f ON s.link = f.link
            ORDER BY s.id DESC LIMIT ?
        ''', (limite,))
        
        registros = cursor.fetchall()
        
        if not registros:
            print("📭 O banco de dados existe, mas ainda está vazio. Nenhuma notícia foi salva.")
            return

        print(f"\n{'='*100}")
        print(f"📊 ÚLTIMOS {len(registros)} REGISTROS DO BANCO DE DADOS MAST (COM STATUS)")
        print(f"{'='*100}\n")

        for reg in registros:
            id_reg, data, fonte, palavra, termo, titulo, status = reg
            
            # Formatação visual do Status para o terminal
            if status == 'novo':
                cor_status = "🟢 NOVO"
            elif status == 'repetido':
                cor_status = "🟡 REPETIDO"
            elif status == 'bloqueado':
                cor_status = "🔴 BLOQUEADO"
            else:
                cor_status = f"⚪ {str(status).upper()}"

            print(f"[{id_reg}] 📅 {data}  |  🏛️ FONTE: {fonte}  |  {cor_status}")
            print(f"     🎯 GATILHO: '{termo}'  ->  📄 TEXTO EXTRAÍDO: '{palavra}'")
            print(f"     📰 TÍTULO: {titulo}")
            print("-" * 100)

        # Mostra o total absoluto de registros já salvos na história
        cursor.execute('SELECT COUNT(*) FROM banco_scraper')
        total = cursor.fetchone()[0]
        print(f"\n📌 TOTAL DE NOTÍCIAS ARQUIVADAS NO BANCO ATÉ HOJE: {total}\n")

    except sqlite3.OperationalError as e:
        print(f"❌ Erro estrutural ao ler o banco. Detalhes: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    ler_dados(100)