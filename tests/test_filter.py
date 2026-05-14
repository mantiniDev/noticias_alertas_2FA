# tests/test_filter.py
"""
Testes unitários para core/filter.py — motor de filtragem do MAST.

Cobre:
  - remover_acentos
  - titulo_tem_imunidade
  - texto_tem_bloqueio
  - texto_tem_alerta
  - avaliar_noticia (fluxo completo)
"""
import pytest
from core.filter import (
    remover_acentos,
    titulo_tem_imunidade,
    texto_tem_bloqueio,
    texto_tem_alerta,
    avaliar_noticia,
)


# ─────────────────────────────────────────────
# remover_acentos
# ─────────────────────────────────────────────
class TestRemoverAcentos:
    def test_remove_cedilha(self):
        assert remover_acentos("ação") == "acao"

    def test_remove_til(self):
        assert remover_acentos("manutenção") == "manutencao"

    def test_remove_acento_agudo(self):
        assert remover_acentos("indisponível") == "indisponivel"

    def test_string_vazia(self):
        assert remover_acentos("") == ""

    def test_none_retorna_vazio(self):
        assert remover_acentos(None) == ""

    def test_sem_acentos_inalterado(self):
        assert remover_acentos("sistema") == "sistema"


# ─────────────────────────────────────────────
# titulo_tem_imunidade
# ─────────────────────────────────────────────
class TestImunidade:
    def test_pje_e_imune(self):
        imune, termo = titulo_tem_imunidade("instabilidade no pje hoje")
        assert imune is True
        assert termo is not None

    def test_dois_fatores_e_imune(self):
        imune, _ = titulo_tem_imunidade("habilitacao de dois fatores obrigatoria")
        assert imune is True

    def test_2fa_e_imune(self):
        imune, _ = titulo_tem_imunidade("tribunal exige 2fa para acesso")
        assert imune is True

    def test_ransomware_e_imune(self):
        imune, _ = titulo_tem_imunidade("ataque de ransomware paralisa tribunal")
        assert imune is True

    def test_sem_termo_imune_retorna_false(self):
        imune, termo = titulo_tem_imunidade("concurso publico aberto para advogados")
        assert imune is False
        assert termo is None

    def test_plural_imune(self):
        # "indisponibilidades" deve casar com padrão de "indisponibilidade"
        imune, _ = titulo_tem_imunidade("registro de indisponibilidades do sistema")
        assert imune is True


# ─────────────────────────────────────────────
# texto_tem_bloqueio
# ─────────────────────────────────────────────
class TestBloqueio:
    def test_concurso_bloqueia(self):
        bloqueado, palavra, _ = texto_tem_bloqueio("abertura de concurso publico no tribunal")
        assert bloqueado is True
        assert palavra is not None

    def test_receita_federal_bloqueia(self):
        bloqueado, _, _ = texto_tem_bloqueio("sistema da receita federal fora do ar")
        assert bloqueado is True

    def test_estagio_bloqueia(self):
        bloqueado, _, _ = texto_tem_bloqueio("processo seletivo para estagio no tjsp")
        assert bloqueado is True

    def test_texto_limpo_nao_bloqueia(self):
        bloqueado, palavra, termo = texto_tem_bloqueio("atualizacao do sistema pje versao 2.3")
        assert bloqueado is False
        assert palavra is None
        assert termo is None


# ─────────────────────────────────────────────
# texto_tem_alerta
# ─────────────────────────────────────────────
class TestAlerta:
    def test_termo_forte_pje(self):
        alerta, palavra, _ = texto_tem_alerta("instabilidade no pje afeta advogados")
        assert alerta is True
        assert "pje" in palavra.lower()

    def test_termo_forte_eproc(self):
        alerta, _, _ = texto_tem_alerta("eproc apresenta lentidao nesta manha")
        assert alerta is True

    def test_termo_forte_2fa(self):
        alerta, _, termo = texto_tem_alerta("tribunal torna 2fa obrigatorio")
        assert alerta is True
        assert "Forte" in termo

    def test_termo_especifico_2fa_pje(self):
        alerta, _, termo = texto_tem_alerta("2fa pje agora exigido para todos os usuarios")
        assert alerta is True
        assert "Específico" in termo

    def test_termo_composto_fora_do_ar(self):
        alerta, _, termo = texto_tem_alerta("sistema do tribunal fora do ar ha horas")
        assert alerta is True
        assert "Composto" in termo

    def test_termo_composto_lentidao_portal(self):
        # Frase sem termo forte isolado → só o composto deve bater
        alerta, _, termo = texto_tem_alerta("lentidao no portal do judiciario hoje")
        assert alerta is True
        assert "Composto" in termo

    def test_sem_termos_ti_retorna_false(self):
        alerta, palavra, termo = texto_tem_alerta("evento cultural no tribunal de justica")
        assert alerta is False
        assert palavra is None
        assert termo is None


# ─────────────────────────────────────────────
# avaliar_noticia — fluxo completo
# ─────────────────────────────────────────────
class TestAvaliarNoticia:
    def test_retorna_4_valores(self):
        resultado = avaliar_noticia("titulo qualquer", "resumo qualquer")
        assert len(resultado) == 4

    def test_aprovado_pelo_titulo(self):
        status, motivo, _, _ = avaliar_noticia(
            "Instabilidade no PJe afeta tribunais do sul", ""
        )
        assert status == "novo"
        assert "Aprovado" in motivo

    def test_bloqueado_pelo_titulo(self):
        status, motivo, _, _ = avaliar_noticia(
            "Concurso publico aberto no TJSP", ""
        )
        assert status == "bloqueado"
        assert "Blacklist" in motivo

    def test_imunidade_supera_bloqueio_no_titulo(self):
        # "pje" é imune → mesmo com "concurso" no título, aprova se houver alerta
        status, _, _, _ = avaliar_noticia(
            "Abertura de inscricoes no modulo pje para concurso de vagas", ""
        )
        assert status == "novo"

    def test_aprovado_pelo_resumo(self):
        status, motivo, _, _ = avaliar_noticia(
            "Comunicado importante do tribunal",
            "O sistema PJe apresentou instabilidade nesta manha",
        )
        assert status == "novo"
        assert "Resumo" in motivo

    def test_bloqueado_pelo_resumo(self):
        status, motivo, _, _ = avaliar_noticia(
            "Notícia do dia no tribunal",
            "Abertura de processo seletivo para estagiarios da area de TI",
        )
        assert status == "bloqueado"
        assert "Resumo" in motivo

    def test_arquivo_pdf_rejeitado(self):
        status, motivo, _, _ = avaliar_noticia("portaria_2024.pdf - TJSP", "")
        assert status == "irrelevante"
        assert "Arquivo" in motivo

    def test_irrelevante_sem_termos_ti(self):
        status, motivo, _, _ = avaliar_noticia(
            "Tribunal realiza evento cultural no auditório",
            "Grande publico compareceu ao evento de comemoração",
        )
        assert status == "irrelevante"
        assert "Sem Termos TI" in motivo

    def test_palavra_extraida_preenchida_quando_aprovado(self):
        _, _, palavra, termo = avaliar_noticia("pje fora do ar nesta manha", "")
        assert palavra not in (None, "N/A")
        assert termo not in (None, "N/A")

    def test_palavra_na_quando_irrelevante(self):
        _, _, palavra, termo = avaliar_noticia("evento cultural no tribunal", "")
        assert palavra == "N/A"
        assert termo == "N/A"
