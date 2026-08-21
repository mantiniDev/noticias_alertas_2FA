"""
core/bq_crawler.py
Consulta as tabelas BigQuery de Clipping e Notícias para o pipeline MAST.

Auth via variável de ambiente GCP_SERVICE_ACCOUNT_JSON (conteúdo JSON da SA key).
Entry point público: fetch_items(data_inicio, data_fim) -> list[dict]

Campos retornados por item:
    origem          "Clipping" | "Noticias"
    tribunal_fonte  sigla do tribunal (ex: "TJSP")
    data_publicacao date em ISO-8601
    titulo          str
    descricao       str | None
    url             str | None
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any

from google.cloud import bigquery
from google.oauth2 import service_account

from config.keywords import (
    CADERNOS_EXCLUIR,
    LIMITE_LINHAS,
    MAX_POR_SIGLA,
    SIGLAS_MONITORADAS,
    TIER_A_TERMS,
)

log = logging.getLogger(__name__)

_PROJECT = "jusbrasil-155317"
_TABLE_CLIPPING = f"{_PROJECT}.data_production_network.jusbrasil_bloco_diario"
_TABLE_NOTICIAS = f"{_PROJECT}.data_production_network.jusbrasil_noticia"

# Combina os padrões TIER_A em uma única regex RE2 para uso no BQ
_REGEX_TIER_A = "|".join(TIER_A_TERMS)

# Mapeamento de colunas — ajustar aqui se o schema das tabelas mudar
_COLS_CLIPPING = {
    "sigla": "sigla",
    "data": "data_publicacao",
    "caderno": "caderno",
    "titulo": "titulo",
    "descricao": "conteudo",
    "url": "url",
}
_COLS_NOTICIAS = {
    "sigla": "sigla",
    "data": "data_publicacao",
    "titulo": "titulo",
    "descricao": "descricao",
    "url": "url",
}

_SQL_CLIPPING = """
SELECT
    {sigla}           AS tribunal_fonte,
    CAST({data} AS STRING)  AS data_publicacao,
    {titulo}          AS titulo,
    {descricao}       AS descricao,
    {url}             AS url,
    'Clipping'        AS origem
FROM `{table}`
WHERE DATE({data}) BETWEEN @data_inicio AND @data_fim
  AND {sigla} IN UNNEST(@siglas)
  AND COALESCE({caderno}, '') NOT IN UNNEST(@cadernos_excluir)
  AND (
      REGEXP_CONTAINS(LOWER(COALESCE({titulo}, '')),   @regex_tier_a)
   OR REGEXP_CONTAINS(LOWER(COALESCE({descricao}, '')), @regex_tier_a)
  )
QUALIFY ROW_NUMBER() OVER (PARTITION BY {sigla} ORDER BY {data} DESC) <= @max_por_sigla
LIMIT @limite_linhas
""".strip()

_SQL_NOTICIAS = """
SELECT
    {sigla}           AS tribunal_fonte,
    CAST({data} AS STRING)  AS data_publicacao,
    {titulo}          AS titulo,
    {descricao}       AS descricao,
    {url}             AS url,
    'Noticias'        AS origem
FROM `{table}`
WHERE DATE({data}) BETWEEN @data_inicio AND @data_fim
  AND {sigla} IN UNNEST(@siglas)
  AND (
      REGEXP_CONTAINS(LOWER(COALESCE({titulo}, '')),   @regex_tier_a)
   OR REGEXP_CONTAINS(LOWER(COALESCE({descricao}, '')), @regex_tier_a)
  )
QUALIFY ROW_NUMBER() OVER (PARTITION BY {sigla} ORDER BY {data} DESC) <= @max_por_sigla
LIMIT @limite_linhas
""".strip()


def _build_client() -> bigquery.Client:
    raw = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise EnvironmentError(
            "Variável de ambiente GCP_SERVICE_ACCOUNT_JSON não definida. "
            "Configure o GitHub Secret correspondente antes de executar."
        )
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/bigquery.readonly"],
    )
    return bigquery.Client(project=_PROJECT, credentials=creds)


def _run_query(
    client: bigquery.Client,
    sql: str,
    params: list[bigquery.query.ScalarQueryParameter | bigquery.query.ArrayQueryParameter],
) -> list[dict[str, Any]]:
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    rows = client.query(sql, job_config=job_config).result()
    return [dict(row) for row in rows]


def _query_clipping(
    client: bigquery.Client,
    data_inicio: date,
    data_fim: date,
) -> list[dict[str, Any]]:
    c = _COLS_CLIPPING
    sql = _SQL_CLIPPING.format(
        table=_TABLE_CLIPPING,
        sigla=c["sigla"],
        data=c["data"],
        caderno=c["caderno"],
        titulo=c["titulo"],
        descricao=c["descricao"],
        url=c["url"],
    )
    params = [
        bigquery.ScalarQueryParameter("data_inicio", "DATE", data_inicio.isoformat()),
        bigquery.ScalarQueryParameter("data_fim", "DATE", data_fim.isoformat()),
        bigquery.ArrayQueryParameter("siglas", "STRING", SIGLAS_MONITORADAS),
        bigquery.ArrayQueryParameter("cadernos_excluir", "STRING", CADERNOS_EXCLUIR),
        bigquery.ScalarQueryParameter("regex_tier_a", "STRING", _REGEX_TIER_A),
        bigquery.ScalarQueryParameter("max_por_sigla", "INT64", MAX_POR_SIGLA),
        bigquery.ScalarQueryParameter("limite_linhas", "INT64", LIMITE_LINHAS),
    ]
    result = _run_query(client, sql, params)
    log.info("Clipping: %d registros recuperados (%s→%s)", len(result), data_inicio, data_fim)
    return result


def _query_noticias(
    client: bigquery.Client,
    data_inicio: date,
    data_fim: date,
) -> list[dict[str, Any]]:
    c = _COLS_NOTICIAS
    sql = _SQL_NOTICIAS.format(
        table=_TABLE_NOTICIAS,
        sigla=c["sigla"],
        data=c["data"],
        titulo=c["titulo"],
        descricao=c["descricao"],
        url=c["url"],
    )
    params = [
        bigquery.ScalarQueryParameter("data_inicio", "DATE", data_inicio.isoformat()),
        bigquery.ScalarQueryParameter("data_fim", "DATE", data_fim.isoformat()),
        bigquery.ArrayQueryParameter("siglas", "STRING", SIGLAS_MONITORADAS),
        bigquery.ScalarQueryParameter("regex_tier_a", "STRING", _REGEX_TIER_A),
        bigquery.ScalarQueryParameter("max_por_sigla", "INT64", MAX_POR_SIGLA),
        bigquery.ScalarQueryParameter("limite_linhas", "INT64", LIMITE_LINHAS),
    ]
    result = _run_query(client, sql, params)
    log.info("Noticias: %d registros recuperados (%s→%s)", len(result), data_inicio, data_fim)
    return result


def fetch_items(data_inicio: date, data_fim: date) -> list[dict[str, Any]]:
    """Retorna itens combinados de Clipping e Notícias para o período informado."""
    client = _build_client()
    clipping = _query_clipping(client, data_inicio, data_fim)
    noticias = _query_noticias(client, data_inicio, data_fim)
    items = clipping + noticias
    log.info("fetch_items: %d itens no total (%d Clipping + %d Noticias)", len(items), len(clipping), len(noticias))
    return items
