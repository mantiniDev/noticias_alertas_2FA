import sqlite3
import os

# Força o Python a usar o caminho absoluto da pasta raiz do projeto
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'mast_dados.db')

def init_db():
    """Cria a tabela no banco de dados caso ela não exista."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_noticias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_noticia TEXT,
            nome_fonte TEXT,
            titulo_noticia TEXT,
            palavra_extraida TEXT,
            termo_base TEXT,
            link TEXT UNIQUE
        )
    ''')
    conn.commit()
    conn.close()

def salvar_noticias(noticias):
    """Recebe a lista de notícias filtradas e salva no banco de dados."""
    if not noticias:
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    novos_registros = 0
    for noti in noticias:
        try:
            cursor.execute('''
                INSERT INTO historico_noticias 
                (data_noticia, nome_fonte, titulo_noticia, palavra_extraida, termo_base, link)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                noti['data_obj'].strftime("%Y-%m-%d %H:%M:%S"),
                noti.get('fonte', 'Desconhecida'),
                noti.get('titulo', 'Sem Título'),
                noti.get('palavra_extraida', 'Não mapeado'), # Proteção contra falhas
                noti.get('termo_base', 'Não mapeado'),       # Proteção contra falhas
                noti['link']
            ))
            novos_registros += 1
        except sqlite3.IntegrityError:
            # A notícia já existe no banco, então o script ignora silenciosamente
            continue
        except Exception as e:
            print(f"❌ Erro ao tentar salvar uma notícia no banco: {e}")
            
    conn.commit()
    conn.close()
    
    if novos_registros > 0:
        print(f"🗄️ Banco de Dados: {novos_registros} novos registros arquivados com sucesso!")
    else:
        print("🗄️ Banco de Dados: Nenhuma notícia nova para arquivar (todas já existiam no banco).")

def buscar_dados_para_pdf(limite=100):
    """Busca as últimas N notícias do banco de dados para montar o relatório PDF."""
    if not os.path.exists(DB_PATH):
        return []
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Pega a data, fonte, palavra extraída, termo, título e link
        cursor.execute('''
            SELECT data_noticia, nome_fonte, palavra_extraida, termo_base, titulo_noticia, link
            FROM historico_noticias 
            ORDER BY id DESC LIMIT ?
        ''', (limite,))
        dados = cursor.fetchall()
        return dados
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()