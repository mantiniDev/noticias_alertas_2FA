# core/notifier.py
import logging
import smtplib
import os
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import encode_rfc2231
from config.settings import TRIBUNAIS, SMTP_TENTATIVAS

log = logging.getLogger(__name__)


_GRUPOS_LABEL = {
    "Sistemas-CNJ":         "Sistemas e CNJ",
    "Tribunais-Superiores": "Tribunais Superiores e Conselhos",
    "Tribunais-Estaduais":  "Tribunais de Justiça Estaduais",
    "TRFs":                 "Tribunais Regionais Federais",
    "TRTs":                 "Tribunais Regionais do Trabalho",
    "TREs":                 "Tribunais Regionais Eleitorais",
}

_GRUPOS_COR = {
    "Sistemas-CNJ":         "#8e44ad",
    "Tribunais-Superiores": "#c0392b",
    "Tribunais-Estaduais":  "#27ae60",
    "TRFs":                 "#d35400",
    "TRTs":                 "#16a085",
    "TREs":                 "#2980b9",
}


def gerar_corpos_email(
    noticias_por_grupo: dict[str, list],
) -> tuple[str, str]:
    """
    Gera o e-mail MAST unificado com todos os itens agrupados por categoria.

    Recebe um único dict {grupo: [itens]} contendo as três fases mescladas:
      • Fase 1 — RSS (tipo="Notícia")
      • Fase 2 — Scraper Direto (tipo="Indisponibilidade")
      • Fase 3 — Notícias Expandidas (tipo varia: "Notícias", "Normativos", …)

    Itens com tipo="Indisponibilidade" recebem borda vermelha e badge de alerta.
    Os demais itens recebem a cor do grupo ao qual pertencem.
    """
    hoje = datetime.now().strftime("%d/%m/%Y")
    duas_dias_atras = (datetime.now() - timedelta(days=2)).strftime("%d/%m/%Y")

    total = sum(len(v) for v in noticias_por_grupo.values())

    texto_puro = (
        f"MAST - Monitoramento Automatizado de Sistemas e Tribunais "
        f"({duas_dias_atras} a {hoje})\n\n"
    )

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #2c3e50;">Monitoramento Automatizado de Sistemas e Tribunais (MAST)</h2>
        <p>Período: <strong>{duas_dias_atras}</strong> até <strong>{hoje} às 8H.</strong></p>
        <hr style="border: 1px solid #eee;">
    """

    if total == 0:
        msg_vazia = "Nenhuma notícia relevante de TI/Sistemas encontrada nos últimos 2 dias."
        texto_puro += msg_vazia + "\n"
        html += f"""
        <p style="padding: 15px; background-color: #f9f9f9;
                  border-left: 4px solid #bdc3c7; color: #7f8c8d;">
            🔍 {msg_vazia}
        </p>
        """
    else:
        for grupo, label in _GRUPOS_LABEL.items():
            itens = noticias_por_grupo.get(grupo, [])
            if not itens:
                continue

            cor_grupo = _GRUPOS_COR.get(grupo, "#7f8c8d")
            texto_puro += f"\n[{label}]\n"
            html += f"""
        <h3 style="color: {cor_grupo}; margin: 20px 0 10px 0;
                   padding-bottom: 5px; border-bottom: 2px solid {cor_grupo};">
            {label}
        </h3>
        <ul style="list-style-type: none; padding: 0;">
            """

            for noticia in itens:
                data_fmt = noticia["data_obj"].strftime("%d/%m/%Y às %H:%M")
                tipo = noticia.get("tipo", "")
                is_alerta = tipo == "Indisponibilidade"

                # Borda: vermelho para alertas, cor do grupo para notícias
                cor_borda = "#e74c3c" if is_alerta else cor_grupo

                # Badge colorido
                if is_alerta:
                    badge_html = (
                        "<span style='background:#e74c3c; color:white; font-size:0.75em; "
                        "padding:2px 6px; border-radius:3px; margin-left:6px;'>"
                        "🔴 Indisponibilidade</span>"
                    )
                    badge_txt = "[Alerta]"
                elif tipo:
                    badge_html = (
                        f"<span style='background:{cor_grupo}; color:white; font-size:0.75em; "
                        f"padding:2px 6px; border-radius:3px; margin-left:6px;'>"
                        f"{tipo}</span>"
                    )
                    badge_txt = f"[{tipo}]"
                else:
                    badge_html = ""
                    badge_txt = ""

                # Link oficial de indisponibilidade (apenas para alertas cujo link
                # não aponta diretamente para um domínio .jus.br — evita duplicar
                # o link quando o Scraper Direto já extraiu a URL do próprio tribunal).
                link_oficial_html = ""
                if is_alerta:
                    noticia_link = noticia.get("link", "")
                    link_is_official = ".jus.br" in noticia_link
                    if not link_is_official:
                        titulo_lower = noticia["titulo"].lower()
                        for tribunal in TRIBUNAIS:
                            if tribunal["acronym"].lower() in titulo_lower:
                                link_oficial_html = (
                                    f"<br><a href='{tribunal['url']}' "
                                    f"style='display:inline-block; margin-top:8px; padding:5px 10px; "
                                    f"background-color:#fde8e8; color:#c0392b; "
                                    f"text-decoration:none; border-radius:4px; font-size:0.85em;'>"
                                    f"🔗 Portal de indisponibilidade — {tribunal['acronym']}</a>"
                                )
                                break

                texto_puro += (
                    f"  {badge_txt} {noticia['titulo']}\n"
                    f"    Data: {data_fmt} | Fonte: {noticia['fonte']}\n"
                    f"    Link: {noticia['link']}\n\n"
                )
                html += f"""
            <li style="margin-bottom: 14px; padding: 12px;
                        border-left: 4px solid {cor_borda}; background-color: #fafafa;">
                <div style="margin: 0 0 6px 0;">
                    <a href="{noticia['link']}"
                       style="color: #2c3e50; text-decoration: none; font-weight: 600;">
                        {noticia['titulo']}
                    </a>{badge_html}
                </div>
                <p style="margin: 0; font-size: 0.85em; color: #7f8c8d;">
                    📅 {data_fmt} &nbsp;|&nbsp; 📰 {noticia['fonte']}
                </p>{link_oficial_html}
            </li>
                """

            html += "</ul>"
            texto_puro += "\n"

    rodape = "\n---\nEste é um e-mail automático gerado pelo MAST."
    texto_puro += rodape
    html += """
        <hr style="border: 1px solid #eee;">
        <p style="font-size: 0.8em; color: #95a5a6;">
            Este é um e-mail automático gerado pelo MAST.
        </p>
      </body>
    </html>
    """
    return texto_puro, html


def _anexar_arquivo(msg: MIMEMultipart, caminho: str) -> None:
    """Anexa um arquivo ao MIMEMultipart com encoding RFC2231 para nomes acentuados."""
    with open(caminho, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    nome_arquivo = os.path.basename(caminho)
    part.add_header(
        "Content-Disposition",
        "attachment",
        filename=encode_rfc2231(nome_arquivo, charset='utf-8'),
    )
    msg.attach(part)


def enviar_email(
    texto_puro: str,
    html: str,
    total_noticias: int,
    anexo_path: str | None = None,
    pdf_path: str | None = None,
) -> None:
    remetente    = os.environ.get('EMAIL_REMETENTE')
    senha        = os.environ.get('EMAIL_SENHA')
    destinatario = os.environ.get('EMAIL_SLACK_DESTINATARIO')

    if not remetente:
        log.error("Variável EMAIL_REMETENTE não configurada nos GitHub Secrets.")
        return
    if not senha:
        log.error("Variável EMAIL_SENHA não configurada nos GitHub Secrets.")
        return
    if not destinatario:
        log.error("Variável EMAIL_SLACK_DESTINATARIO não configurada nos GitHub Secrets.")
        return

    if total_noticias == 0:
        assunto = f"MAST - Sem alertas relevantes em {datetime.now().strftime('%d/%m/%Y')}"
    else:
        assunto = f"MAST - {total_noticias} alerta(s) encontrado(s) em {datetime.now().strftime('%d/%m/%Y')}"

    msg = MIMEMultipart('alternative')
    msg['From']    = remetente
    msg['To']      = destinatario
    msg['Subject'] = assunto

    msg.attach(MIMEText(texto_puro, 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    if anexo_path and os.path.exists(anexo_path):
        _anexar_arquivo(msg, anexo_path)
        log.info("Anexo CSV adicionado: %s", os.path.basename(anexo_path))

    if pdf_path and os.path.exists(pdf_path):
        _anexar_arquivo(msg, pdf_path)
        log.info("Anexo PDF adicionado: %s", os.path.basename(pdf_path))

    # ── Envio com retry/backoff exponencial ───────────────────────────────
    for tentativa in range(1, SMTP_TENTATIVAS + 1):
        try:
            log.info("Conectando ao servidor SMTP (tentativa %d/%d)...", tentativa, SMTP_TENTATIVAS)
            server = smtplib.SMTP('smtp.gmail.com', 587, timeout=30)
            server.starttls()
            server.login(remetente, senha)
            server.send_message(msg)
            server.quit()
            log.info("📧 E-mail enviado com sucesso! (%d alertas)", total_noticias)
            return
        except Exception as exc:
            if tentativa == SMTP_TENTATIVAS:
                log.error("❌ Falha ao enviar e-mail após %d tentativas: %s", SMTP_TENTATIVAS, exc)
            else:
                espera = 2 ** tentativa
                log.warning("⚠️  Tentativa %d falhou (%s) — retentando em %ds...", tentativa, exc, espera)
                time.sleep(espera)
