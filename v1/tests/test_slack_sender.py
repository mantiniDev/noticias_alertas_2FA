"""Testes para core/slack_sender.py"""

import pytest
from unittest.mock import MagicMock, patch

from core.slack_sender import (
    _limpar_texto,
    _resumir_texto,
    _rotulo_origem,
    _rotulo_link,
    _acao_sugerida,
    _montar_link,
    _build_message,
    send_alerts,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

class TestLimparTexto:
    def test_escapa_ampersand(self):
        assert "&amp;" in _limpar_texto("A & B")

    def test_escapa_menor(self):
        assert "&lt;" in _limpar_texto("<tag>")

    def test_escapa_maior(self):
        assert "&gt;" in _limpar_texto("<tag>")

    def test_none_retorna_vazio(self):
        assert _limpar_texto(None) == ""

    def test_strip(self):
        assert _limpar_texto("  ok  ") == "ok"


class TestResumirTexto:
    def test_texto_curto_intacto(self):
        assert _resumir_texto("abc", 10) == "abc"

    def test_texto_longo_truncado(self):
        resultado = _resumir_texto("a" * 100, 20)
        assert len(resultado) == 20
        assert resultado.endswith("...")

    def test_none_retorna_vazio(self):
        assert _resumir_texto(None, 50) == ""

    def test_espacos_normalizados(self):
        assert _resumir_texto("a   b   c", 50) == "a b c"


class TestRotuloOrigem:
    def test_noticias(self):
        assert _rotulo_origem("noticias") == "Notícias"

    def test_noticias_acentuado(self):
        assert _rotulo_origem("notícias") == "Notícias"

    def test_clipping(self):
        assert _rotulo_origem("clipping") == "Diário Oficial"

    def test_script_git(self):
        assert _rotulo_origem("script_git") == "RSS"

    def test_rss(self):
        assert _rotulo_origem("rss") == "RSS"

    def test_desconhecido(self):
        assert _rotulo_origem("outro") == "outro"

    def test_none_retorna_fonte(self):
        assert _rotulo_origem(None) == "Fonte"


class TestRotuloLink:
    def test_clipping_retorna_publicacao(self):
        assert _rotulo_link("clipping") == "Abrir publicação"

    def test_outros_retorna_noticia(self):
        assert _rotulo_link("noticias") == "Abrir notícia"
        assert _rotulo_link(None) == "Abrir notícia"


class TestAcaoSugerida:
    def test_relevante(self):
        assert "crawler" in _acao_sugerida("RELEVANTE")

    def test_talvez(self):
        assert "acompanhar" in _acao_sugerida("TALVEZ")

    def test_outro(self):
        assert _acao_sugerida("IRRELEVANTE") == ""


class TestMontarLink:
    def test_url_valida(self):
        assert "<https://x.com|Texto>" == _montar_link("https://x.com", "Texto")

    def test_url_vazia(self):
        assert _montar_link("", "Texto") == "Sem link disponível"

    def test_url_none(self):
        assert _montar_link(None, "Texto") == "Sem link disponível"


# ── _build_message ────────────────────────────────────────────────────────────

def _item(classificacao="RELEVANTE", **kw):
    base = {
        "id": "1",
        "origem": "noticias",
        "tribunal_fonte": "TJSP",
        "data_publicacao": "2026-08-11",
        "titulo": "Tribunal migra para eProc",
        "descricao": "O TJSP anunciou migração.",
        "url": "https://tjsp.jus.br/noticia",
        "url_fonte": "",
        "classificacao": classificacao,
        "justificativa": "Impacto direto em crawler.",
    }
    base.update(kw)
    return base


class TestBuildMessage:
    def test_contem_titulo(self):
        msg = _build_message([_item()])
        assert "Tribunal migra para eProc" in msg

    def test_emoji_relevante(self):
        assert ":large_green_circle:" in _build_message([_item("RELEVANTE")])

    def test_emoji_talvez(self):
        assert ":large_yellow_circle:" in _build_message([_item("TALVEZ")])

    def test_resumo_contagem(self):
        itens = [_item("RELEVANTE"), _item("TALVEZ")]
        msg = _build_message(itens)
        assert "Relevantes: 1" in msg
        assert "Talvez: 1" in msg
        assert "Total: 2" in msg

    def test_sem_link_exibe_aviso(self):
        item = _item(url="", url_fonte="")
        msg = _build_message([item])
        assert "Sem link disponível" in msg

    def test_link_presente(self):
        msg = _build_message([_item()])
        assert "https://tjsp.jus.br/noticia" in msg

    def test_classificacao_minuscula_conta_corretamente(self):
        itens = [_item("relevante"), _item("talvez")]
        msg = _build_message(itens)
        assert "Relevantes: 1" in msg
        assert "Talvez: 1" in msg

    def test_classificacao_mista_emoji_verde(self):
        assert ":large_green_circle:" in _build_message([_item("Relevante")])

    def test_classificacao_mista_emoji_amarelo(self):
        assert ":large_yellow_circle:" in _build_message([_item("Talvez")])

    def test_classificacao_minuscula_acao_sugerida(self):
        msg = _build_message([_item("relevante")])
        assert "crawler" in msg

    def test_classificacao_com_espacos_conta_corretamente(self):
        msg = _build_message([_item(" RELEVANTE "), _item(" TALVEZ ")])
        assert "Relevantes: 1" in msg
        assert "Talvez: 1" in msg


# ── send_alerts ───────────────────────────────────────────────────────────────

class TestSendAlerts:
    def test_nenhum_item_nao_chama_webhook(self):
        with patch("core.slack_sender._send_webhook") as mock_wh:
            send_alerts([])
            mock_wh.assert_not_called()

    def test_irrelevante_filtrado(self):
        with patch("core.slack_sender._send_webhook") as mock_wh:
            send_alerts([_item("IRRELEVANTE")])
            mock_wh.assert_not_called()

    def test_classificacao_none_nao_levanta_erro(self):
        with patch("core.slack_sender._send_webhook") as mock_wh:
            send_alerts([_item(classificacao=None)])
            mock_wh.assert_not_called()

    def test_sem_justificativa_filtrado(self):
        with patch("core.slack_sender._send_webhook") as mock_wh:
            send_alerts([_item(justificativa="")])
            mock_wh.assert_not_called()

    def test_relevante_chama_webhook(self):
        with patch("core.slack_sender._send_webhook") as mock_wh:
            send_alerts([_item("RELEVANTE")])
            mock_wh.assert_called_once()

    def test_talvez_chama_webhook(self):
        with patch("core.slack_sender._send_webhook") as mock_wh:
            send_alerts([_item("TALVEZ")])
            mock_wh.assert_called_once()

    def test_mensagem_contem_titulo(self):
        capturado = {}

        def fake_send(texto):
            capturado["texto"] = texto

        with patch("core.slack_sender._send_webhook", side_effect=fake_send):
            send_alerts([_item("RELEVANTE")])

        assert "Tribunal migra para eProc" in capturado["texto"]


class TestSendWebhookIntegracao:
    def test_webhook_url_ausente_levanta_erro(self):
        from core.slack_sender import _send_webhook

        with patch.dict("os.environ", {}, clear=True):
            import os
            os.environ.pop("SLACK_WEBHOOK_URL", None)
            with pytest.raises(EnvironmentError, match="SLACK_WEBHOOK_URL"):
                _send_webhook("teste")

    def test_resposta_nao_ok_levanta_erro(self):
        from core.slack_sender import _send_webhook

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "invalid"

        with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
            with patch("core.slack_sender.requests.post", return_value=mock_resp):
                with pytest.raises(RuntimeError, match="Erro ao enviar"):
                    _send_webhook("teste")

    def test_status_500_levanta_erro(self):
        from core.slack_sender import _send_webhook

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"

        with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
            with patch("core.slack_sender.requests.post", return_value=mock_resp):
                with pytest.raises(RuntimeError, match="Erro ao enviar"):
                    _send_webhook("teste")

    def test_envio_bem_sucedido(self):
        from core.slack_sender import _send_webhook

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "ok"

        with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
            with patch("core.slack_sender.requests.post", return_value=mock_resp) as mock_post:
                _send_webhook("mensagem de teste")
                mock_post.assert_called_once()
                call_kwargs = mock_post.call_args
                assert call_kwargs[1]["json"] == {"text": "mensagem de teste"}
