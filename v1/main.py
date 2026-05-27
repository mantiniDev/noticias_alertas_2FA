# main.py
"""
Orquestrador principal do MAST.

Fase 1 — Scraper RSS (Google News)       → buscar_noticias_semanais()
Fase 2 — Scraper Direto (tribunais)      → buscar_noticias_direto()
Fase 3 — Notícias Expandidas (106 fontes) → buscar_noticias_fontes()

Fases 1+2 são unificadas, deduplicadas e compõem a seção de alertas
do e-mail. A Fase 3 é exibida em seção separada, agrupada por categoria
(Sistemas/CNJ, Tribunais Superiores, TJEs, TRFs, TRTs).
CSV e PDF de auditoria são anexados ao e-mail (Fases 1+2 apenas).
Google Sheets recebe todos os itens brutos das Fases 1+2.
"""

import logging
import logging.handlers
import os
from datetime import datetime, timedelta

from core.scraper import buscar_noticias_semanais
from core.scraper_direto import buscar_noticias_direto, buscar_noticias_fontes, FONTES_NOTICIAS
from core.notifier import gerar_corpos_email, enviar_email
from core.sheets_writer import enviar_para_sheets
from core.database import init_db, buscar_dados_para_csv
from core.csv_generator import gerar_csv_relatorio
from core.pdf_generator import gerar_pdf_relatorio
from config.settings import DIAS_JANELA, CSV_LIMITE_REGISTROS
from core.filter import normalizar_titulo_chave


def _configurar_logging() -> None:
    """
    Configura dois handlers:
      - Console  : nível INFO  — mensagens visíveis no terminal / GitHub Actions
      - Arquivo  : nível DEBUG — log completo em logs/mast.log (rotativo 5 MB, 3 backups)
    """
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, 'mast.log')

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console: apenas INFO+ (mantém saída limpa no terminal)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(message)s'))

    # Arquivo: DEBUG+ com timestamp e módulo (para diagnóstico)
    arquivo = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,   # 5 MB por arquivo
        backupCount=3,               # mantém mast.log + 3 rotações
        encoding='utf-8',
    )
    arquivo.setLevel(logging.DEBUG)
    arquivo.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))

    root.addHandler(console)
    root.addHandler(arquivo)


if __name__ == "__main__":
    _configurar_logging()
    log = logging.getLogger(__name__)

    log.info("=" * 60)
    log.info("  MAST — Monitoramento Automatizado de Sistemas e Tribunais")
    log.info("=" * 60)

    # 0. Inicializa os bancos de dados (cria tabelas se não existirem)
    init_db()

    # Lista que acumula todos os itens brutos (antes do filtro) para o Sheets
    noticias_brutas: list[dict] = []

    # ── Fase 1: Scraper RSS ────────────────────────────────────────────
    log.info("\n[Fase 1] Scraper RSS — Google News")
    noticias_rss = buscar_noticias_semanais(brutas=noticias_brutas)

    # ── Fase 2: Scraper Direto ─────────────────────────────────────────
    log.info("\n[Fase 2] Scraper Direto — Portais dos Tribunais")
    noticias_direto = buscar_noticias_direto(brutas=noticias_brutas)

    # ── Fase 3: Notícias Expandidas ────────────────────────────────────
    log.info("\n[Fase 3] Notícias Expandidas — %d fontes por categoria", len(FONTES_NOTICIAS))
    noticias_fontes = buscar_noticias_fontes()   # dict[grupo, list]

    # ── Unificação e deduplicação por link E por conteúdo ─────────────
    # Dedup por link: evita o mesmo URL duas vezes.
    # Dedup por título: evita a mesma notícia com URLs diferentes
    #   (scraper direto usa URL do tribunal; RSS usa URL do Google News).
    links_vistos: set[str] = set()
    titulos_vistos: set[str] = set()
    noticias_unificadas: list[dict] = []

    for n in noticias_rss + noticias_direto:
        chave = normalizar_titulo_chave(n["titulo"])
        if n["link"] in links_vistos:
            continue
        if chave and chave in titulos_vistos:
            log.debug("Dedup por título: '%s'", n["titulo"][:80])
            continue
        links_vistos.add(n["link"])
        if chave:
            titulos_vistos.add(chave)
        noticias_unificadas.append(n)

    noticias_unificadas.sort(key=lambda x: x["data_obj"], reverse=True)

    # ── Relatórios CSV e PDF ───────────────────────────────────────────
    data_limite = datetime.now() - timedelta(days=DIAS_JANELA)
    dados_banco = buscar_dados_para_csv(limite=CSV_LIMITE_REGISTROS, desde=data_limite)
    caminho_csv = gerar_csv_relatorio(dados_banco)
    caminho_pdf = gerar_pdf_relatorio(dados_banco)

    # ── Log de resumo ──────────────────────────────────────────────────
    total_fontes = sum(len(v) for v in noticias_fontes.values())
    log.info("\n%s", "─" * 60)
    log.info("  Notícias RSS aprovadas      : %d", len(noticias_rss))
    log.info("  Notícias Direto aprovadas   : %d", len(noticias_direto))
    log.info("  Total alertas (Fases 1+2)   : %d", len(noticias_unificadas))
    log.info("  Notícias Fontes (Fase 3)    : %d", total_fontes)
    log.info("  TOTAL GERAL                 : %d", len(noticias_unificadas) + total_fontes)
    log.info("%s\n", "─" * 60)

    # ── E-mail com CSV + PDF anexados ──────────────────────────────────
    texto, html = gerar_corpos_email(noticias_unificadas, noticias_fontes)
    enviar_email(
        texto, html,
        len(noticias_unificadas) + total_fontes,
        anexo_path=caminho_csv,
        pdf_path=caminho_pdf,
    )

    # ── Google Sheets — coleta bruta (sem filtro) ──────────────────────
    log.info("\n[Sheets] Enviando %d itens brutos para a planilha...", len(noticias_brutas))
    total_sheets = enviar_para_sheets(noticias_brutas)
    log.info("[Sheets] %d linhas inseridas.", total_sheets)
