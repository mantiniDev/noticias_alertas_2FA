# tests/test_database.py
"""
Testes unitários para core/database.py.

Usa banco SQLite temporário (tmp_path do pytest) para isolar cada teste.
"""
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


@pytest.fixture
def db_path(tmp_path):
    """Cria um banco temporário e inicializa as tabelas."""
    caminho = str(tmp_path / "test_mast.db")
    with patch("core.database.DB_PATH", caminho):
        from core.database import init_db
        init_db()
    return caminho


def test_init_db_cria_tabelas(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tabelas = {row[0] for row in cursor.fetchall()}
    conn.close()
    assert "banco_scraper" in tabelas
    assert "banco_filter" in tabelas


def test_init_db_cria_coluna_titulo_chave(db_path):
    """banco_filter deve ter a coluna titulo_chave após init_db."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(banco_filter)")
    colunas = {row[1] for row in cursor.fetchall()}
    conn.close()
    assert "titulo_chave" in colunas


def test_noticia_nova_nao_existe(db_path):
    with patch("core.database.DB_PATH", db_path):
        from core.database import verificar_status_noticia
        assert verificar_status_noticia("https://exemplo.com/noticia-nova") is False


def test_salvar_e_verificar_noticia(db_path):
    with patch("core.database.DB_PATH", db_path):
        from core.database import salvar_auditoria, verificar_status_noticia

        noticia = {
            "link": "https://exemplo.com/pje-instavel",
            "titulo": "PJe instável nesta manhã",
            "resumo": "Sistema apresentou lentidão",
            "data_obj": datetime.now(),
            "fonte": "TJSP",
        }

        assert verificar_status_noticia(noticia["link"]) is False
        salvar_auditoria(noticia, "novo", "Aprovado (Título)", "pje", "pje (Forte)")
        assert verificar_status_noticia(noticia["link"]) is True


def test_salvar_auditoria_duplicada_atualiza(db_path):
    """Segundo salvar_auditoria com mesmo link deve fazer UPDATE, não falhar."""
    with patch("core.database.DB_PATH", db_path):
        from core.database import salvar_auditoria, verificar_status_noticia

        noticia = {
            "link": "https://exemplo.com/noticia-dup",
            "titulo": "Notícia duplicada",
            "resumo": "",
            "data_obj": datetime.now(),
            "fonte": "TJRJ",
        }

        salvar_auditoria(noticia, "novo", "Aprovado (Título)", "pje", "pje (Forte)")
        # Segundo save com status diferente — não deve lançar exceção
        salvar_auditoria(noticia, "repetido", "Já Existente", "N/A", "N/A")
        assert verificar_status_noticia(noticia["link"]) is True


def test_buscar_dados_para_csv_retorna_lista(db_path):
    with patch("core.database.DB_PATH", db_path):
        from core.database import salvar_auditoria, buscar_dados_para_csv

        noticia = {
            "link": "https://exemplo.com/csv-test",
            "titulo": "PJe fora do ar",
            "resumo": "Sistema indisponível",
            "data_obj": datetime.now(),
            "fonte": "TRF1",
        }
        salvar_auditoria(noticia, "novo", "Aprovado (Título)", "pje", "pje (Forte)")

        dados = buscar_dados_para_csv(limite=10)
        assert isinstance(dados, list)
        assert len(dados) >= 1
        assert len(dados[0]) == 8  # 8 colunas conforme o SELECT


def test_buscar_dados_banco_inexistente(tmp_path):
    """Banco que não existe deve retornar lista vazia sem erros."""
    caminho_inexistente = str(tmp_path / "nao_existe.db")
    with patch("core.database.DB_PATH", caminho_inexistente):
        from core.database import buscar_dados_para_csv
        dados = buscar_dados_para_csv()
        assert dados == []


# ─────────────────────────────────────────────
# verificar_titulo_chave — dedup cross-run
# ─────────────────────────────────────────────

def test_titulo_chave_nao_encontrado_em_banco_vazio(db_path):
    with patch("core.database.DB_PATH", db_path):
        from core.database import verificar_titulo_chave
        assert verificar_titulo_chave("tjto eproc sabado manutencao sistema") is False


def test_titulo_chave_detecta_aprovado_recente(db_path):
    """Título aprovado recentemente deve ser bloqueado por verificar_titulo_chave."""
    with patch("core.database.DB_PATH", db_path):
        from core.database import salvar_auditoria, verificar_titulo_chave

        noticia = {
            "link": "https://news.google.com/rss/articles/abc123",
            "titulo": "TJTO comunica indisponibilidade do eproc para atualizacao",
            "resumo": "",
            "data_obj": datetime.now(),
            "fonte": "Tribunal de Justiça do Tocantins",
        }
        chave = "tjto comunica indisponibilidade do eproc para atualizacao"
        salvar_auditoria(noticia, "novo", "Aprovado (Título)", "eproc", "eproc (Forte)", chave)

        # Mesma chave, URL diferente (como faria o Scraper Direto) → deve bloquear
        assert verificar_titulo_chave(chave, janela_dias=3) is True


def test_titulo_chave_nao_bloqueia_status_bloqueado(db_path):
    """Título salvo como 'bloqueado' não deve impedir nova avaliação."""
    with patch("core.database.DB_PATH", db_path):
        from core.database import salvar_auditoria, verificar_titulo_chave

        noticia = {
            "link": "https://exemplo.com/link-bloqueado",
            "titulo": "Instabilidade no PJe afeta advogados",
            "resumo": "processo seletivo para estagiarios",
            "data_obj": datetime.now(),
            "fonte": "TJSP",
        }
        chave = "instabilidade no pje afeta advogados"
        salvar_auditoria(noticia, "bloqueado", "Blacklist (Resumo)", "estagio", "estágio", chave)

        # Status 'bloqueado' não conta como dedup
        assert verificar_titulo_chave(chave, janela_dias=3) is False


def test_titulo_chave_nao_bloqueia_fora_da_janela(db_path):
    """Título aprovado fora da janela de dias não deve bloquear nova entrada."""
    with patch("core.database.DB_PATH", db_path):
        from core.database import salvar_auditoria, verificar_titulo_chave
        import sqlite3 as _sql

        noticia = {
            "link": "https://exemplo.com/noticia-antiga",
            "titulo": "Manutencao programada do eproc na madrugada",
            "resumo": "",
            "data_obj": datetime.now() - timedelta(days=10),  # 10 dias atrás
            "fonte": "TJSC",
        }
        chave = "manutencao programada do eproc na madrugada"
        salvar_auditoria(noticia, "novo", "Aprovado (Título)", "eproc", "eproc (Forte)", chave)

        # Com janela de 3 dias, notícia de 10 dias atrás não deve bloquear
        assert verificar_titulo_chave(chave, janela_dias=3) is False


def test_titulo_chave_vazio_nao_bloqueia(db_path):
    """Chave vazia nunca deve bloquear (evita falso positivo em títulos curtos)."""
    with patch("core.database.DB_PATH", db_path):
        from core.database import verificar_titulo_chave
        assert verificar_titulo_chave("", janela_dias=3) is False
