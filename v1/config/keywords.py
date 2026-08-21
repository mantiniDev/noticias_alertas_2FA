"""
Termos de filtragem para consultas BigQuery e classificação de relevância.

TIER_A_TERMS: lista de padrões regex (compatível com RE2/BigQuery REGEXP_CONTAINS)
usados para filtrar publicações de diários oficiais e notícias de tribunais.
Deve manter paridade exata com o array TIER_A_TERMS do Keywords.gs no Apps Script.
"""

# ── Limites de consulta BQ ────────────────────────────────────────────────────

MAX_POR_SIGLA: int = 200   # máximo de registros por sigla por consulta
LIMITE_LINHAS: int = 3000  # limite total de linhas retornadas por tabela

# ── Siglas monitoradas ────────────────────────────────────────────────────────

SIGLAS_MONITORADAS: list[str] = [
    # Tribunais superiores federais
    "STF", "STJ", "TST", "TSE", "STM", "CJF", "CNJ", "CNMP",
    # Tribunais de Justiça Estaduais (27)
    "TJAC", "TJAL", "TJAP", "TJAM", "TJBA", "TJCE", "TJDFT",
    "TJES", "TJGO", "TJMA", "TJMT", "TJMS", "TJPA", "TJPB",
    "TJPE", "TJPI", "TJPR", "TJRJ", "TJRN", "TJRO", "TJRR",
    "TJRS", "TJSC", "TJSE", "TJSP", "TJTO", "TJMG",
    # Tribunais Regionais Federais
    "TRF1", "TRF2", "TRF3", "TRF4", "TRF5", "TRF6",
    # Tribunais Regionais do Trabalho
    "TRT1", "TRT2", "TRT3", "TRT4", "TRT5", "TRT6",
    "TRT7", "TRT8", "TRT9", "TRT10", "TRT11", "TRT12",
    "TRT13", "TRT14", "TRT15", "TRT16", "TRT17", "TRT18",
    "TRT19", "TRT20", "TRT21", "TRT22", "TRT23", "TRT24",
]

# ── Cadernos do Diário Oficial a excluir ─────────────────────────────────────

CADERNOS_EXCLUIR: list[str] = [
    # Seções administrativas sem impacto em sistemas/acesso
    "Pessoal",
    "Atos de Pessoal",
    "Movimentação de Pessoal",
    "Editais",
    "Licitações",
    "Licitacoes",
    "Avisos de Licitação",
    "Avisos de Licitacao",
    "Convênios",
    "Convenios",
    "Concursos Públicos",
    "Concursos Publicos",
    "Resultado de Concurso",
]

# ── Termos de filtragem TIER A ────────────────────────────────────────────────

TIER_A_TERMS: list[str] = [
    # Sistemas judiciais específicos
    "pjeoffice",
    "pje office",
    r"\beproc\b",
    "e-proc",
    r"\besaj\b",
    "e-saj",
    "saj digital",
    "sajdigital",
    r"\bpdpj-br\b",
    r"\bpdpj\b",
    "tucujuris",
    "themis judicial",
    "creta judicial",

    # Migrações e trocas de sistema
    "migracao para eproc",
    "migracao para o eproc",
    "migracao para pje",
    "migracao para o pje",
    "migracao para projudi",
    "migracao para esaj",
    "migracao de sistema processual",
    "migracao processual",
    "migracao dos processos",
    "troca de sistema",
    "transicao de sistema",
    "virada de chave",
    "desativacao do sistema",
    "descontinuacao do sistema",
    "implantacao do eproc",
    "implantacao do pje",
    "implantacao do projudi",
    "implantacao do pdpj",
    "implantacao piloto",
    "entrada em producao",

    # Autenticação forte
    "autenticacao em dois fatores",
    "autenticacao de dois fatores",
    "duplo fator de autenticacao",
    "segundo fator de autenticacao",
    "segundo fator obrigatorio",
    "verificacao em duas etapas",
    "autenticacao multifator",
    "autenticacao multifatorial",
    "2fa obrigatorio",
    "mfa obrigatorio",
    "habilitacao de segundo fator",
    "ativacao de segundo fator",
    "obrigatoriedade do segundo fator",
    "google authenticator",
    "microsoft authenticator",
    "aplicativo authenticator",
    "aplicativo autenticador",

    # Gov.br
    "login gov.br obrigatorio",
    "acesso gov.br obrigatorio",
    "conta gov.br obrigatoria",
    "selo prata obrigatorio",
    "selo ouro obrigatorio",
    "nivel prata obrigatorio",
    "nivel ouro obrigatorio",

    # Restrições de acesso
    "bloqueio de acesso externo",
    "restricao de acesso automatizado",
    "acesso automatizado vedado",
    "coleta automatizada",
    "consulta automatizada",
    "consulta robotizada",
    "bloqueio de crawlers",
    "bloqueio de robos",
    "captcha obrigatorio",
    "recaptcha",
    "bloqueio por ip",
    "whitelist de ip",
    "lista de ips autorizados",

    # Segurança e incidentes graves
    "ransomware",
    "incidente de seguranca",
    "ciberataque",
    "ataque cibernetico",
    "ataque hacker",
    "vazamento de dados",
    "violacao de dados",
    "zero trust",
    "patch de seguranca",

    # Sistemas centralizados do CNJ
    "domicilio judicial eletronico",
    "domicilio eletronico do judiciario",
    "obrigatoriedade.*djen",
    "implantacao.*djen",
    "adesao.*djen",
    "balcao virtual",
    "sistema codex",
    "plataforma codex",
    "codex.*cnj",
    r"\bdatajud\b",
    "base nacional de dados processuais",
    "sistema seeu",
    "implantacao.*seeu",
    "execucao penal eletronica",
    r"portal jus\.br",
    r"plataforma jus\.br",
    "plataforma digital do poder judiciario",
    "juizo 100% digital",
    "juizo 100 digital",

    # SSO / federação de identidade
    "single sign-on",
    "single sign on",
    "federacao de identidade",
    "identidade digital do judiciario",

    # Resoluções/portarias compostas
    r"resolucao.*\beproc\b",
    r"resolucao.*\bpje\b",
    "resolucao.*projudi",
    r"resolucao.*\besaj\b",
    "portaria.*migracao",
    "portaria conjunta.*sistema",
    "aviso conjunto.*sistema",
    "ato conjunto.*sistema",
    "instrucao normativa.*sistema",

    # Licitações de TI estratégicas
    "solucao de autenticacao",
    "solucao de duplo fator",
    "solucao de mfa",
    "solucao de 2fa",
    "firewall de aplicacao",
    "web application firewall",
    "firewall de perimetro",
    "balanceador de carga",
    "servico gerenciado de seguranca",
    "pregao eletronico.*sistema",
    "pregao eletronico.*seguranca",
    "pregao eletronico.*firewall",
    "pregao eletronico.*autenticacao",
]
