# core/pdf_generator.py
import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime

def gerar_pdf_relatorio(dados):
    """Gera um PDF formatado com os dados históricos do banco e retorna o caminho do arquivo."""
    
    # O PDF será salvo temporariamente na raiz do projeto
    caminho_pdf = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Relatorio_MAST.pdf'))
    
    doc = SimpleDocTemplate(caminho_pdf, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Estilo do Título
    title_style = styles['Heading1']
    title_style.alignment = 1 # Centralizado
    title_style.spaceAfter = 20
    
    # Estilo do Texto Padrão
    normal_style = styles['Normal']
    normal_style.fontSize = 10
    normal_style.spaceAfter = 12

    story = []
    
    hoje = datetime.now().strftime("%d/%m/%Y às %H:%M")
    story.append(Paragraph(f"Relatório Monitoramento Automatizado de Sistemas e Tribunais", title_style))
    story.append(Paragraph(f"<b>Extração do Banco de Dados</b> - Gerado em: {hoje}", normal_style))
    story.append(Spacer(1, 20))
    
    if not dados:
        story.append(Paragraph("Nenhum dado registrado no banco de dados.", normal_style))
    else:
        for row in dados:
            data, fonte, palavra, termo, titulo, link = row
            
            # Monta o bloco de texto para cada notícia
            texto = f"<b>Data:</b> {data} <br/>" \
                    f"<b>Fonte:</b> {fonte} <br/>" \
                    f"<b>Gatilho / Palavra:</b> {termo} -> <i>{palavra}</i> <br/>" \
                    f"<b>Título:</b> {titulo} <br/>" \
                    f"<b>Link:</b> <a href='{link}' color='blue'>Clique aqui para acessar</a>"
                    
            story.append(Paragraph(texto, normal_style))
            story.append(Spacer(1, 10))

    # Constrói o PDF fisicamente
    doc.build(story)
    print(f"📄 PDF Gerado com sucesso: {caminho_pdf}")
    return caminho_pdf