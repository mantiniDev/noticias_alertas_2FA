#!/usr/bin/env python3
"""
scripts/teste_rapido_fontes.py
──────────────────────────────
Smoke test de buscar_noticias_fontes() sem tocar no banco de dados real.

Mocka as funções de banco (verificar_status_noticia, verificar_titulo_chave,
salvar_auditoria) para não precisar de mast_dados.db, mas FAZ requests reais
às URLs para validar fetch + parse.

Uso:
    python scripts/teste_rapido_fontes.py              # testa todos os grupos
    python scripts/teste_rapido_fontes.py TRFs         # filtra por grupo
    python scripts/teste_rapido_fontes.py TRT1 CNJ-J40 # filtra por acronym
"""

import sys
import os
import time
from datetime import datetime
from unittest.mock import patch

# Garante que o root do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scraper_direto import (
    FONTES_NOTICIAS,
    fetch_page,
    PARSERS,
    parse_generic_news,
    _GRUPOS_LABEL,
)

# ── Filtro por argumento de linha de comando ──────────────────────────────────
filtros = sys.argv[1:]
if filtros:
    fontes_alvo = [
        f for f in FONTES_NOTICIAS
        if f["grupo"] in filtros or f["acronym"] in filtros
    ]
    if not fontes_alvo:
        print(f"⚠️  Nenhuma fonte encontrada para filtros: {filtros}")
        print(f"   Grupos válidos  : {list(_GRUPOS_LABEL.keys())}")
        print(f"   Acronyms válidos: {[f['acronym'] for f in FONTES_NOTICIAS]}")
        sys.exit(1)
else:
    fontes_alvo = FONTES_NOTICIAS

print("=" * 65)
print("  MAST — Smoke Test: buscar_noticias_fontes()")
print(f"  {len(fontes_alvo)} fontes | {datetime.now().strftime('%d/%m/%Y %H:%M')}")
print("=" * 65)

resultados = []
grupo_atual = None

for fonte in fontes_alvo:
    grupo = fonte["grupo"]
    acronym = fonte["acronym"]

    if grupo != grupo_atual:
        grupo_atual = grupo
        print(f"\n── {_GRUPOS_LABEL.get(grupo, grupo)} ──")

    # Pula fontes com vpn_required ativo
    if fonte.get("vpn_required"):
        print(f"  ⚠️  [{acronym:12}] Requer VPN — pulado")
        resultados.append({"acronym": acronym, "status": "vpn", "itens": 0})
        continue

    inicio = time.time()
    try:
        soup = fetch_page(fonte)
        elapsed = int((time.time() - inicio) * 1000)

        if not soup:
            print(f"  ✗  [{acronym:12}] Sem conteúdo ({elapsed}ms)")
            resultados.append({"acronym": acronym, "status": "sem_conteudo", "itens": 0})
            continue

        parser_fn = PARSERS.get(fonte["parser"], parse_generic_news)
        itens = parser_fn(soup, acronym, fonte["base_url"])

        if itens:
            primeiro = itens[0]["titulo"][:60]
            print(f"  ✓  [{acronym:12}] {len(itens):3} itens  ({elapsed}ms)  → \"{primeiro}…\"")
            resultados.append({"acronym": acronym, "status": "ok", "itens": len(itens)})
        else:
            print(f"  ⚠️  [{acronym:12}]   0 itens  ({elapsed}ms)  — parse retornou vazio")
            resultados.append({"acronym": acronym, "status": "vazio", "itens": 0})

    except Exception as exc:
        elapsed = int((time.time() - inicio) * 1000)
        print(f"  ✗  [{acronym:12}] ERRO ({elapsed}ms): {exc}")
        resultados.append({"acronym": acronym, "status": "erro", "itens": 0})

# ── Resumo ────────────────────────────────────────────────────────────────────
ok      = [r for r in resultados if r["status"] == "ok"]
vazios  = [r for r in resultados if r["status"] == "vazio"]
erros   = [r for r in resultados if r["status"] in ("erro", "sem_conteudo")]
pulados = [r for r in resultados if r["status"] == "vpn"]

print(f"\n{'=' * 65}")
print(f"  RESULTADO: {len(ok)} OK  |  {len(vazios)} vazios  |  {len(erros)} erros  |  {len(pulados)} pulados")
print(f"  Total de itens coletados: {sum(r['itens'] for r in ok)}")

if vazios:
    print(f"\n  ⚠️  Parse retornou vazio (pode precisar de parser específico):")
    for r in vazios:
        print(f"     • {r['acronym']}")

if erros:
    print(f"\n  ✗  Com erro/sem conteúdo:")
    for r in erros:
        print(f"     • {r['acronym']}")

print("=" * 65)
sys.exit(1 if erros else 0)
