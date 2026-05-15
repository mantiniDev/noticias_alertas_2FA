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
    normalizar_titulo_chave,
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
# normalizar_titulo_chave
# ─────────────────────────────────────────────
class TestNormalizarTituloChave:
    def test_remove_prefixo_data_simples(self):
        chave = normalizar_titulo_chave("15/04/2026 – PORTAL DE CUSTAS - INDISPONIBILIDADE")
        assert not chave.startswith("15")
        assert "portal de custas" in chave

    def test_remove_prefixo_data_intervalo(self):
        chave = normalizar_titulo_chave("10 e 11/02/2026 – INDISPONIBILIDADE DO EPROC")
        assert "indisponibilidade do eproc" in chave
        assert not chave.startswith("10")

    def test_titulo_sem_prefixo_inalterado(self):
        chave = normalizar_titulo_chave("TJTO comunica indisponibilidade do eproc neste sabado")
        assert chave.startswith("tjto comunica")

    def test_remove_acentos_e_lowercase(self):
        chave = normalizar_titulo_chave("Indisponibilidade no PJé afetou Advogados")
        assert chave == normalizar_titulo_chave("indisponibilidade no pje afetou advogados")

    def test_trunca_em_80_chars(self):
        titulo_longo = "A" * 200
        chave = normalizar_titulo_chave(titulo_longo)
        assert len(chave) <= 80

    def test_titulo_curto_retorna_vazio(self):
        # Menos de 20 chars → não gera chave (evita falsos positivos)
        assert normalizar_titulo_chave("Login") == ""
        assert normalizar_titulo_chave("Home") == ""

    def test_rss_e_direto_geram_mesma_chave(self):
        """Versão RSS (com sufixo da fonte) e versão direta devem ter a mesma chave."""
        titulo_direto = "TJTO comunica indisponibilidade do eproc para atualizacao da infraestrutura de seguranca neste sabado"
        titulo_rss    = titulo_direto + " - Tribunal de Justiça do Tocantins"
        # A chave usa os primeiros 80 chars; os dois compartilham o mesmo prefixo
        assert normalizar_titulo_chave(titulo_direto)[:60] == normalizar_titulo_chave(titulo_rss)[:60]

    def test_datas_diferentes_geram_chaves_diferentes(self):
        """Comunicações com mesma base mas datas distintas → chaves diferentes."""
        t1 = "24/03/2026 – PORTAL DE CUSTAS - INDISPONIBILIDADE DOS SERVIÇOS"
        t2 = "01/04/2026 – PORTAL DE CUSTAS - INDISPONIBILIDADE DOS SERVIÇOS"
        # Após remoção do prefixo de data, ambas ficam iguais — comportamento esperado,
        # pois a dedup por janela de tempo (3 dias) garante que eventos antigos expirem.
        # Este teste documenta o comportamento atual, não que seja um problema.
        assert normalizar_titulo_chave(t1) == normalizar_titulo_chave(t2)


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
