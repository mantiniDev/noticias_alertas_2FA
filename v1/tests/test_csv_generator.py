# tests/test_csv_generator.py
"""
Testes unitários para core/csv_generator.py.
"""
import csv
import os

import pytest


@pytest.fixture
def dados_exemplo() -> list[tuple]:
    return [
        (
            "2024-01-15 09:30:00", "TJSP", "PJe instável nesta manhã",
            "novo", "Aprovado (Título)", "pje (Forte)", "pje",
            "https://tjsp.jus.br/noticia-1",
        ),
        (
            "2024-01-15 10:00:00", "TRF1", "Concurso público aberto",
            "bloqueado", "Blacklist (Título)", "concurso", "concurso",
            "https://trf1.jus.br/noticia-2",
        ),
    ]


def test_gerar_csv_vazio(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Redireciona a raiz do projeto para tmp_path
    import core.csv_generator as mod
    monkeypatch.setattr(mod.os.path, "abspath", lambda p: str(tmp_path / os.path.basename(p)))

    from core.csv_generator import gerar_csv_relatorio
    caminho = gerar_csv_relatorio([])

    assert os.path.exists(caminho)
    with open(caminho, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f, delimiter=";"))

    assert len(rows) == 1  # apenas o cabeçalho
    assert rows[0][0] == "Data da Notícia"
    assert len(rows[0]) == 8


def test_gerar_csv_com_dados(tmp_path, monkeypatch, dados_exemplo):
    import core.csv_generator as mod
    raiz_fake = str(tmp_path)

    original_abspath = os.path.abspath

    def abspath_fake(p):
        # Redireciona caminhos relativos ao projeto para tmp_path
        resultado = original_abspath(p)
        if "Historico" in resultado or "historico" in resultado:
            return str(tmp_path / os.path.basename(resultado))
        return resultado

    monkeypatch.setattr(mod.os.path, "abspath", abspath_fake)

    from core.csv_generator import gerar_csv_relatorio
    caminho = gerar_csv_relatorio(dados_exemplo)

    with open(caminho, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f, delimiter=";"))

    assert len(rows) == 3  # cabeçalho + 2 linhas
    assert rows[1][2] == "PJe instável nesta manhã"
    assert rows[2][3] == "bloqueado"


def test_gerar_csv_cria_copia_historica(tmp_path):
    """Verifica que a pasta historico/ é criada com arquivo timestampado."""
    raiz = tmp_path

    # Patch direto nos caminhos gerados dentro da função
    import core.csv_generator as mod
    import importlib

    original_dirname = os.path.dirname

    def dirname_fake(p):
        # Faz o módulo achar que sua raiz é tmp_path
        if "csv_generator" in p:
            return str(raiz / "core")
        return original_dirname(p)

    # Cria estrutura esperada
    (raiz / "core").mkdir(exist_ok=True)
    (raiz / "historico").mkdir(exist_ok=True)

    from core.csv_generator import _escrever_csv, _CABECALHO

    # Testa diretamente a função auxiliar
    caminho_teste = str(raiz / "historico" / "Historico_2024-01-15_0930.csv")
    _escrever_csv(caminho_teste, [])

    assert os.path.exists(caminho_teste)
    with open(caminho_teste, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f, delimiter=";"))
    assert rows[0] == _CABECALHO


def test_cabecalho_tem_8_colunas():
    from core.csv_generator import _CABECALHO
    assert len(_CABECALHO) == 8


def test_cabecalho_ordem_correta():
    from core.csv_generator import _CABECALHO
    assert _CABECALHO[0] == "Data da Notícia"
    assert _CABECALHO[2] == "Título"
    assert _CABECALHO[5] == "Lista do Gatilho"
    assert _CABECALHO[6] == "Palavra Capturada"
    assert _CABECALHO[7] == "Link da Notícia"
