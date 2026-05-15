# tests/test_scraper.py
"""
Testes unitários para os padrões de detecção de páginas de sistema
definidos em core/scraper.py.

Cobre:
  - _RE_FONTE_DOMINIO  : distingue domínio puro de nome de fonte legítimo
  - _RE_TITULO_SISTEMA : detecta títulos genéricos de telas de sistema
  - Combinação: domínio puro + título de sistema  → deve ser descartado
  - Combinação: fonte legítima + qualquer título  → NÃO deve ser descartado
"""
import pytest
from core.scraper import _RE_FONTE_DOMINIO, _RE_TITULO_SISTEMA


# ─────────────────────────────────────────────
# _RE_FONTE_DOMINIO — fonte parece domínio puro
# ─────────────────────────────────────────────
class TestFonteDominio:
    def test_dominio_prd_tjrj(self):
        assert _RE_FONTE_DOMINIO.match("prd.tjrj.pje.jus.br")

    def test_dominio_tjrj_pje(self):
        assert _RE_FONTE_DOMINIO.match("tjrj.pje.jus.br")

    def test_dominio_simples(self):
        assert _RE_FONTE_DOMINIO.match("tjsp.jus.br")

    def test_fonte_legitima_com_espaco(self):
        # "TJRJ Notícias" tem espaço — não é domínio puro
        assert not _RE_FONTE_DOMINIO.match("TJRJ Noticias")

    def test_fonte_google_news(self):
        assert not _RE_FONTE_DOMINIO.match("Google News")

    def test_fonte_consultor_juridico(self):
        assert not _RE_FONTE_DOMINIO.match("Consultor Juridico")

    def test_fonte_cnj_noticias(self):
        assert not _RE_FONTE_DOMINIO.match("CNJ - Noticias")


# ─────────────────────────────────────────────
# _RE_TITULO_SISTEMA — título de tela genérica
# ─────────────────────────────────────────────
class TestTituloSistema:
    def test_processo_judicial_eletronico(self):
        assert _RE_TITULO_SISTEMA.search("processo judicial eletronico")

    def test_detalhe_do_processo(self):
        assert _RE_TITULO_SISTEMA.search("detalhe do processo")

    def test_consulta_processual(self):
        assert _RE_TITULO_SISTEMA.search("consulta processual")

    def test_acesso_externo(self):
        assert _RE_TITULO_SISTEMA.search("acesso externo")

    def test_pagina_inicial(self):
        assert _RE_TITULO_SISTEMA.search("pagina inicial")

    def test_login_puro(self):
        assert _RE_TITULO_SISTEMA.search("login")

    def test_acesso_ao_sistema(self):
        assert _RE_TITULO_SISTEMA.search("acesso ao sistema")

    def test_noticia_real_pje_instabilidade(self):
        # Notícia legítima NÃO deve bater no padrão de tela
        assert not _RE_TITULO_SISTEMA.search(
            "instabilidade no pje afeta tribunais do sul"
        )

    def test_noticia_real_certificado(self):
        assert not _RE_TITULO_SISTEMA.search(
            "tribunais migram para certificado digital em nuvem"
        )

    def test_noticia_real_2fa(self):
        assert not _RE_TITULO_SISTEMA.search(
            "tjrj torna 2fa obrigatorio para advogados"
        )


# ─────────────────────────────────────────────
# Combinação: domínio puro + título de sistema
# ─────────────────────────────────────────────
class TestCombinacao:
    def _deve_descartar(self, fonte: str, titulo: str) -> bool:
        """Replica a lógica do guard em extrair_noticias_do_feed."""
        return bool(
            _RE_FONTE_DOMINIO.match(fonte)
            and _RE_TITULO_SISTEMA.search(titulo)
        )

    def test_pagina_pje_tjrj_descartada(self):
        assert self._deve_descartar(
            "prd.tjrj.pje.jus.br",
            "processo judicial eletronico",
        )

    def test_detalhe_processo_descartado(self):
        assert self._deve_descartar(
            "tjrj.pje.jus.br",
            "detalhe do processo",
        )

    def test_consulta_dominio_descartada(self):
        assert self._deve_descartar(
            "eproc.tjsc.jus.br",
            "consulta processual",
        )

    def test_noticia_real_fonte_dominio_nao_descartada(self):
        # Domínio puro mas título de notícia legítima → NÃO descarta
        assert not self._deve_descartar(
            "tjrj.jus.br",
            "instabilidade no pje afeta advogados",
        )

    def test_titulo_sistema_fonte_legitima_nao_descartada(self):
        # Título de tela mas fonte com nome legítimo → NÃO descarta
        assert not self._deve_descartar(
            "Consultor Juridico",
            "processo judicial eletronico",
        )

    def test_ambos_limpos_nao_descartado(self):
        assert not self._deve_descartar(
            "TJSP Noticias",
            "instabilidade no eproc afeta advogados de sp",
        )
