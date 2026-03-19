# core/notifier.py
import smtplib
import os
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config.settings import TRIBUNAIS
from email.mime.base import MIMEBase
from email import encoders

def gerar_corpos_email(noticias):
    hoje = datetime.now().strftime("%d/%m/%Y")
    uma_semana_atras = (datetime.now() - timedelta(days=2)).strftime("%d/%m/%Y")

    texto_puro = f"MAST - Monitoramento Automatizado de Sistemas e Tribunais ({uma_semana_atras} a {hoje})\n\n"

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #2c3e50;">Monitoramento Automatizado de Sistemas e Tribunais (MAST)</h2>
        <p>Período: <strong>{uma_semana_atras}</strong> até <strong>{hoje} às 8H.</strong></p>
        <hr style="border: 1px solid #eee;">
    """

    if not noticias:
        msg_vazia = "Nenhuma notícia 100% relevante de TI/Sistemas encontrada nos últimos 2 dias."
        texto_puro += msg_vazia + "\n"
        html += f"<p>{msg_vazia}</p>"
    else:
        html += "<ul style='list-style-type: none; padding: 0;'>"
        for i, noticia in enumerate(noticias, 1):
            data_formatada = noticia['data_obj'].strftime("%d/%m/%Y às %H:%M")
            titulo_lower = noticia['titulo'].lower()

            link_oficial_html = ""
            for tribunal in TRIBUNAIS:
                if tribunal['acronym'].lower() in titulo_lower:
                    link_oficial_html = f"<br><a href='{tribunal['url']}' style='display: inline-block; margin-top: 8px; padding: 5px 10px; background-color: #e8f4f8; color: #2980b9; text-decoration: none; border-radius: 4px; font-size: 0.85em;'></a>"
                    break

            texto_puro += f"{i}. {noticia['titulo']}\n   Data: {data_formatada}\n   Link da Notícia: {noticia['link']}\n\n"

            html += f"""
            <li style="margin-bottom: 20px; padding: 15px; border-left: 4px solid #3498db; background-color: #f9f9f9;">
                <h3 style="margin: 0 0 10px 0;">
                    <a href="{noticia['link']}" style="color: #2c3e50; text-decoration: none;">{noticia['titulo']}</a>
                </h3>
                <p style="margin: 0; font-size: 0.9em; color: #7f8c8d;">
                    📅 {data_formatada} &nbsp;|&nbsp; 📰 Fonte: {noticia['fonte']}
                </p>
                {link_oficial_html}
            </li>
            """
        html += "</ul>"

    rodape = "\n---\nEste é um e-mail automático gerado pelo MAST."
    texto_puro += rodape
    html += f"""
        <hr style="border: 1px solid #eee;">
        <p style="font-size: 0.8em; color: #95a5a6;">Este é um e-mail automático gerado pelo MAST.</p>
      </body>
    </html>
    """
    return texto_puro, html

def enviar_email(texto_puro, html, total_noticias, anexo_pdf=None):
    remetente = os.environ.get('EMAIL_REMETENTE')
    senha = os.environ.get('EMAIL_SENHA')
    destinatario = os.environ.get('EMAIL_DESTINATARIO')

    if not remetente or not senha:
        print("Erro: Credenciais não configuradas no GitHub Secrets.")
        return

    msg = MIMEMultipart('alternative')
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = f"Monitoramento Automatizado de Sistemas e Tribunais - {datetime.now().strftime('%d/%m/%Y')} ({total_noticias} alertas)"

    msg.attach(MIMEText(texto_puro, 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    # --- LÓGICA DO ANEXO PDF ---
    if anexo_pdf and os.path.exists(anexo_pdf):
        with open(anexo_pdf, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        
        # Codifica em Base64 para poder trafegar pela internet
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= Relatorio_MAST_Consultas.pdf",
        )
        msg.attach(part)
    # ----------------------------

    try:
        print("Conectando ao servidor SMTP...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        print(f"📧 E-mail HTML enviado com sucesso (com anexo)! ({total_noticias} alertas)")
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail: {e}")