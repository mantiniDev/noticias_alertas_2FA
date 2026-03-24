import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'mast_dados.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabela 1: Scraper (Dados Brutos Completos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banco_scraper (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_noticia TEXT,
            nome_fonte TEXT,
            titulo_noticia TEXT,
            resumo_noticia TEXT,
            link TEXT UNIQUE
        )
    ''')

    # Tabela 2: Filter (Auditoria Profunda da Malha Fina)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banco_filter (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            status TEXT,
            motivo TEXT,
            palavra_encontrada TEXT,
            termo_base TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def verificar_status_noticia(link):
    if not os.path.exists(DB_PATH): return False
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM banco_filter WHERE link = ?", (link,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None 

def salvar_auditoria(noticia_bruta, status, motivo, palavra_encontrada, termo_base):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    link = noticia_bruta['link']
    
    # 1. Grava os dados brutos
    try:
        cursor.execute('''
            INSERT INTO banco_scraper 
            (data_noticia, nome_fonte, titulo_noticia, resumo_noticia, link)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            noticia_bruta['data_obj'].strftime("%Y-%m-%d %H:%M:%S"),
            noticia_bruta.get('fonte', 'Desconhecida'),
            noticia_bruta.get('titulo', 'Sem Título'),
            noticia_bruta.get('resumo', 'Sem Resumo'),
            link
        ))
    except sqlite3.IntegrityError:
        pass 
        
    # 2. Grava a decisão do filtro
    try:
        cursor.execute('''
            INSERT INTO banco_filter 
            (link, status, motivo, palavra_encontrada, termo_base)
            VALUES (?, ?, ?, ?, ?)
        ''', (link, status, motivo, palavra_encontrada, termo_base))
    except sqlite3.IntegrityError:
        cursor.execute('''
            UPDATE banco_filter 
            SET status = ?, motivo = ?, palavra_encontrada = ?, termo_base = ? 
            WHERE link = ?
        ''', (status, motivo, palavra_encontrada, termo_base, link))
        
    conn.commit()
    conn.close()

def buscar_dados_para_csv(limite=500):
    if not os.path.exists(DB_PATH): return []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Traz todas as colunas essenciais para auditoria no Excel
        cursor.execute('''
            SELECT s.data_noticia, s.nome_fonte, s.titulo_noticia, f.status, f.motivo, f.termo_base, f.palavra_encontrada, s.link
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