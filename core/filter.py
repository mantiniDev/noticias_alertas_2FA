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
        match = re.search(r'\b' + re.escape(termo_limpo) + r'(s)?\b', texto_limpo)
        if match:
            return True, match.group(0) # Retorna True e a palavra que bloqueou
    return False, None

def texto_tem_alerta(texto_limpo):
    for termo in TERMOS_FORTES_TI:
        termo_limpo = remover_acentos(termo.lower())
        padrao = r'\b' + re.escape(termo_limpo) + r'(s|es)?\b'
        match = re.search(padrao, texto_limpo)
        if match:
            return True, match.group(0), termo
            
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
    """
    Avalia a notícia e retorna: (STATUS, palavra_extraida, motivo/termo_base)
    Status possíveis: 'novo', 'bloqueado', 'irrelevante'
    """
    titulo_puro = titulo.rsplit(' - ', 1)[0]
    titulo_formatado = remover_acentos(titulo_puro.lower())
    resumo_formatado = remover_acentos(resumo.lower()) if resumo else ""

    # 1. Verifica se há bloqueio logo no Título
    tem_bloqueio_tit, palavra_bloq_tit = texto_tem_bloqueio(titulo_formatado)
    if tem_bloqueio_tit:
        return 'bloqueado', palavra_bloq_tit, 'Blacklist (Título)'

    # 2. Verifica se é um Alerta de TI no Título
    tem_alerta_tit, palavra_tit, termo_tit = texto_tem_alerta(titulo_formatado)
    if tem_alerta_tit:
        return 'novo', palavra_tit, termo_tit

    # 3. Verifica se há bloqueio escondido no Resumo
    tem_bloqueio_res, palavra_bloq_res = texto_tem_bloqueio(resumo_formatado)
    if tem_bloqueio_res:
        return 'bloqueado', palavra_bloq_res, 'Blacklist (Resumo)'

    # 4. Verifica se o Alerta está no Resumo
    tem_alerta_res, palavra_res, termo_res = texto_tem_alerta(resumo_formatado)
    if tem_alerta_res:
        return 'novo', palavra_res, termo_res

    # Se não tem alerta e não tem bloqueio
    return 'irrelevante', 'N/A', 'Sem Termos TI'