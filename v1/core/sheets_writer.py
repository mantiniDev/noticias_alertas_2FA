# core/sheets_writer.py
"""
Envia os resultados brutos dos scrapers para o Google Sheets
via Apps Script webhook (sem service account, sem credenciais Google).

Configuração:
  1. Siga as instruções em apps_script.js para publicar o web app na planilha.
  2. Copie a URL gerada e salve como secret SHEETS_WEBHOOK_URL no GitHub Actions.
     (localmente: export SHEETS_WEBHOOK_URL="https://script.google.com/macros/s/...")

Comportamento: append — cada execução adiciona linhas ao final da aba,
preservando o histórico completo de execuções anteriores.
"""

import logging
import os
from datetime import datetime

import requests

WEBHOOK_URL_ENV = "SHEETS_WEBHOOK_URL"
BATCH_SIZE = 200   # linhas por requisição (limite seguro do Apps Script)

COLUNAS = [
    "Titulo",
    "Link",
    "Data Publicacao",
    "Fonte",
    "Resumo",
    "Termo Buscado",
    "Origem",
    "Data Captura",
]

log = logging.getLogger(__name__)


def enviar_para_sheets(noticias: list[dict]) -> int:
    """
    Envia todas as notícias para a planilha via webhook.
    Retorna o número total de linhas inseridas.
    """
    if not noticias:
        log.info("Nenhuma notícia bruta para enviar ao Sheets.")
        return 0

    url = os.environ.get(WEBHOOK_URL_ENV)
    if not url:
        raise EnvironmentError(
            f"Variável de ambiente '{WEBHOOK_URL_ENV}' não configurada. "
            "Cole a URL do Apps Script web app nessa variável."
        )

    data_captura = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Monta as linhas no formato esperado pelo Apps Script
    linhas = []
    for n in noticias:
        data_obj = n.get("data_obj")
        data_pub = (
            data_obj.strftime("%Y-%m-%d %H:%M")
            if isinstance(data_obj, datetime)
            else str(data_obj or "")
        )
        fonte  = n.get("fonte", "")
        origem = n.get("origem", "Direto" if "Scraper Direto" in fonte else "RSS")

        linhas.append([
            n.get("titulo", ""),
            n.get("link", ""),
            data_pub,
            fonte,
            n.get("resumo", ""),
            n.get("termo_buscado", ""),
            origem,
            data_captura,
        ])

    # Envia em lotes para respeitar o timeout de 30s do Apps Script
    total_inserido = 0
    n_batches = -(-len(linhas) // BATCH_SIZE)   # teto da divisão

    for i in range(0, len(linhas), BATCH_SIZE):
        batch = linhas[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        log.info("[Sheets] Enviando batch %d/%d (%d linhas)...", batch_num, n_batches, len(batch))

        resp = requests.post(url, json={"rows": batch}, timeout=60)
        resp.raise_for_status()

        resultado = resp.json()
        if resultado.get("status") != "ok":
            raise RuntimeError(
                f"Apps Script retornou erro no batch {batch_num}: {resultado.get('message')}"
            )

        total_inserido += resultado.get("inserted", len(batch))

    log.info("[Sheets] Total inserido: %d linhas.", total_inserido)
    return total_inserido
