#!/usr/bin/env python3
"""
inspecionar_zeros.py
────────────────────
Inspeciona a estrutura HTML dos fontes com status ZERO/ERRO para
identificar qual seletor de área está sendo escolhido e por quê o
parse_generic_news não encontra itens.

Uso:
    cd v1
    py -3 inspecionar_zeros.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import logging
logging.basicConfig(level=logging.WARNING)

from core.scraper_direto import (
    FONTES_NOTICIAS, fetch_page, _NAV_TAGS, _limpar_data_titulo,
)

ALVOS = ["CNMP", "TJAP", "TRT23", "TJPI"]

AREA_SELETORES = [
    "main", "#main", ".main-content", "#content", "#main-content",
    ".content-area", ".portlet-body", ".journal-content-article",
    ".portlet-content", ".lfr-portlet-body", ".asset-publisher-content",
    "#portal-content", ".conteudo", "#conteudo", ".page-content",
]

SEP = "=" * 70


def inspecionar(fonte: dict) -> None:
    acronym = fonte["acronym"]
    url     = fonte["url"]
    print(f"\n{SEP}")
    print(f"  [{acronym}]  {url}")
    print(SEP)

    if fonte.get("skip"):
        print(f"  ⏭️  PULADO: {fonte.get('skip_reason', 'skip=True')}")
        return

    # ── Fetch ──────────────────────────────────────────────────────────
    try:
        soup = fetch_page(fonte)
    except Exception as exc:
        print(f"  ❌ ERRO no fetch: {exc}")
        return

    if not soup:
        print("  ❌ fetch_page retornou None")
        return

    print(f"  HTML total após fetch: {len(str(soup)) // 1024} KB")

    # ── Remove nav (igual ao parse_generic_news) ───────────────────────
    removidos = 0
    for tag in soup.select(_NAV_TAGS):
        tag.decompose()
        removidos += 1
    print(f"  Tags nav/acessib. removidas: {removidos}")

    # ── Descobre qual área seria selecionada ───────────────────────────
    area_matched = None
    area_sel_name = "soup (nenhum seletor matchou)"
    for sel in AREA_SELETORES:
        tag = soup.select_one(sel)
        if tag:
            area_matched = tag
            area_sel_name = sel
            break
    area = area_matched or soup

    print(f"\n  ── Área selecionada: {area_sel_name}")
    print(f"     Tamanho da área : {len(str(area)) // 1024} KB de {len(str(soup)) // 1024} KB")

    # Conta quantas vezes o seletor aparece na página (Liferay tem múltiplos portlets!)
    if area_matched:
        total_igual = len(soup.select(area_sel_name))
        print(f"     Ocorrências de '{area_sel_name}' no soup: {total_igual}")
        if total_igual > 1:
            print(f"     ⚠️  ATENÇÃO: select_one escolhe o 1º de {total_igual} — pode ser portlet errado!")

    # ── Estatísticas de elementos na área ─────────────────────────────
    print(f"\n  ── Elementos na área:")
    for sel_check in ["article", "h2 a", "h3 a", "h4 a", ".views-row", ".portlet-content"]:
        n = len(area.select(sel_check))
        if n:
            print(f"     {sel_check:<30}: {n}")

    a_tags = area.select("a[href]")
    print(f"     {'a[href]':<30}: {len(a_tags)}")

    # ── Primeiros 8 links com texto útil ──────────────────────────────
    print(f"\n  ── Primeiros 8 links com texto na área:")
    count = 0
    for a in a_tags:
        raw  = a.get_text(" ", strip=True)
        limpo = _limpar_data_titulo(raw)
        href  = a.get("href", "")
        if len(raw) > 3:
            status = ""
            if len(limpo) >= 25 and not href.startswith("#") and "javascript" not in href:
                status = " ← S5 pegaria"
            print(f"     [{count+1:02d}] raw='{raw[:70]}'" )
            if limpo != raw:
                print(f"          lim='{limpo[:70]}'{status}")
            else:
                print(f"          {status or '(texto = limpo)'}")
            count += 1
            if count >= 8:
                break

    # ── Primeiros 5 h2/h3/h4 ─────────────────────────────────────────
    print(f"\n  ── Primeiros 5 h2/h3/h4 na área:")
    for i, h in enumerate(area.select("h2, h3, h4")[:5]):
        txt  = h.get_text(" ", strip=True)[:80]
        a_in = h.find("a")
        href = a_in.get("href", "–")[:50] if a_in else "sem <a>"
        print(f"     [{i+1}] <{h.name}> '{txt}' → {href}")

    # ── Se há múltiplos portlets, mostra o MAIOR ───────────────────────
    portlets = soup.select(".portlet-content")
    if len(portlets) > 1:
        maior = max(portlets, key=lambda p: len(str(p)))
        print(f"\n  ── Maior portlet-content: {len(str(maior)) // 1024} KB")
        a_maior = maior.select("a[href]")
        print(f"     Links a[href] nele: {len(a_maior)}")
        for i, a in enumerate(a_maior[:5]):
            raw = a.get_text(" ", strip=True)[:70]
            href = a.get("href", "")[:50]
            print(f"     [{i+1}] '{raw}' → {href}")


if __name__ == "__main__":
    for fonte in FONTES_NOTICIAS:
        if fonte["acronym"] in ALVOS:
            inspecionar(fonte)
    print(f"\n{SEP}\nInspeção concluída.\n")
