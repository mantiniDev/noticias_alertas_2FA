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
    """Verifica alertas e retorna: (Boolean, palavra_extraida, termo_base)"""
    # 1. Filtro Exato
    for termo in TERMOS_FORTES_TI:
        termo_limpo = remover_acentos(termo.lower())
        padrao = r'\b' + re.escape(termo_limpo) + r'(s|es)?\b'
        match = re.search(padrao, texto_limpo)
        if match:
            # Retorna: True, a palavra exata que estava no texto, a palavra base da nossa lista
            return True, match.group(0), termo
            
    # 2. Filtro Composto
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
            return True, palavra_ext, termo_bs
            
    return False, None, None

def avaliar_noticia(titulo, resumo):
    """Avalia título e resumo e retorna: (Boolean, palavra_extraida, termo_base)"""
    titulo_puro = titulo.rsplit(' - ', 1)[0]
    titulo_formatado = remover_acentos(titulo_puro.lower())
    resumo_formatado = remover_acentos(resumo.lower()) if resumo else ""

    # REGRA 1: Título é soberano
    has_alerta, palavra, termo = texto_tem_alerta(titulo_formatado)
    if has_alerta and not texto_tem_bloqueio(titulo_formatado):
        return True, palavra, termo
        
    # REGRA 2: Olha para o Resumo
    has_alerta_res, palavra_res, termo_res = texto_tem_alerta(resumo_formatado)
    if has_alerta_res and not texto_tem_bloqueio(resumo_formatado):
        if not texto_tem_bloqueio(titulo_formatado):
            return True, palavra_res, termo_res

    return False, None, None