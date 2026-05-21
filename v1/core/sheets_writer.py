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

log = logging.getLogger(__name__)

WEBHOOK_URL_ENV = "SHEETS_WEBHOOK_URL"
BATCH_SIZE = 200   # linhas por requisição (limite seguro do Apps Script)


def _post_seguindo_redirect(url: str, data: dict, timeout: int = 60, max_hops: int = 8) -> requests.Response:
    """Google Apps Script redireciona POST para script.googleusercontent.com.

    O comportamento padrão de requests.post() é seguir o redirect, mas ele
    muda automaticamente o método de POST para GET (conforme RFC 7231 §6.4.3),
    fazendo com que doGet() seja invocado ao invés de doPost() — o corpo
    da resposta vem vazio ou é HTML de erro.

    Esta função itera por toda a cadeia de redirecionamentos re-enviando
    sempre como POST, preservando o body JSON em cada salto.
    """
    for hop in range(max_hops):
        log.debug("[Sheets] POST hop %d → %s", hop + 1, url)
        resp = requests.post(url, json=data, allow_redirects=False, timeout=30)
        log.debug("[Sheets] Resposta hop %d: status=%d", hop + 1, resp.status_code)

        if resp.status_code in (301, 302, 303, 307, 308):
            next_url = resp.headers.get("Location")
            if not next_url:
                log.warning("[Sheets] Redirect %d sem Location header — usando URL original.", resp.status_code)
                break
            log.debug("[Sheets] Redirect %d → %s", resp.status_code, next_url)
            url = next_url
        else:
            # Status final (200, 4xx, 5xx) — retorna a resposta
            return resp

    raise RuntimeError(
        f"Muitos redirecionamentos ao chamar o Apps Script (>{max_hops} hops). "
        "Verifique se a URL do SHEETS_WEBHOOK_URL está correta."
    )


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

        resp = _post_seguindo_redirect(url, {"rows": batch})
        resp.raise_for_status()

        body = resp.text.strip()
        log.debug("[Sheets] Resposta Apps Script (primeiros 300 chars): %r", body[:300])

        if not body:
            raise RuntimeError(
                f"Apps Script retornou resposta vazia no batch {batch_num}. "
                "Verifique se o web app está publicado com acesso anônimo."
            )

        try:
            resultado = resp.json()
        except Exception as exc:
            raise RuntimeError(
                f"Apps Script retornou resposta inválida (não-JSON) no batch {batch_num}. "
                f"Status HTTP: {resp.status_code}. "
                f"Corpo recebido (primeiros 400 chars): {body[:400]!r}"
            ) from exc

        if resultado.get("status") != "ok":
            raise RuntimeError(
                f"Apps Script retornou erro no batch {batch_num}: {resultado.get('message')}"
            )

        total_inserido += resultado.get("inserted", len(batch))

    log.info("[Sheets] Total inserido: %d linhas.", total_inserido)
    return total_inserido
