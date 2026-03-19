import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'mast_dados.db')

def ler_dados(limite=15):
    """Lê os últimos N registros do banco de dados e exibe no terminal."""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ O banco de dados não foi encontrado em: {DB_PATH}")
        print("Certifique-se de já ter rodado o 'main.py' pelo menos uma vez para criar o arquivo.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Busca os registros ordenados do mais recente para o mais antigo
        cursor.execute('''
            SELECT id, data_noticia, nome_fonte, palavra_extraida, termo_base, titulo_noticia 
            FROM historico_noticias 
            ORDER BY id DESC LIMIT ?
        ''', (limite,))
        
        registros = cursor.fetchall()
        
        if not registros:
            print("📭 O banco de dados existe, mas ainda está vazio. Nenhuma notícia foi salva.")
            return

        print(f"\n{'='*100}")
        print(f"📊 ÚLTIMOS {len(registros)} REGISTROS DO BANCO DE DADOS MAST")
        print(f"{'='*100}\n")

        for reg in registros:
            id_reg, data, fonte, palavra, termo, titulo = reg
            print(f"[{id_reg}] 📅 DATA: {data}  |  🏛️ FONTE: {fonte}")
            print(f"     🎯 GATILHO: '{termo}'  ->  📄 TEXTO EXTRAÍDO: '{palavra}'")
            print(f"     📰 TÍTULO: {titulo}")
            print("-" * 100)

        # Mostra o total absoluto de registros já salvos na história
        cursor.execute('SELECT COUNT(*) FROM historico_noticias')
        total = cursor.fetchone()[0]
        print(f"\n📌 TOTAL DE NOTÍCIAS ARQUIVADAS NO BANCO ATÉ HOJE: {total}\n")

    except sqlite3.OperationalError as e:
        print(f"❌ Erro estrutural ao ler o banco. A tabela já foi criada? Detalhes: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Você pode mudar o número 15 abaixo para 50, 100, ou o que desejar ver de cada vez.
    ler_dados(15)