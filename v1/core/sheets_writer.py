# core/sheets_writer.py
"""
Envia os resultados brutos dos scrapers para o Google Sheets
via Apps Script webhook (sem service account, sem credenciais Google).

Configuração:
  1. Abra o editor do Apps Script na planilha e cole o conteúdo de apps_script.js.
  2. Crie um novo deployment:
       Implantações > Gerenciar implantações > Nova implantação
       Tipo: App da Web | Executar como: Eu | Quem tem acesso: Qualquer pessoa
  3. Copie a URL gerada e salve como secret SHEETS_WEBHOOK_URL no GitHub Actions.
     (localmente: export SHEETS_WEBHOOK_URL="https://script.google.com/macros/s/...")

Comportamento: append — cada execução adiciona linhas ao final da aba,
preservando o histórico completo de execuções anteriores.
"""

import logging
import os
from datetime import datetime

import requests

log = logging.getLogger(__name__)

WEBHOOK_URL_ENV    = "SHEETS_WEBHOOK_URL"
WEBHOOK_SECRET_ENV = "SHEETS_WEBHOOK_SECRET"
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
    "Conteudo Artigo",
]


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

    secret = os.environ.get(WEBHOOK_SECRET_ENV)

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
            n.get("titulo", "") or "",
            n.get("link", "") or "",
            data_pub,
            fonte or "",
            n.get("resumo", "") or "",
            n.get("termo_buscado", "") or "",
            origem or "",
            data_captura,
            n.get("conteudo_artigo", "") or "",
        ])

    # Envia em lotes para respeitar o timeout de 30s do Apps Script
    total_inserido = 0
    n_batches = -(-len(linhas) // BATCH_SIZE)   # teto da divisão

    for i in range(0, len(linhas), BATCH_SIZE):
        batch = linhas[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        log.info("[Sheets] Enviando batch %d/%d (%d linhas)...", batch_num, n_batches, len(batch))

        # requests.post() segue o redirect 302 do Apps Script automaticamente,
        # convertendo POST→GET para buscar a resposta pre-computada no endpoint /echo.
        # Isso é o comportamento correto — não altere allow_redirects.
        payload = {"rows": batch}
        if secret:
            payload["secret"] = secret
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()

        body = resp.text.strip()
        log.debug("[Sheets] Corpo da resposta (primeiros 300 chars): %r", body[:300])

        if not body:
            raise RuntimeError(
                f"Apps Script retornou resposta vazia no batch {batch_num}. "
                "Verifique se o web app está publicado com acesso anônimo (apps_script.js)."
            )

        try:
            resultado = resp.json()
        except Exception as exc:
            raise RuntimeError(
                f"Apps Script retornou resposta não-JSON no batch {batch_num}. "
                f"Status HTTP: {resp.status_code}. "
                f"Corpo (primeiros 500 chars): {body[:500]!r}"
            ) from exc

        if resultado.get("status") != "ok":
            raise RuntimeError(
                f"Apps Script reportou erro no batch {batch_num}: "
                f"{resultado.get('message', resultado)}"
            )

        total_inserido += resultado.get("inserted", len(batch))
        log.info("[Sheets] Batch %d/%d: %d linhas inseridas.", batch_num, n_batches, resultado.get("inserted", len(batch)))

    log.info("[Sheets] Total inserido: %d linhas.", total_inserido)
    return total_inserido
