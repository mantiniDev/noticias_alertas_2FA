#!/usr/bin/env python3
"""
diagnostico_fase3.py
────────────────────
Testa todas as fontes da Fase 3 (FONTES_NOTICIAS) e gera um relatório
de quais estão funcionando, quais retornam 0 itens e quais dão erro.

Uso:
    cd v1
    py -3 diagnostico_fase3.py

Saída:
    - Console com ✅ / ⚠️ / ❌ por fonte
    - diagnostico_fase3_AAAA-MM-DD.csv na pasta v1/

Interpretação dos resultados:
    ✅  OK       → parser funcionou, N itens encontrados
    ⚠️  ZERO     → HTML chegou mas parser não extraiu nada
                   • HTML pequeno (< 2 KB) → provável JS-only → precisa Playwright
                   • HTML grande (>= 2 KB) → parser não cobre a estrutura HTML
    ❌  ERRO     → timeout, HTTP 4xx/5xx, SSL, bloqueio, redirect de login
    ⏭️  PULADO   → vpn_required=True na fonte
"""

import csv
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Garante que o pacote v1 está no path ─────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from core.scraper_direto import (   # noqa: E402
    FONTES_NOTICIAS,
    PARSERS,
    fetch_page,
    parse_generic_news,
    _GRUPOS_LABEL,
)

# ── Logging mínimo: só WARNING para não poluir o output ──────────────
logging.basicConfig(level=logging.WARNING, format="%(message)s")

# ── Paleta ANSI ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

# ── Limiar para detectar páginas JS-only ─────────────────────────────
JS_THRESHOLD_BYTES = 2_000   # HTML < 2 KB após parse = provavelmente vazio/JS


def _html_size(soup) -> int:
    """Retorna o tamanho aproximado do HTML em bytes."""
    try:
        return len(str(soup).encode("utf-8"))
    except Exception:
        return 0


def _html_snippet(soup, chars: int = 300) -> str:
    """Extrai os primeiros N chars de texto visível da página."""
    try:
        return soup.get_text(" ", strip=True)[:chars].replace("\n", " ")
    except Exception:
        return ""


def diagnosticar() -> None:
    hoje = datetime.now().strftime("%Y-%m-%d")
    csv_path = ROOT / f"diagnostico_fase3_{hoje}.csv"

    stats = {"ok": 0, "zero": 0, "erro": 0, "pulado": 0}
    linhas_csv: list[dict] = []

    grupo_atual = None
    total = len(FONTES_NOTICIAS)

    print(f"\n{BOLD}MAST — Diagnóstico Fase 3 ({total} fontes){RESET}")
    print("=" * 65)

    for i, fonte in enumerate(FONTES_NOTICIAS, 1):
        acronym    = fonte["acronym"]
        nome       = fonte.get("nome", "")
        grupo      = fonte.get("grupo", "")
        url        = fonte["url"]
        base_url   = fonte.get("base_url", url)
        parser_key = fonte.get("parser", "generic_news")

        # Separador de grupo
        if grupo != grupo_atual:
            grupo_atual = grupo
            label = _GRUPOS_LABEL.get(grupo, grupo)
            print(f"\n{CYAN}{BOLD}── {label} ──{RESET}")

        prefix = f"  [{i:>3}/{total}] [{acronym}]"

        # Fontes que requerem VPN
        if fonte.get("vpn_required"):
            print(f"{prefix} ⏭️  PULADO (vpn_required)")
            stats["pulado"] += 1
            linhas_csv.append(_linha(fonte, "PULADO", 0, 0, "vpn_required", ""))
            continue

        # Fetch
        t0 = time.time()
        try:
            soup = fetch_page(fonte)
        except Exception as exc:
            elapsed = time.time() - t0
            msg = f"{type(exc).__name__}: {str(exc)[:120]}"
            print(f"{RED}{prefix} ❌  ERRO  ({elapsed:.1f}s) — {msg}{RESET}")
            stats["erro"] += 1
            linhas_csv.append(_linha(fonte, "ERRO", 0, 0, msg, ""))
            continue
        elapsed = time.time() - t0

        if not soup:
            msg = "fetch_page retornou None (sem conteúdo ou HTTP erro)"
            print(f"{RED}{prefix} ❌  ERRO  ({elapsed:.1f}s) — {msg}{RESET}")
            stats["erro"] += 1
            linhas_csv.append(_linha(fonte, "ERRO", 0, 0, msg, ""))
            continue

        # Parse
        html_bytes = _html_size(soup)
        parser_fn  = PARSERS.get(parser_key, parse_generic_news)
        try:
            itens = parser_fn(soup, acronym, base_url)
        except Exception as exc:
            msg = f"Parser {parser_key} falhou: {type(exc).__name__}: {str(exc)[:120]}"
            print(f"{RED}{prefix} ❌  ERRO  ({elapsed:.1f}s) — {msg}{RESET}")
            stats["erro"] += 1
            linhas_csv.append(_linha(fonte, "ERRO", 0, html_bytes, msg, ""))
            continue

        n = len(itens)

        if n > 0:
            print(f"{GREEN}{prefix} ✅  OK    ({elapsed:.1f}s) — {n} itens{RESET}")
            stats["ok"] += 1
            linhas_csv.append(_linha(fonte, "OK", n, html_bytes, "", ""))
        else:
            # Classifica causa do ZERO
            if html_bytes < JS_THRESHOLD_BYTES:
                causa = "HTML_PEQUENO (provável JS-only → precisa Playwright)"
            else:
                causa = f"ZERO_ITENS (HTML {html_bytes//1024} KB — parser '{parser_key}' não cobriu)"

            snippet = _html_snippet(soup)
            print(f"{YELLOW}{prefix} ⚠️   ZERO  ({elapsed:.1f}s) — {causa}{RESET}")
            stats["zero"] += 1
            linhas_csv.append(_linha(fonte, "ZERO", 0, html_bytes, causa, snippet))

    # ── Resumo final ──────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print(f"{BOLD}RESUMO{RESET}")
    print(f"  ✅  OK     : {GREEN}{stats['ok']}{RESET}")
    print(f"  ⚠️   ZERO   : {YELLOW}{stats['zero']}{RESET}")
    print(f"  ❌  ERRO   : {RED}{stats['erro']}{RESET}")
    print(f"  ⏭️   PULADO : {stats['pulado']}")
    print(f"  TOTAL  : {total}")

    taxa_ok = stats["ok"] / max(total - stats["pulado"], 1) * 100
    print(f"\n  Taxa de sucesso : {taxa_ok:.0f}%")

    # ── Detalhes dos ZEROs por grupo ──────────────────────────────────
    zeros = [l for l in linhas_csv if l["status"] == "ZERO"]
    if zeros:
        print(f"\n{YELLOW}── ZEROs para corrigir ──{RESET}")
        for l in zeros:
            print(f"  [{l['acronym']}] {l['url']}")
            print(f"    parser={l['parser']}  html={l['html_kb']} KB")
            print(f"    causa: {l['causa']}")
            if l["snippet"]:
                print(f"    snippet: {l['snippet'][:120]}…")
            print()

    # ── Salva CSV ─────────────────────────────────────────────────────
    campos = ["grupo", "acronym", "nome", "url", "parser",
              "status", "n_itens", "html_kb", "causa", "snippet"]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas_csv)

    print(f"\n📄 Relatório salvo em: {csv_path}")


def _linha(fonte: dict, status: str, n: int, html_bytes: int,
           causa: str, snippet: str) -> dict:
    return {
        "grupo":   fonte.get("grupo", ""),
        "acronym": fonte["acronym"],
        "nome":    fonte.get("nome", ""),
        "url":     fonte["url"],
        "parser":  fonte.get("parser", "generic_news"),
        "status":  status,
        "n_itens": n,
        "html_kb": round(html_bytes / 1024, 1),
        "causa":   causa,
        "snippet": snippet[:200],
    }


if __name__ == "__main__":
    diagnosticar()
