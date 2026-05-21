# main_v2.py
"""
MAST v2 — Orquestrador principal.

Diferenças em relação ao v1:
  - Sem filtro, sem banco de dados, sem e-mail.
  - Toda a coleta (RSS + Direto) é enviada diretamente ao Google Sheets.
  - Deduplicação apenas por link dentro da execução.
  - Planilha: 1Ny0_IzTczY9pNxSGAnYS6OvLmBaeveWVajSVTa7E9qA / aba: script_git
"""

import logging
import logging.handlers
import os

from core.scraper_v2 import buscar_noticias_rss
from core.scraper_direto_v2 import buscar_noticias_direto
from core.sheets_writer import enviar_para_sheets


def _configurar_logging() -> None:
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))

    arquivo = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, "mast_v2.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    arquivo.setLevel(logging.DEBUG)
    arquivo.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root.addHandler(console)
    root.addHandler(arquivo)


if __name__ == "__main__":
    _configurar_logging()
    log = logging.getLogger(__name__)

    log.info("=" * 60)
    log.info("  MAST v2 — Coleta bruta para Google Sheets")
    log.info("=" * 60)

    # Fase 1: Scraper RSS
    log.info("\n[Fase 1] Scraper RSS — Google News")
    noticias_rss = buscar_noticias_rss()

    # Fase 2: Scraper Direto
    log.info("\n[Fase 2] Scraper Direto — Portais dos Tribunais")
    noticias_direto = buscar_noticias_direto()

    # Deduplicação por link dentro da execução
    links_vistos: set[str] = set()
    noticias_unificadas: list[dict] = []

    for n in noticias_rss + noticias_direto:
        link = n.get("link", "")
        if not link or link in links_vistos:
            continue
        links_vistos.add(link)
        noticias_unificadas.append(n)

    log.info("\n%s", "─" * 60)
    log.info("  RSS coletadas    : %d", len(noticias_rss))
    log.info("  Direto coletadas : %d", len(noticias_direto))
    log.info("  Total único      : %d", len(noticias_unificadas))
    log.info("%s\n", "─" * 60)

    # Envio ao Google Sheets
    log.info("[Sheets] Enviando para a planilha...")
    total_enviado = enviar_para_sheets(noticias_unificadas)
    log.info("[Sheets] %d linhas inseridas com sucesso.", total_enviado)
