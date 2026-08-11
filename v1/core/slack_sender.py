"""
core/slack_sender.py
Envio de alertas classificados pela IA para o Slack via Incoming Webhook.

Espera a variável de ambiente SLACK_WEBHOOK_URL configurada no repositório
(GitHub Secrets → Actions → SLACK_WEBHOOK_URL).

Cada item da lista deve ser um dict com as chaves:
    id, origem, tribunal_fonte, data_publicacao, titulo,
    descricao, url, url_fonte, classificacao, justificativa
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any

import requests

log = logging.getLogger(__name__)

_TIMEOUT = 15  # segundos


# ── Helpers ──────────────────────────────────────────────────────────────────

def _limpar_texto(texto: Any) -> str:
    s = (
        str(texto or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return re.sub(r"\s+", " ", s).strip()


def _resumir_texto(texto: Any, limite: int) -> str:
    limpo = re.sub(r"\s+", " ", str(texto or "")).strip()
    if len(limpo) <= limite:
        return limpo
    return limpo[: limite - 3].rstrip() + "..."


def _rotulo_origem(origem: Any) -> str:
    s = str(origem or "").strip().lower()
    if s in ("noticias", "notícias"):
        return "Notícias"
    if s == "clipping":
        return "Diário Oficial"
    if s in ("script_git", "rss"):
        return "RSS"
    return str(origem or "Fonte")


def _rotulo_link(origem: Any) -> str:
    if str(origem or "").strip().lower() == "clipping":
        return "Abrir publicação"
    return "Abrir notícia"


def _acao_sugerida(classificacao: str) -> str:
    if classificacao == "RELEVANTE":
        return "validar possível impacto em crawler/credenciais."
    if classificacao == "TALVEZ":
        return "acompanhar próximos atos/publicações sobre o tema."
    return ""


def _montar_link(url: Any, texto: str) -> str:
    limpo = str(url or "").strip()
    if not limpo:
        return "Sem link disponível"
    return f"<{limpo}|{texto}>"


# ── Montagem da mensagem ──────────────────────────────────────────────────────

def _build_message(itens: list[dict]) -> str:
    hoje = datetime.now().strftime("%d/%m/%Y")

    relevantes = sum(1 for i in itens if i.get("classificacao") == "RELEVANTE")
    talvez = sum(1 for i in itens if i.get("classificacao") == "TALVEZ")
    total = len(itens)

    texto = (
        f":jusbrasil: *Clipping de Tribunais: alertas identificados pela IA · {hoje}*\n"
        "Pessoal, seguem os itens classificados como *RELEVANTE* ou *TALVEZ* no monitoramento de hoje.\n\n"
        "*Itens*\n\n"
    )

    for item in itens:
        classificacao = item.get("classificacao", "")
        emoji = ":large_green_circle:" if classificacao == "RELEVANTE" else ":large_yellow_circle:"

        titulo = _limpar_texto(item.get("titulo", ""))
        fonte = _limpar_texto(item.get("tribunal_fonte") or "Fonte não identificada")
        origem = _rotulo_origem(item.get("origem"))
        descricao = _resumir_texto(item.get("descricao", ""), 450)
        justificativa = _resumir_texto(item.get("justificativa", ""), 300)
        acao = _acao_sugerida(classificacao)
        link = item.get("url") or item.get("url_fonte") or ""

        texto += (
            f"{emoji} *{titulo}*\n"
            f"{fonte} · {origem}\n"
            f"*O que diz:* {_limpar_texto(descricao)}\n"
            f"*Por que a IA sinalizou:* {_limpar_texto(justificativa)}\n"
            f"*Ação sugerida:* {acao}\n"
        )

        if link:
            texto += f"🔗 {_montar_link(link, _rotulo_link(item.get('origem')))}\n\n"
        else:
            texto += "🔗 Sem link disponível\n\n"

    texto += (
        "*Resumo*\n"
        f":large_green_circle: Relevantes: {relevantes}"
        f" · :large_yellow_circle: Talvez: {talvez}"
        f" · Total: {total}\n"
        "Itens enviados por indicarem possível mudança em sistema, acesso, autenticação, "
        "portal, consulta ou coleta. Itens IRRELEVANTE não foram encaminhados."
    )

    return texto


# ── Envio ao Slack ────────────────────────────────────────────────────────────

def _send_webhook(texto: str) -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise EnvironmentError("SLACK_WEBHOOK_URL não configurada nos secrets do repositório.")

    resp = requests.post(
        webhook_url,
        json={"text": texto},
        timeout=_TIMEOUT,
    )

    if resp.status_code < 200 or resp.status_code >= 300 or resp.text != "ok":
        raise RuntimeError(
            f"Erro ao enviar para Slack. Status: {resp.status_code} | Resposta: {resp.text!r}"
        )


# ── Ponto de entrada público ──────────────────────────────────────────────────

def send_alerts(itens: list[dict]) -> None:
    """Envia para o Slack todos os itens RELEVANTE/TALVEZ da lista.

    Filtra itens sem justificativa antes de montar a mensagem.
    Raises RuntimeError se o webhook falhar.
    """
    candidatos = [
        i for i in itens
        if i.get("classificacao", "").upper() in ("RELEVANTE", "TALVEZ")
        and str(i.get("justificativa") or "").strip()
    ]

    if not candidatos:
        log.info("Nenhum alerta RELEVANTE/TALVEZ com justificativa para enviar ao Slack.")
        return

    mensagem = _build_message(candidatos)
    _send_webhook(mensagem)
    log.info("Alertas enviados ao Slack: %d item(s).", len(candidatos))
