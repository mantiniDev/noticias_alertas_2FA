# main.py
"""
Orquestrador principal do MAST.

Fase 1 — Scraper RSS (Google News)       → buscar_noticias_semanais()
Fase 2 — Scraper Direto (tribunais)      → buscar_noticias_direto()
Fase 3 — Notícias Expandidas (104 fontes) → buscar_noticias_fontes()

Todas as fases são unificadas em um único dict {grupo: [itens]} e exibidas
em relatório categorizado por: Sistemas/CNJ, Tribunais Superiores,
TJEs, TRFs, TRTs, TREs.
CSV e PDF de auditoria são anexados ao e-mail (Fases 1+2 apenas).
Google Sheets recebe todos os itens brutos das Fases 1+2.
"""

import logging
import logging.handlers
import os
from datetime import datetime, timedelta

from core.scraper import buscar_noticias_semanais
from core.scraper_direto import buscar_noticias_direto, buscar_noticias_fontes, FONTES_NOTICIAS, FONTES
from core.notifier import gerar_corpos_email, enviar_email, _GRUPOS_LABEL
from core.sheets_writer import enviar_para_sheets
from core.database import init_db, buscar_dados_para_csv
from core.csv_generator import gerar_csv_relatorio
from core.pdf_generator import gerar_pdf_relatorio
from config.settings import DIAS_JANELA, CSV_LIMITE_REGISTROS
from core.filter import normalizar_titulo_chave

# ── Mapeamento acrônimo → grupo (derivado da lista unificada de fontes) ────
# Usado por _inferir_grupo_rss() para categorizar notícias RSS por tribunal.
_ACRONYM_GRUPO: dict[str, str] = {f["acronym"]: f["grupo"] for f in FONTES}


def _inferir_grupo_rss(titulo: str, fonte: str) -> str:
    """
    Tenta inferir o grupo de uma notícia RSS pelo acrônimo do tribunal no título.
    Retorna "Sistemas-CNJ" como grupo padrão quando nenhum acrônimo é identificado.
    """
    titulo_upper = titulo.upper()
    for acronym, grupo in _ACRONYM_GRUPO.items():
        if acronym.upper() in titulo_upper:
            return grupo
    return "Sistemas-CNJ"


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
    noticias_fontes = buscar_noticias_fontes(brutas=noticias_brutas)   # dict[grupo, list]

    # ── Deduplicação Fases 1+2 por link E por conteúdo ────────────────
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

    # ── Unificação das 3 fases em relatório único por categoria ───────
    # Estrutura: {grupo: [itens]} — ordenado conforme _GRUPOS_LABEL
    noticias_por_grupo: dict[str, list] = {g: [] for g in _GRUPOS_LABEL}

    # Fases 1+2 (após dedup): inferir grupo via acrônimo no título
    for n in noticias_unificadas:
        grupo = n.get("grupo") or _inferir_grupo_rss(n["titulo"], n.get("fonte", ""))
        item = dict(n)
        item["grupo"] = grupo
        item.setdefault("tipo", "Notícia")
        dest = grupo if grupo in noticias_por_grupo else "Sistemas-CNJ"
        noticias_por_grupo[dest].append(item)

    # Fase 3 (notícias expandidas por categoria)
    for grupo, itens in noticias_fontes.items():
        if grupo in noticias_por_grupo:
            noticias_por_grupo[grupo].extend(itens)
        else:
            log.warning("Grupo desconhecido na Fase 3: '%s' (%d itens ignorados)", grupo, len(itens))

    # Ordenar cada categoria por data (mais recente primeiro)
    for itens in noticias_por_grupo.values():
        itens.sort(key=lambda x: x["data_obj"], reverse=True)

    # ── Log de resumo ──────────────────────────────────────────────────
    total_fontes = sum(len(v) for v in noticias_fontes.values())
    total_geral  = sum(len(v) for v in noticias_por_grupo.values())
    log.info("\n%s", "─" * 60)
    log.info("  Notícias RSS aprovadas      : %d", len(noticias_rss))
    log.info("  Notícias Direto aprovadas   : %d", len(noticias_direto))
    log.info("  Total alertas (Fases 1+2)   : %d", len(noticias_unificadas))
    log.info("  Notícias Fontes (Fase 3)    : %d", total_fontes)
    log.info("  TOTAL GERAL                 : %d", total_geral)
    for g, itens in noticias_por_grupo.items():
        if itens:
            log.info("    %-26s: %d", g, len(itens))
    log.info("%s\n", "─" * 60)

    # ── E-mail com CSV + PDF anexados ──────────────────────────────────
    texto, html = gerar_corpos_email(noticias_por_grupo)
    enviar_email(
        texto, html,
        total_geral,
        anexo_path=caminho_csv,
        pdf_path=caminho_pdf,
    )

    # ── Google Sheets — coleta bruta (sem filtro) ──────────────────────
    log.info("\n[Sheets] Enviando %d itens brutos para a planilha...", len(noticias_brutas))
    total_sheets = enviar_para_sheets(noticias_brutas)
    log.info("[Sheets] %d linhas inseridas.", total_sheets)
