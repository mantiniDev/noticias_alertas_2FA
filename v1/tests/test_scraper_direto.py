# tests/test_scraper_direto.py
"""
Testes unitários para core/scraper_direto.py — Subsistemas 1 e 2.

Cobre (sem rede, sem banco de dados):
  - Integridade estrutural de TRIBUNAIS_DIRETO e FONTES_NOTICIAS
  - Parsers com HTML mockado: generic_news, generic_table, tjsp, telegram
  - Helpers _txt e _abs
  - Assinatura e tipo de retorno de buscar_noticias_fontes (com mock de DB)
"""

import pytest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

from core.scraper_direto import (
    FONTES,
    TRIBUNAIS_DIRETO,
    FONTES_NOTICIAS,
    _txt,
    _abs,
    parse_generic_news,
    parse_generic_table,
    parse_tjsp,
    parse_telegram,
    PARSERS,
    _GRUPOS_LABEL,
)

# ---------------------------------------------------------------------------
# Fixtures de HTML mockado
# ---------------------------------------------------------------------------

HTML_GENERIC_NEWS = """
<html><body>
  <article>
    <h2><a href="/noticia/1">PJe registra instabilidade em 5 TRTs</a></h2>
    <p class="resumo">Sistema ficou fora do ar por 3 horas na manha de hoje.</p>
  </article>
  <article>
    <h2><a href="/noticia/2">CNJ lança nova versão do PDPJ-Br</a></h2>
    <p class="resumo">Atualização traz melhorias de desempenho.</p>
  </article>
  <article>
    <h2><a href="/noticia/3">Ai</a></h2>
  </article>
</body></html>
"""

HTML_TABLE = """
<html><body>
  <table>
    <tr><th>Sistema</th><th>Período</th><th>Status</th></tr>
    <tr><td>PJe TRF1</td><td>10/06 08h–12h</td><td>Concluído</td></tr>
    <tr><td>eproc TJRS</td><td>11/06 00h–02h</td><td>Em andamento</td></tr>
    <tr><td>sistema</td><td></td><td></td></tr>
  </table>
</body></html>
"""

HTML_TJSP = """
<html><body>
  <table>
    <tr><th>Data</th><th>Comunicado</th></tr>
    <tr>
      <td>10/06/2025</td>
      <td><a href="/comunicados/123">Indisponibilidade PJe — manutenção programada</a></td>
    </tr>
    <tr>
      <td>09/06/2025</td>
      <td><a href="/comunicados/122">Atualização do certificado digital A3</a></td>
    </tr>
  </table>
</body></html>
"""

HTML_TELEGRAM = """
<html><body>
  <div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message">
      <div class="tgme_widget_message_text">
        Nova versão do PJe 2.1.8.3 disponível: corrige falha no upload de PDF
        e melhora desempenho na consulta de processos.
      </div>
      <a class="tgme_widget_message_date" href="https://t.me/pjenews/451">
        <time>2025-06-10T08:00:00+00:00</time>
      </a>
    </div>
  </div>
  <div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message">
      <div class="tgme_widget_message_text">Curto demais.</div>
    </div>
  </div>
  <div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message">
      <div class="tgme_widget_message_text">Tribunal Regional do Trabalho da 14a Regiao - PJe</div>
      <a class="tgme_widget_message_date" href="https://t.me/pjenews/452">
        <time>2025-06-10T09:00:00+00:00</time>
      </a>
    </div>
  </div>
</body></html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestTxt:
    def test_extrai_texto_simples(self):
        soup = BeautifulSoup("<p>Olá mundo</p>", "lxml")
        assert _txt(soup.find("p")) == "Olá mundo"

    def test_retorna_vazio_para_none(self):
        assert _txt(None) == ""

    def test_strip_espacos(self):
        soup = BeautifulSoup("<p>  texto  </p>", "lxml")
        assert _txt(soup.find("p")) == "texto"


class TestAbs:
    def test_href_absoluto_passa_direto(self):
        assert _abs("https://www.tjsp.jus.br/noticias", "https://www.tjsp.jus.br") \
               == "https://www.tjsp.jus.br/noticias"

    def test_href_relativo_completa(self):
        assert _abs("/noticia/123", "https://www.tjsp.jus.br") \
               == "https://www.tjsp.jus.br/noticia/123"

    def test_javascript_retorna_base(self):
        assert _abs("javascript:void(0)", "https://base.jus.br") \
               == "https://base.jus.br"

    def test_href_vazio_retorna_base(self):
        assert _abs("", "https://base.jus.br") == "https://base.jus.br"


# ---------------------------------------------------------------------------
# Integridade estrutural das listas
# ---------------------------------------------------------------------------

class TestFontes:
    """Testa a estrutura da lista unificada FONTES (97 entradas nested)."""

    CAMPOS_OBRIGATORIOS = {"acronym", "nome", "grupo", "alertas", "noticias"}
    CAMPOS_ALERTAS      = {"url", "parser", "base_url"}
    CAMPOS_NOTICIAS     = {"nome", "url", "parser", "base_url", "tipo"}

    def test_tem_97_entradas(self):
        assert len(FONTES) == 97

    @pytest.mark.parametrize("f", FONTES)
    def test_campos_obrigatorios(self, f):
        faltando = self.CAMPOS_OBRIGATORIOS - f.keys()
        assert not faltando, f"{f.get('acronym','?')} sem campos: {faltando}"

    @pytest.mark.parametrize("f", FONTES)
    def test_alertas_e_dict_ou_none(self, f):
        a = f["alertas"]
        assert a is None or isinstance(a, dict), \
            f"{f['acronym']}: alertas deve ser dict ou None"

    @pytest.mark.parametrize("f", FONTES)
    def test_alertas_campos_obrigatorios(self, f):
        a = f["alertas"]
        if a is None:
            return
        faltando = self.CAMPOS_ALERTAS - a.keys()
        assert not faltando, f"{f['acronym']} alertas sem campos: {faltando}"

    @pytest.mark.parametrize("f", FONTES)
    def test_alertas_url_https(self, f):
        a = f["alertas"]
        if a is None:
            return
        assert a["url"].startswith("https://"), \
            f"{f['acronym']}: alertas URL não começa com https"

    @pytest.mark.parametrize("f", FONTES)
    def test_noticias_e_lista_nao_vazia(self, f):
        assert isinstance(f["noticias"], list) and len(f["noticias"]) > 0, \
            f"{f['acronym']}: noticias deve ser lista não vazia"

    @pytest.mark.parametrize("f", FONTES)
    def test_noticias_campos_obrigatorios(self, f):
        for i, n in enumerate(f["noticias"]):
            faltando = self.CAMPOS_NOTICIAS - n.keys()
            assert not faltando, \
                f"{f['acronym']} noticias[{i}] sem campos: {faltando}"

    @pytest.mark.parametrize("f", FONTES)
    def test_noticias_url_https(self, f):
        for n in f["noticias"]:
            assert n["url"].startswith("https://"), \
                f"{f['acronym']}: noticias URL '{n['url']}' não começa com https"

    def test_tribunais_direto_derivado_corretamente(self):
        """_to_alertas_entry produz 68 entradas com todos os campos planos."""
        assert len(TRIBUNAIS_DIRETO) == 68

    def test_fontes_noticias_derivado_corretamente(self):
        """_to_noticias_entries produz 106 entradas com todos os campos planos."""
        assert len(FONTES_NOTICIAS) == 106


class TestTribunaisDireto:
    CAMPOS_OBRIGATORIOS = {"acronym", "nome", "url", "parser", "base_url", "fase", "tipo", "grupo"}

    def test_tem_exatamente_68_fontes(self):
        assert len(TRIBUNAIS_DIRETO) == 68

    @pytest.mark.parametrize("t", TRIBUNAIS_DIRETO)
    def test_campos_obrigatorios(self, t):
        faltando = self.CAMPOS_OBRIGATORIOS - t.keys()
        assert not faltando, f"{t.get('acronym','?')} sem campos: {faltando}"

    @pytest.mark.parametrize("t", TRIBUNAIS_DIRETO)
    def test_url_https(self, t):
        assert t["url"].startswith("https://"), \
            f"{t['acronym']}: URL não começa com https"

    @pytest.mark.parametrize("t", TRIBUNAIS_DIRETO)
    def test_parser_registrado(self, t):
        assert t["parser"] in PARSERS, \
            f"{t['acronym']}: parser '{t['parser']}' não existe em PARSERS"


class TestFontesNoticias:
    CAMPOS_OBRIGATORIOS = {"nome", "acronym", "url", "tipo", "grupo", "parser", "base_url", "fase"}
    GRUPOS_VALIDOS = set(_GRUPOS_LABEL.keys())

    def test_tem_106_fontes(self):
        assert len(FONTES_NOTICIAS) == 106

    @pytest.mark.parametrize("f", FONTES_NOTICIAS)
    def test_campos_obrigatorios(self, f):
        faltando = self.CAMPOS_OBRIGATORIOS - f.keys()
        assert not faltando, f"{f.get('acronym','?')} sem campos: {faltando}"

    @pytest.mark.parametrize("f", FONTES_NOTICIAS)
    def test_url_https(self, f):
        assert f["url"].startswith("https://"), \
            f"{f['acronym']}: URL não começa com https"

    @pytest.mark.parametrize("f", FONTES_NOTICIAS)
    def test_grupo_valido(self, f):
        assert f["grupo"] in self.GRUPOS_VALIDOS, \
            f"{f['acronym']}: grupo '{f['grupo']}' inválido"

    @pytest.mark.parametrize("f", FONTES_NOTICIAS)
    def test_parser_registrado(self, f):
        assert f["parser"] in PARSERS, \
            f"{f['acronym']}: parser '{f['parser']}' não existe em PARSERS"

    def test_todos_grupos_representados(self):
        grupos_presentes = {f["grupo"] for f in FONTES_NOTICIAS}
        assert grupos_presentes == self.GRUPOS_VALIDOS

    def test_nenhuma_fonte_com_vpn_required_ativo(self):
        """TRF3 não deve mais ter vpn_required=True."""
        vpn = [f["acronym"] for f in FONTES_NOTICIAS if f.get("vpn_required")]
        assert not vpn, f"Fontes com vpn_required ativo: {vpn}"


# ---------------------------------------------------------------------------
# Parsers com HTML mockado
# ---------------------------------------------------------------------------

class TestParseGenericNews:
    def _soup(self):
        return BeautifulSoup(HTML_GENERIC_NEWS, "lxml")

    def test_retorna_lista(self):
        assert isinstance(parse_generic_news(self._soup(), "TST", "https://tst.jus.br"), list)

    def test_extrai_dois_itens_validos(self):
        # O 3º artigo tem título "Ai" (< 10 chars) → deve ser ignorado
        result = parse_generic_news(self._soup(), "TST", "https://tst.jus.br")
        assert len(result) == 2

    def test_titulo_correto(self):
        result = parse_generic_news(self._soup(), "TST", "https://tst.jus.br")
        assert "PJe registra instabilidade" in result[0]["titulo"]

    def test_link_absoluto(self):
        result = parse_generic_news(self._soup(), "TST", "https://tst.jus.br")
        assert result[0]["link"].startswith("https://tst.jus.br")

    def test_resumo_extraido(self):
        result = parse_generic_news(self._soup(), "TST", "https://tst.jus.br")
        assert "fora do ar" in result[0]["resumo"].lower()


class TestParseGenericTable:
    def _soup(self):
        return BeautifulSoup(HTML_TABLE, "lxml")

    def test_retorna_dois_itens_reais(self):
        # Linha de cabeçalho e linha "sistema" devem ser ignoradas
        result = parse_generic_table(self._soup(), "TRF1", "https://trf1.jus.br")
        assert len(result) == 2

    def test_titulo_primeira_linha(self):
        result = parse_generic_table(self._soup(), "TRF1", "https://trf1.jus.br")
        assert result[0]["titulo"] == "PJe TRF1"

    def test_resumo_inclui_colunas_extras(self):
        result = parse_generic_table(self._soup(), "TRF1", "https://trf1.jus.br")
        assert "10/06 08h" in result[0]["resumo"]


class TestParseTjsp:
    def _soup(self):
        return BeautifulSoup(HTML_TJSP, "lxml")

    def test_extrai_dois_comunicados(self):
        result = parse_tjsp(self._soup(), "TJSP", "https://www.tjsp.jus.br")
        assert len(result) == 2

    def test_titulo_vem_do_link(self):
        result = parse_tjsp(self._soup(), "TJSP", "https://www.tjsp.jus.br")
        assert "Indisponibilidade PJe" in result[0]["titulo"]


class TestParseTelegram:
    def _soup(self):
        return BeautifulSoup(HTML_TELEGRAM, "lxml")

    def test_extrai_mensagem_longa(self):
        # Msg 1: 118 chars (real news) → OK
        # Msg 2: "Curto demais." (13 chars) → descartada por min 80
        # Msg 3: "Tribunal ... - PJe" (49 chars) → descartada por min 80
        result = parse_telegram(self._soup(), "PJeNews", "https://t.me")
        assert len(result) == 1

    def test_titulo_contem_conteudo(self):
        result = parse_telegram(self._soup(), "PJeNews", "https://t.me")
        assert "PJe" in result[0]["titulo"]

    def test_link_para_mensagem(self):
        result = parse_telegram(self._soup(), "PJeNews", "https://t.me")
        assert "t.me/pjenews/451" in result[0]["link"]

    def test_descarta_link_generico_portal(self):
        """Mensagens do tipo 'Tribunal X - PJe' não devem ser extraídas."""
        result = parse_telegram(self._soup(), "PJeNews", "https://t.me")
        titulos = [r["titulo"] for r in result]
        assert not any("Regiao - PJe" in t for t in titulos)


# ---------------------------------------------------------------------------
# buscar_noticias_fontes — retorno e estrutura (mock de DB e rede)
# ---------------------------------------------------------------------------

class TestBuscarNoticiasFontes:
    """
    Testa apenas a estrutura de retorno sem chamar a rede nem o banco.
    Mocka fetch_page para retornar HTML simples e as funções de DB para no-op.
    """

    @patch("core.scraper_direto.verificar_titulo_chave", return_value=False)
    @patch("core.scraper_direto.verificar_status_noticia", return_value=False)
    @patch("core.scraper_direto.avaliar_noticia", return_value=("novo", "Aprovado", "pje", "pje"))
    @patch("core.scraper_direto.fetch_page")
    def test_retorna_dict_com_todos_os_grupos(
        self, mock_fetch, mock_avaliar, mock_status, mock_titulo
    ):
        from core.scraper_direto import buscar_noticias_fontes, _GRUPOS_LABEL

        # Retorna HTML com uma notícia válida para cada fonte
        mock_fetch.return_value = BeautifulSoup(HTML_GENERIC_NEWS, "lxml")

        resultado = buscar_noticias_fontes()

        assert isinstance(resultado, dict)
        assert set(resultado.keys()) == set(_GRUPOS_LABEL.keys())

    @patch("core.scraper_direto.verificar_titulo_chave", return_value=False)
    @patch("core.scraper_direto.verificar_status_noticia", return_value=False)
    @patch("core.scraper_direto.avaliar_noticia", return_value=("novo", "Aprovado", "pje", "pje"))
    @patch("core.scraper_direto.fetch_page")
    def test_cada_noticia_tem_campos_obrigatorios(
        self, mock_fetch, mock_avaliar, mock_status, mock_titulo
    ):
        from core.scraper_direto import buscar_noticias_fontes

        mock_fetch.return_value = BeautifulSoup(HTML_GENERIC_NEWS, "lxml")

        resultado = buscar_noticias_fontes()

        for grupo, noticias in resultado.items():
            for n in noticias:
                for campo in ("titulo", "link", "fonte", "grupo", "tipo", "data_obj"):
                    assert campo in n, f"Campo '{campo}' ausente em notícia do grupo {grupo}"

    @patch("core.scraper_direto.fetch_page", return_value=None)
    def test_sem_rede_retorna_grupos_vazios(self, mock_fetch):
        from core.scraper_direto import buscar_noticias_fontes, _GRUPOS_LABEL

        resultado = buscar_noticias_fontes()

        assert isinstance(resultado, dict)
        assert all(resultado[g] == [] for g in _GRUPOS_LABEL)
