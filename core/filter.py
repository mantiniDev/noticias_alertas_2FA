# core/filter.py
import re
import unicodedata
from config.settings import TERMOS_BLOQUEADOS, TERMOS_FORTES_TI, TERMOS_COMPOSTOS, TERMOS_ESPECIFICOS

def remover_acentos(texto):
    if not texto: return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    return u"".join([c for c in nfkd if not unicodedata.combining(c)])

def texto_tem_bloqueio(texto_limpo):
    for termo in TERMOS_BLOQUEADOS:
        termo_limpo = remover_acentos(termo.lower())
        match = re.search(r'\b' + re.escape(termo_limpo) + r'(s)?\b', texto_limpo)
        if match:
            # Retorna True, a palavra exata que bloqueou, e a palavra original da Blacklist
            return True, match.group(0), termo 
    return False, None, None

def texto_tem_alerta(texto_limpo):
    # 1. Filtro de Termos Específicos (Prioridade Máxima)
    for termo in TERMOS_ESPECIFICOS:
        # Removemos as aspas duplas da string para bater com o texto limpo da notícia
        termo_limpo = remover_acentos(termo.replace('"', '').lower())
        padrao = r'\b' + re.escape(termo_limpo) + r'(s|es)?\b'
        match = re.search(padrao, texto_limpo)
        if match:
            return True, match.group(0), termo.replace('"', '') + " (Específico)"

    # 2. Filtro de Termos Fortes
    for termo in TERMOS_FORTES_TI:
        termo_limpo = remover_acentos(termo.lower())
        padrao = r'\b' + re.escape(termo_limpo) + r'(s|es)?\b'
        match = re.search(padrao, texto_limpo)
        if match:
            return True, match.group(0), termo + " (Forte)"
            
    # 3. Filtro de Termos Compostos
    for par in TERMOS_COMPOSTOS:
        p1 = remover_acentos(par[0].lower())
        p2 = remover_acentos(par[1].lower())
        padrao1 = r'\b' + re.escape(p1) + r'(s|es)?\b'
        padrao2 = r'\b' + re.escape(p2) + r'(s|es)?\b'
        match1 = re.search(padrao1, texto_limpo)
        match2 = re.search(padrao2, texto_limpo)
        
        if match1 and match2:
            palavra_ext = f"{match1.group(0)} + {match2.group(0)}"
            termo_bs = f"{par[0]} + {par[1]}"
            return True, palavra_ext, termo_bs + " (Composto)"
            
    return False, None, None

def avaliar_noticia(titulo, resumo):
    """
    Retorna 4 itens: (STATUS, MOTIVO, PALAVRA_EXTRAIDA, TERMO_BASE)
    """
    titulo_puro = titulo.rsplit(' - ', 1)[0]
    titulo_formatado = remover_acentos(titulo_puro.lower())
    resumo_formatado = remover_acentos(resumo.lower()) if resumo else ""

    # 1. Bloqueio no Título
    tem_bloqueio_tit, palavra_bloq_tit, termo_bloq_tit = texto_tem_bloqueio(titulo_formatado)
    if tem_bloqueio_tit:
        return 'bloqueado', 'Blacklist (Título)', palavra_bloq_tit, termo_bloq_tit

    # 2. Alerta no Título
    tem_alerta_tit, palavra_tit, termo_tit = texto_tem_alerta(titulo_formatado)
    if tem_alerta_tit:
        return 'novo', 'Aprovado (Título)', palavra_tit, termo_tit

    # 3. Bloqueio no Resumo
    tem_bloqueio_res, palavra_bloq_res, termo_bloq_res = texto_tem_bloqueio(resumo_formatado)
    if tem_bloqueio_res:
        return 'bloqueado', 'Blacklist (Resumo)', palavra_bloq_res, termo_bloq_res

    # 4. Alerta no Resumo
    tem_alerta_res, palavra_res, termo_res = texto_tem_alerta(resumo_formatado)
    if tem_alerta_res:
        return 'novo', 'Aprovado (Resumo)', palavra_res, termo_res
    
    # 5. Rejeita titulos que são nomes de arquivos
    if re.search(r'\.(pdf|doc|docx|xls|xlsx)(\s*-|$)', titulo.lower()):
        return 'irrelevante', 'Arquivo (não é notícia)', 'N/A', 'N/A'

    return 'irrelevante', 'Sem Termos TI', 'N/A', 'N/A'