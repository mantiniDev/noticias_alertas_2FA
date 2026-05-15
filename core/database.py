# core/database.py
import sqlite3
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'mast_dados.db')


def init_db() -> None:
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
            termo_base TEXT,
            titulo_chave TEXT DEFAULT ''
        )
    ''')

    # ── Migração: adiciona titulo_chave em bancos já existentes ──────────────
    # ALTER TABLE ignora o erro se a coluna já existir — idempotente.
    try:
        cursor.execute(
            "ALTER TABLE banco_filter ADD COLUMN titulo_chave TEXT DEFAULT ''"
        )
    except sqlite3.OperationalError:
        pass  # coluna já existe — banco novo ou migração já aplicada

    conn.commit()
    conn.close()


def verificar_titulo_chave(chave: str, janela_dias: int = 3) -> bool:
    """
    Retorna True se a mesma chave de título já foi aprovada (status='novo')
    dentro dos últimos `janela_dias` dias.

    Por que isso é necessário:
      O RSS e o Scraper Direto podem capturar a MESMA notícia com URLs
      diferentes (Google News URL vs URL direta do tribunal).  O check por
      link não bloqueia essa situação.  Ao persistir a chave normalizada do
      título, conseguimos detectar o mesmo conteúdo entre execuções distintas.

    Janela de tempo:
      Usamos DIAS_JANELA + 1 (padrão 3 dias) — cobre a sobreposição entre
      execuções sem bloquear eventos legítimos que recorrem semanalmente
      com títulos similares (ex: "Indisponibilidade de Manutenção - TJSP").
      Quando a janela expira, o evento pode voltar a ser aprovado se
      reaparecer — o check por link ainda bloqueia re-entradas exatas.
    """
    if not chave or not os.path.exists(DB_PATH):
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    desde = (datetime.now() - timedelta(days=janela_dias)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        SELECT 1 FROM banco_filter f
        INNER JOIN banco_scraper s ON f.link = s.link
        WHERE f.titulo_chave = ?
          AND f.status = 'novo'
          AND s.data_noticia >= ?
        LIMIT 1
        """,
        (chave, desde),
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None


def verificar_status_noticia(link: str) -> bool:
    if not os.path.exists(DB_PATH):
        return False
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM banco_filter WHERE link = ?", (link,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None


def salvar_auditoria(
    noticia_bruta: dict,
    status: str,
    motivo: str,
    palavra_encontrada: str,
    termo_base: str,
    titulo_chave: str = "",
) -> None:
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

    # 2. Grava a decisão do filtro (inclui titulo_chave para dedup cross-run)
    try:
        cursor.execute('''
            INSERT INTO banco_filter
            (link, status, motivo, palavra_encontrada, termo_base, titulo_chave)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (link, status, motivo, palavra_encontrada, termo_base, titulo_chave))
    except sqlite3.IntegrityError:
        cursor.execute('''
            UPDATE banco_filter
            SET status = ?, motivo = ?, palavra_encontrada = ?, termo_base = ?,
                titulo_chave = CASE WHEN titulo_chave = '' THEN ? ELSE titulo_chave END
            WHERE link = ?
        ''', (status, motivo, palavra_encontrada, termo_base, titulo_chave, link))

    conn.commit()
    conn.close()


def buscar_dados_para_csv(limite: int = 500, desde: datetime | None = None) -> list[tuple]:
    """
    Retorna os registros de auditoria para geração do CSV.

    Parâmetros:
        limite (int): número máximo de registros a retornar.
        desde (datetime | None): se informado, filtra apenas registros
            com data_noticia >= desde. Usado pelo main.py para restringir
            o CSV ao período da rodada atual (últimos 2 dias), evitando
            que o anexo misture dados históricos com o e-mail do dia.
    """
    if not os.path.exists(DB_PATH):
        return []

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        if desde is not None:
            # Converte para string no formato gravado pelo salvar_auditoria
            desde_str = desde.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
                SELECT
                    s.data_noticia,
                    s.nome_fonte,
                    s.titulo_noticia,
                    f.status,
                    f.motivo,
                    f.termo_base,
                    f.palavra_encontrada,
                    s.link
                FROM banco_scraper s
                INNER JOIN banco_filter f ON s.link = f.link
                WHERE s.data_noticia >= ?
                ORDER BY s.id DESC
                LIMIT ?
            ''', (desde_str, limite))
        else:
            cursor.execute('''
                SELECT
                    s.data_noticia,
                    s.nome_fonte,
                    s.titulo_noticia,
                    f.status,
                    f.motivo,
                    f.termo_base,
                    f.palavra_encontrada,
                    s.link
                FROM banco_scraper s
                INNER JOIN banco_filter f ON s.link = f.link
                ORDER BY s.id DESC
                LIMIT ?
            ''', (limite,))

        return cursor.fetchall()

    except sqlite3.OperationalError:
        return []
    finally:
        conn.close() 