# tests/test_database.py
"""
Testes unitários para core/database.py.

Usa banco SQLite temporário (tmp_path do pytest) para isolar cada teste.
"""
import sqlite3
from datetime import datetime
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
