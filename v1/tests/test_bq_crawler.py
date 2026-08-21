"""
Testes para core/bq_crawler.py.

Usa unittest.mock para substituir o cliente BigQuery — sem chamadas reais ao GCP.
"""

import json
import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Stub mínimo de google.cloud.bigquery para que o módulo importe sem a lib real
import sys
import types

_bq_stub = types.ModuleType("google.cloud.bigquery")


class _ScalarParam:
    def __init__(self, name, type_, value):
        self.name = name
        self.type_ = type_
        self.value = value


class _ArrayParam:
    def __init__(self, name, type_, values):
        self.name = name
        self.type_ = type_
        self.values = values


class _QueryJobConfig:
    def __init__(self, query_parameters=None):
        self.query_parameters = query_parameters or []


class _Client:
    def __init__(self, *a, **kw):
        pass

    def query(self, sql, job_config=None):
        raise NotImplementedError("deve ser mockado nos testes")


_bq_stub.Client = _Client
_bq_stub.QueryJobConfig = _QueryJobConfig
_bq_stub.ScalarQueryParameter = _ScalarParam
_bq_stub.ArrayQueryParameter = _ArrayParam
_bq_stub.query = types.ModuleType("google.cloud.bigquery.query")

_google = types.ModuleType("google")
_google_cloud = types.ModuleType("google.cloud")
_google_oauth2 = types.ModuleType("google.oauth2")
_sa_mod = types.ModuleType("google.oauth2.service_account")


class _Credentials:
    @staticmethod
    def from_service_account_info(info, scopes=None):
        return _Credentials()


_sa_mod.Credentials = _Credentials

sys.modules.setdefault("google", _google)
sys.modules.setdefault("google.cloud", _google_cloud)
sys.modules.setdefault("google.cloud.bigquery", _bq_stub)
sys.modules.setdefault("google.oauth2", _google_oauth2)
sys.modules.setdefault("google.oauth2.service_account", _sa_mod)

# Agora o módulo pode ser importado
from core import bq_crawler  # noqa: E402


SA_JSON = json.dumps(
    {
        "type": "service_account",
        "project_id": "jusbrasil-155317",
        "private_key_id": "key-id",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA0Z3...\n-----END RSA PRIVATE KEY-----\n",
        "client_email": "mast-bq-reader@jusbrasil-155317.iam.gserviceaccount.com",
        "client_id": "123",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
)

D_INICIO = date(2026, 8, 1)
D_FIM = date(2026, 8, 21)

_CLIPPING_ROW = {
    "tribunal_fonte": "TJSP",
    "data_publicacao": "2026-08-10",
    "titulo": "Resolução 2FA obrigatório no PJe",
    "descricao": "A partir de setembro todos os advogados deverão usar segundo fator.",
    "url": "https://www.tjsp.jus.br/diario/123",
    "origem": "Clipping",
}

_NOTICIAS_ROW = {
    "tribunal_fonte": "TRT3",
    "data_publicacao": "2026-08-15",
    "titulo": "Migração para eProc no TRT3",
    "descricao": None,
    "url": "https://www.trt3.jus.br/noticias/456",
    "origem": "Noticias",
}


def _make_client(clipping_rows=None, noticias_rows=None):
    """Cria um mock de bigquery.Client que retorna linhas predefinidas."""
    client = MagicMock(spec=_Client)
    call_count = {"n": 0}

    def _query(sql, job_config=None):
        job = MagicMock()
        if "Clipping" in sql or _bq_crawler_table_clipping() in sql:
            job.result.return_value = clipping_rows or []
        else:
            job.result.return_value = noticias_rows or []
        call_count["n"] += 1
        return job

    client.query.side_effect = _query
    return client, call_count


def _bq_crawler_table_clipping():
    return bq_crawler._TABLE_CLIPPING


class TestBuildClient:
    def test_raises_without_env(self, monkeypatch):
        monkeypatch.delenv("GCP_SERVICE_ACCOUNT_JSON", raising=False)
        with pytest.raises(EnvironmentError, match="GCP_SERVICE_ACCOUNT_JSON"):
            bq_crawler._build_client()

    def test_builds_with_env(self, monkeypatch):
        monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", SA_JSON)
        client = bq_crawler._build_client()
        assert client is not None


class TestFetchItems:
    def test_returns_combined_results(self, monkeypatch):
        monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", SA_JSON)
        client, _ = _make_client(
            clipping_rows=[_CLIPPING_ROW],
            noticias_rows=[_NOTICIAS_ROW],
        )
        monkeypatch.setattr(bq_crawler, "_build_client", lambda: client)

        items = bq_crawler.fetch_items(D_INICIO, D_FIM)

        assert len(items) == 2
        origens = {i["origem"] for i in items}
        assert origens == {"Clipping", "Noticias"}

    def test_empty_when_no_rows(self, monkeypatch):
        monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", SA_JSON)
        client, _ = _make_client(clipping_rows=[], noticias_rows=[])
        monkeypatch.setattr(bq_crawler, "_build_client", lambda: client)

        items = bq_crawler.fetch_items(D_INICIO, D_FIM)

        assert items == []

    def test_clipping_fields(self, monkeypatch):
        monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", SA_JSON)
        client, _ = _make_client(clipping_rows=[_CLIPPING_ROW], noticias_rows=[])
        monkeypatch.setattr(bq_crawler, "_build_client", lambda: client)

        items = bq_crawler.fetch_items(D_INICIO, D_FIM)

        assert items[0]["origem"] == "Clipping"
        assert items[0]["tribunal_fonte"] == "TJSP"
        assert items[0]["titulo"] == "Resolução 2FA obrigatório no PJe"

    def test_noticias_fields(self, monkeypatch):
        monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", SA_JSON)
        client, _ = _make_client(clipping_rows=[], noticias_rows=[_NOTICIAS_ROW])
        monkeypatch.setattr(bq_crawler, "_build_client", lambda: client)

        items = bq_crawler.fetch_items(D_INICIO, D_FIM)

        assert items[0]["origem"] == "Noticias"
        assert items[0]["tribunal_fonte"] == "TRT3"

    def test_calls_both_tables(self, monkeypatch):
        monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", SA_JSON)
        client, call_count = _make_client()
        monkeypatch.setattr(bq_crawler, "_build_client", lambda: client)

        bq_crawler.fetch_items(D_INICIO, D_FIM)

        assert call_count["n"] == 2, "deve consultar exatamente 2 tabelas (Clipping + Noticias)"
