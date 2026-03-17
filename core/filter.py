# core/filter.py
import re
import unicodedata
from config.settings import TERMOS_BLOQUEADOS, TERMOS_FORTES_TI, TERMOS_COMPOSTOS

def remover_acentos(texto):
    if not texto: return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    return u"".join([c for c in nfkd if not unicodedata.combining(c)])

def texto_tem_bloqueio(texto_limpo):
    for termo in TERMOS_BLOQUEADOS:
        termo_limpo = remover_acentos(termo.lower())
        if re.search(r'\b' + re.escape(termo_limpo) + r'(s)?\b', texto_limpo):
            return True
    return False

def texto_tem_alerta(texto_limpo):
    for termo in TERMOS_FORTES_TI:
        termo_limpo = remover_acentos(termo.lower())
        padrao = r'\b' + re.escape(termo_limpo) + r'(s|es)?\b'
        if re.search(padrao, texto_limpo):
            return True
            
    for par in TERMOS_COMPOSTOS:
        p1 = remover_acentos(par[0].lower())
        p2 = remover_acentos(par[1].lower())
        padrao1 = r'\b' + re.escape(p1) + r'(s|es)?\b'
        padrao2 = r'\b' + re.escape(p2) + r'(s|es)?\b'
        if re.search(padrao1, texto_limpo) and re.search(padrao2, texto_limpo):
            return True
            
    return False

def avaliar_noticia(titulo, resumo):
    titulo_puro = titulo.rsplit(' - ', 1)[0]
    titulo_formatado = remover_acentos(titulo_puro.lower())
    resumo_formatado = remover_acentos(resumo.lower()) if resumo else ""

    if texto_tem_alerta(titulo_formatado) and not texto_tem_bloqueio(titulo_formatado):
        return True
        
    if texto_tem_alerta(resumo_formatado) and not texto_tem_bloqueio(resumo_formatado):
        if not texto_tem_bloqueio(titulo_formatado):
            return True

    return False