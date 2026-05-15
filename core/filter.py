# core/filter.py
import re
import unicodedata

# Padrão de prefixo de data — compilado uma vez no carregamento do módulo.
# Cobre formatos: "15/04/2026 – ", "10 e 11/02/2026 - ", "3 e 4/5/2026 — "
_RE_PREFIXO_DATA = re.compile(r'^[\d\s/eEaA]+[-–—]+\s*')
from config.settings import (
    TERMOS_BLOQUEADOS, TERMOS_FORTES_TI,
    TERMOS_COMPOSTOS, TERMOS_ESPECIFICOS, TERMOS_IMUNES,
)

# ──────────────────────────────────────────────────────────────────────────────
# Pré-compilação dos padrões regex no carregamento do módulo.
# Antes: ~150 re.compile() a cada notícia avaliada.
# Agora: compilação única na inicialização; avaliação usa apenas .search().
# ──────────────────────────────────────────────────────────────────────────────

def _limpar(termo: str) -> str:
    """Remove acentos e converte para minúsculas (usado só na inicialização)."""
    nfkd = unicodedata.normalize('NFKD', termo)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _compilar(termo_limpo: str, sufixo: str = r'(s|es)?') -> re.Pattern:
    return re.compile(r'\b' + re.escape(termo_limpo) + sufixo + r'\b')


# (padrão, termo_original)
_IMUNES: list[tuple[re.Pattern, str]] = [
    (_compilar(_limpar(t)), t)
    for t in TERMOS_IMUNES
]

# (padrão, termo_original)
_BLOQUEADOS: list[tuple[re.Pattern, str]] = [
    (_compilar(_limpar(t), r'(s)?'), t)
    for t in TERMOS_BLOQUEADOS
]

# (padrão, termo_limpo_display, termo_display_com_tipo)
_ESPECIFICOS: list[tuple[re.Pattern, str, str]] = [
    (
        _compilar(_limpar(t.replace('"', ''))),
        t.replace('"', ''),
        t.replace('"', '') + ' (Específico)',
    )
    for t in TERMOS_ESPECIFICOS
]

# (padrão, termo_original, termo_display_com_tipo)
_FORTES: list[tuple[re.Pattern, str, str]] = [
    (_compilar(_limpar(t)), t, t + ' (Forte)')
    for t in TERMOS_FORTES_TI
]

# (padrão1, padrão2, termo1, termo2)
_COMPOSTOS: list[tuple[re.Pattern, re.Pattern, str, str]] = [
    (_compilar(_limpar(par[0])), _compilar(_limpar(par[1])), par[0], par[1])
    for par in TERMOS_COMPOSTOS
]

# Padrão de arquivo — compilado uma vez
_ARQUIVO = re.compile(r'\.(pdf|doc|docx|xls|xlsx)(\s*-|$)')


# ──────────────────────────────────────────────────────────────────────────────
# Funções de avaliação (usam apenas os padrões pré-compilados acima)
# ──────────────────────────────────────────────────────────────────────────────

def normalizar_titulo_chave(titulo: str) -> str:
    """
    Gera uma chave normalizada do título para deduplicação por conteúdo.

    Usada em dois contextos:
      1. Intra-run  : main.py deduplica notícias da mesma execução que chegam
                     via URL diferente (RSS vs Scraper Direto).
      2. Cross-run  : database.py persiste a chave para bloquear o mesmo
                     conteúdo que reaparece via URL diferente em rodadas futuras.

    Estratégia:
      - Remove prefixo de data ("15/04/2026 – ") que o Google News omite nos
        títulos dos scrapers diretos.
      - Remove acentos e converte para minúsculas.
      - Trunca em 80 chars — suficiente para identificar o evento, curto o
        bastante para ignorar o sufixo "- Nome da Fonte" do RSS.
      - Retorna '' para títulos com menos de 20 chars (evita falsos positivos
        em títulos muito curtos como "Login" ou "Home").
    """
    t = _RE_PREFIXO_DATA.sub('', titulo).strip()
    t = remover_acentos(t.lower())
    return t[:80] if len(t) >= 20 else ""


def remover_acentos(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def titulo_tem_imunidade(titulo_limpo: str) -> tuple[bool, str | None]:
    """Retorna (True, termo) se o título contiver um termo imune."""
    for padrao, termo in _IMUNES:
        if padrao.search(titulo_limpo):
            return True, termo
    return False, None


def texto_tem_bloqueio(texto_limpo: str) -> tuple[bool, str | None, str | None]:
    for padrao, termo in _BLOQUEADOS:
        match = padrao.search(texto_limpo)
        if match:
            return True, match.group(0), termo
    return False, None, None


def texto_tem_alerta(texto_limpo: str) -> tuple[bool, str | None, str | None]:
    # 1. Termos específicos (prioridade máxima)
    for padrao, _, termo_display in _ESPECIFICOS:
        match = padrao.search(texto_limpo)
        if match:
            return True, match.group(0), termo_display

    # 2. Termos fortes
    for padrao, _, termo_display in _FORTES:
        match = padrao.search(texto_limpo)
        if match:
            return True, match.group(0), termo_display

    # 3. Termos compostos (ambas as palavras devem estar presentes)
    for padrao1, padrao2, t1, t2 in _COMPOSTOS:
        match1 = padrao1.search(texto_limpo)
        match2 = padrao2.search(texto_limpo)
        if match1 and match2:
            return True, f"{match1.group(0)} + {match2.group(0)}", f"{t1} + {t2} (Composto)"

    return False, None, None


def avaliar_noticia(titulo: str, resumo: str) -> tuple[str, str, str, str]:
    """
    Retorna 4 itens: (STATUS, MOTIVO, PALAVRA_EXTRAIDA, TERMO_BASE)

    Ordem de avaliação:
      1. Imunidade no Título  → se tem termo imune, pula bloqueio e vai direto ao alerta
      2. Bloqueio no Título   → descarta se blacklist bater (sem imunidade)
      3. Alerta no Título     → aprova se termo de TI bater
      4. Bloqueio no Resumo  → descarta se blacklist bater
      5. Alerta no Resumo    → aprova se termo de TI bater
      6. Arquivo              → descarta títulos que são nomes de arquivo
      7. Irrelevante          → sem termos de TI
    """
    titulo_puro = titulo.rsplit(' - ', 1)[0]
    titulo_formatado = remover_acentos(titulo_puro.lower())
    resumo_formatado = remover_acentos(resumo.lower()) if resumo else ""

    # 1. Imunidade no Título
    imune, termo_imune = titulo_tem_imunidade(titulo_formatado)
    if imune:
        tem_alerta, palavra, termo = texto_tem_alerta(titulo_formatado)
        if tem_alerta:
            return 'novo', f'Aprovado - Imune por "{termo_imune}" (Título)', palavra, termo

    # 2. Bloqueio no Título
    tem_bloqueio, palavra, termo = texto_tem_bloqueio(titulo_formatado)
    if tem_bloqueio:
        return 'bloqueado', 'Blacklist (Título)', palavra, termo

    # 3. Alerta no Título
    tem_alerta, palavra, termo = texto_tem_alerta(titulo_formatado)
    if tem_alerta:
        return 'novo', 'Aprovado (Título)', palavra, termo

    # 4. Bloqueio no Resumo
    tem_bloqueio, palavra, termo = texto_tem_bloqueio(resumo_formatado)
    if tem_bloqueio:
        return 'bloqueado', 'Blacklist (Resumo)', palavra, termo

    # 5. Alerta no Resumo
    tem_alerta, palavra, termo = texto_tem_alerta(resumo_formatado)
    if tem_alerta:
        return 'novo', 'Aprovado (Resumo)', palavra, termo

    # 6. Rejeita títulos que são nomes de arquivos
    if _ARQUIVO.search(titulo.lower()):
        return 'irrelevante', 'Arquivo (não é notícia)', 'N/A', 'N/A'

    return 'irrelevante', 'Sem Termos TI', 'N/A', 'N/A'
