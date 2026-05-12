# main.py
"""
Orquestrador principal do MAST.

Fase 1 — Scraper RSS (Google News)   → buscar_noticias_semanais()
Fase 2 — Scraper Direto (tribunais)  → buscar_noticias_direto()

Os resultados são unificados, deduplicados por link e enviados
em um único e-mail com CSV de auditoria anexado.
"""

from datetime import datetime, timedelta

from core.scraper import buscar_noticias_semanais
from core.scraper_direto import buscar_noticias_direto
from core.notifier import gerar_corpos_email, enviar_email
from core.database import init_db, buscar_dados_para_csv
from core.csv_generator import gerar_csv_relatorio


if __name__ == "__main__":
    print("=" * 60)
    print("  MAST — Monitoramento Automatizado de Sistemas e Tribunais")
    print("=" * 60)

    # 0. Inicializa os bancos de dados (cria tabelas se não existirem)
    init_db()

    # ── Fase 1: Scraper RSS ────────────────────────────────────────────
    print("\n[Fase 1] Scraper RSS — Google News")
    noticias_rss = buscar_noticias_semanais()

    # ── Fase 2: Scraper Direto ─────────────────────────────────────────
    print("\n[Fase 2] Scraper Direto — Portais dos Tribunais")
    noticias_direto = buscar_noticias_direto()

    # ── Unificação e deduplicação por link ─────────────────────────────
    # O banco já deduplica por link, mas aqui garantimos que a mesma URL
    # não apareça duas vezes no e-mail caso os dois scrapers a capturem.
    links_vistos = set()
    noticias_unificadas = []

    for n in noticias_rss + noticias_direto:
        if n["link"] not in links_vistos:
            links_vistos.add(n["link"])
            noticias_unificadas.append(n)

    # Ordena por data decrescente
    noticias_unificadas.sort(key=lambda x: x["data_obj"], reverse=True)

    # ── Relatório CSV ──────────────────────────────────────────────────
    data_limite = datetime.now() - timedelta(days=2)
    dados_banco = buscar_dados_para_csv(limite=100, desde=data_limite)
    caminho_csv = gerar_csv_relatorio(dados_banco)

    # ── Log de resumo ──────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  Notícias RSS aprovadas    : {len(noticias_rss)}")
    print(f"  Notícias Direto aprovadas : {len(noticias_direto)}")
    print(f"  Total unificado           : {len(noticias_unificadas)}")
    print(f"{'─'*60}\n")

    # ── E-mail ─────────────────────────────────────────────────────────
    texto, html = gerar_corpos_email(noticias_unificadas)
    enviar_email(texto, html, len(noticias_unificadas), anexo_path=caminho_csv)