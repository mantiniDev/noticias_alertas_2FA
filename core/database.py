import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'mast_dados.db')

def init_db():
    """Cria as tabelas do Scraper e do Filtro caso não existam."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabela 1: Dados Brutos do Scraper
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banco_scraper (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_noticia TEXT,
            nome_fonte TEXT,
            titulo_noticia TEXT,
            palavra_scraper TEXT,
            termo_base TEXT,
            link TEXT UNIQUE
        )
    ''')

    # Tabela 2: Auditoria e Status do Filtro
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banco_filter (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            palavra_filtrada TEXT,
            termo_base TEXT,
            status TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def verificar_status_noticia(link):
    """Verifica se a notícia já existe no banco para classificá-la como 'repetido'."""
    if not os.path.exists(DB_PATH):
        return False
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM banco_filter WHERE link = ?", (link,))
    resultado = cursor.fetchone()
    conn.close()
    
    return resultado is not None # Retorna True se já existe (é repetida)

def salvar_auditoria(noticia_bruta, status, palavra_filtrada=None, termo_base=None):
    """
    Salva a notícia nos dois bancos simultaneamente.
    Status esperados: 'novo', 'repetido', 'bloqueado', 'irrelevante'
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    link = noticia_bruta['link']
    
    # 1. Salva no Banco Scraper (Dados Brutos)
    try:
        cursor.execute('''
            INSERT INTO banco_scraper 
            (data_noticia, nome_fonte, titulo_noticia, palavra_scraper, termo_base, link)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            noticia_bruta['data_obj'].strftime("%Y-%m-%d %H:%M:%S"),
            noticia_bruta.get('fonte', 'Desconhecida'),
            noticia_bruta.get('titulo', 'Sem Título'),
            palavra_filtrada if palavra_filtrada else 'N/A',
            termo_base if termo_base else 'N/A',
            link
        ))
    except sqlite3.IntegrityError:
        pass # Se já existir no banco scraper, apenas ignoramos
        
    # 2. Salva no Banco Filter (Status)
    try:
        cursor.execute('''
            INSERT INTO banco_filter 
            (link, palavra_filtrada, termo_base, status)
            VALUES (?, ?, ?, ?)
        ''', (
            link,
            palavra_filtrada if palavra_filtrada else 'N/A',
            termo_base if termo_base else 'N/A',
            status
        ))
    except sqlite3.IntegrityError:
        # Se for uma atualização de status, podemos dar um UPDATE
        cursor.execute('''
            UPDATE banco_filter 
            SET status = ?, palavra_filtrada = ?, termo_base = ? 
            WHERE link = ?
        ''', (status, palavra_filtrada, termo_base, link))
        
    conn.commit()
    conn.close()

def buscar_dados_para_csv(limite=500): # Aumentei o limite padrão para 500 para ter uma boa amostragem
    """Busca as notícias do banco de dados (Scraper + Filter) para montar o relatório CSV com o Status."""
    if not os.path.exists(DB_PATH):
        return []
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Faz um JOIN entre as tabelas e agora traz TUDO (incluindo o f.status)
        cursor.execute('''
            SELECT s.data_noticia, s.nome_fonte, f.palavra_filtrada, f.termo_base, s.titulo_noticia, s.link, f.status
            FROM banco_scraper s
            INNER JOIN banco_filter f ON s.link = f.link
            ORDER BY s.id DESC LIMIT ?
        ''', (limite,))
        dados = cursor.fetchall()
        return dados
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()