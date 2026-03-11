import feedparser
import urllib.parse
from datetime import datetime, timedelta
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import re 

# ==============================================================================
# 1. CONSTANTES E CONFIGURAÇÕES DE BUSCA
# ==============================================================================

TRIBUNAIS = [
    # --- TRIBUNAIS SUPERIORES E FEDERAIS ---
    {"id": "1", "name": "Supremo Tribunal Federal", "acronym": "STF",
        "url": "https://portal.stf.jus.br/textos/verTexto.asp?servico=indispAplicacoes&pagina=principal"},
    {"id": "2", "name": "Superior Tribunal de Justiça", "acronym": "STJ",
        "url": "https://ri.web.stj.jus.br/registro-de-indisponibilidades/"},
    {"id": "3", "name": "Conselho Nacional de Justiça", "acronym": "CNJ",
        "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/justica-4-0/relatorios-de-indisponibilidade/"},
    {"id": "4", "name": "Tribunal Regional Federal da 1ª Região", "acronym": "TRF1",
        "url": "https://app.trf1.jus.br/indisponibilidades-relatorio/"},
    {"id": "5", "name": "Tribunal Regional Federal da 2ª Região",
        "acronym": "TRF2", "url": "https://www.trf2.jus.br/trf2/comunicacao"},
    {"id": "6", "name": "Tribunal Regional Federal da 3ª Região",
        "acronym": "TRF3", "url": "https://status.trf3.jus.br/"},
    {"id": "7", "name": "Tribunal Regional Federal da 4ª Região", "acronym": "TRF4",
        "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=aviso_listar"},
    {"id": "8", "name": "Tribunal Regional Federal da 5ª Região", "acronym": "TRF5",
        "url": "https://pje.trf5.jus.br/pje/IndisponibilidadeSistema/listView.seam?&Itemid=530"},
    {"id": "9", "name": "Tribunal Regional Federal da 6ª Região",
        "acronym": "TRF6", "url": "https://portal.trf6.jus.br/avisos/"},

    # --- TRIBUNAIS DE JUSTIÇA ESTADUAIS (27 TJs) ---
    {"id": "101", "name": "Tribunal de Justiça do Acre 1g", "acronym": "TJAC",
        "url": "https://www.tjac.jus.br/indisponibilidade/?tax=grau-1grau"},
    {"id": "102", "name": "Tribunal de Justiça de Acre 2G", "acronym": "TJAL",
        "url": "https://www.tjac.jus.br/indisponibilidade/?tax=grau-2grau"},
    {"id": "103", "name": "Tribunal de Justiça de Alagoas", "acronym": "TJAL",
        "url": "https://www.tjal.jus.br/indisponibilidades"},
    {"id": "104", "name": "Tribunal de Justiça do Amapá", "acronym": "TJAP",
        "url": "https://sig.tjap.jus.br/deintel_grid_vw_ocorrencias_ext/deintel_grid_vw_ocorrencias_ext.php"},
    {"id": "105", "name": "Tribunal de Justiça do Amazonas", "acronym": "TJAM",
        "url": "https://www.tjam.jus.br/index.php/certidoes-de-indisponibilidade"},
    {"id": "106", "name": "Tribunal de Justiça da Bahia", "acronym": "TJBA",
        "url": "https://www.tjba.jus.br/portal/aviso-indisponibilidade/"},
    {"id": "107", "name": "Tribunal de Justiça do Ceará", "acronym": "TJCE",
        "url": "https://www.tjce.jus.br/historico-de-indisponibilidade-portal-e-saj/"},
    {"id": "108", "name": "Tribunal de Justiça do Distrito Federal e Territórios",
        "acronym": "TJDFT", "url": "https://pje-indisponibilidade.tjdft.jus.br/"},
    {"id": "109", "name": "Tribunal de Justiça do Espírito Santo", "acronym": "TJES",
        "url": "https://www.tjes.jus.br/pje/consulta-indisponibilidade/"},
    {"id": "110", "name": "Tribunal de Justiça de Goiás", "acronym": "TJGO",
        "url": "https://www.tjgo.jus.br/index.php/agencia-de-noticias/noticias-ccse"},
    {"id": "111", "name": "Tribunal de Justiça do Maranhão", "acronym": "TJMA",
        "url": "https://www.tjma.jus.br/atos/tj/geral/0/120/o"},
    {"id": "112", "name": "Tribunal de Justiça do Mato Grosso",
        "acronym": "TJMT", "url": "https://www.tjmt.jus.br/noticias"},
    {"id": "113", "name": "Tribunal de Justiça do Mato Grosso do Sul",
        "acronym": "TJMS", "url": "https://www5.tjms.jus.br/monitoramentoEsaj/"},
    {"id": "114", "name": "Tribunal de Justiça de Minas Gerais", "acronym": "TJMG",
        "url": "https://www.tjmg.jus.br/pje/certidao-de-indisponibilidade/"},
    {"id": "115", "name": "Tribunal de Justiça de Minas GErais",
        "acronym": "TJMG", "url": "https://www.tjmg.jus.br/pje/atos-normativos/"},
    {"id": "116", "name": "Tribunal de Justiça do Pará", "acronym": "TJPA",
        "url": "https://www.tjpa.jus.br/PortalExterno/indexBibliotecaDigital.xhtml#resultados=&categoria=353&biblioteca=Documentos+Oficiais"},
    {"id": "117", "name": "Tribunal de Justiça da Paraíba 1G", "acronym": "TJPB",
        "url": "https://www.tjpb.jus.br/pje/monitoramento/indicador-de-indisponibilidade-do-pje-1o-grau"},
    {"id": "118", "name": "Tribunal de Justiça do Paraíba 2G", "acronym": "TJPR",
        "url": "https://www.tjpb.jus.br/pje/monitoramento/indicador-de-indisponibilidade-do-pje-2o-grau-e-turmas-recursais"},
    {"id": "119", "name": "Tribunal de Justiça do Paraná", "acronym": "TJPR",
        "url": "https://www.tjpr.jus.br/home/-/asset_publisher/A2gt/content/id/5924367#5924367"},
    {"id": "120", "name": "Tribunal de Justiça de Pernambuco", "acronym": "TJPE",
        "url": "https://www.tjpe.jus.br/pje/indisponibilidade-do-pje"},
    {"id": "121", "name": "Tribunal de Justiça do Piauí", "acronym": "TJPI",
        "url": "https://www.tjpi.jus.br/portaltjpi/pje/indisponibilidade-do-sistema/"},
    {"id": "122", "name": "Tribunal de Justiça do Rio de Janeiro", "acronym": "TJRJ",
        "url": "https://www3.tjrj.jus.br/portalservicos/#/modindpub-principal"},
    {"id": "123", "name": "Tribunal de Justiça do Rio Grande do Norte",
        "acronym": "TJRN", "url": "https://www.tjrn.jus.br/noticias/"},
    {"id": "124", "name": "Tribunal de Justiça do Rio Grande do Sul", "acronym": "TJRS",
        "url": "https://www.tjrs.jus.br/novo/processos-e-servicos/consultas-processuais/certidoes-indisponibilidade/"},
    {"id": "125", "name": "Tribunal de Justiça de Rondônia",
        "acronym": "TJRO", "url": "https://www.tjro.jus.br/sci/evento"},
    {"id": "126", "name": "Tribunal de Justiça de Roraima", "acronym": "TJRR",
        "url": "https://projudi.tjrr.jus.br/projudi/indisponibilidades.jsp"},
    {"id": "127", "name": "Tribunal de Justiça de Santa Catarina", "acronym": "TJSC",
        "url": "https://eproc1g.tjsc.jus.br/eproc/externo_controlador.php?acao=processo_disponibilidade_listagem"},
    {"id": "128", "name": "Tribunal de Justiça de São Paulo", "acronym": "TJSP",
        "url": "https://www.tjsp.jus.br/Indisponibilidade/Comunicados"},
    {"id": "129", "name": "Tribunal de Justiça de Sergipe", "acronym": "TJSE",
        "url": "https://www.tjse.jus.br/portal/consultas/novo-cpc/indisponibilidade-de-sistemas"},
    {"id": "130", "name": "Tribunal de Justiça do Tocantins",
        "acronym": "TJTO", "url": "https://www.tjto.jus.br/comunicacao/noticias"},

    # --- TRIBUNAIS REGIONAIS DO TRABALHO (24 TRTs) ---
    {"id": "201", "name": "TRT 1ª Região (RJ)", "acronym": "TRT1",
     "url": "https://trt1.jus.br/certidao-de-indisponibilidade"},
    {"id": "202", "name": "TRT 2ª Região (SP)", "acronym": "TRT2",
     "url": "https://aplicacoes8.trt2.jus.br/sis/indisponibilidade/consulta"},
    {"id": "203", "name": "TRT 3ª Região (MG)", "acronym": "TRT3",
     "url": "https://cinde.trt3.jus.br/cinde/certidao/listagem.htm?dswid=-6858"},
    {"id": "204", "name": "TRT 4ª Região (RS)", "acronym": "TRT4",
     "url": "https://www.trt4.jus.br/portais/trt4/pje-indisponibilidade"},
    {"id": "205", "name": "TRT 5ª Região (BA)", "acronym": "TRT5",
     "url": "https://portalpje.trt5.jus.br/pje-indisponibilidades"},
    {"id": "206", "name": "TRT 6ª Região (PE)", "acronym": "TRT6",
     "url": "https://www.trt6.jus.br/portal/noticias"},
    {"id": "207", "name": "TRT 7ª Região (CE)", "acronym": "TRT7",
     "url": "https://www.trt7.jus.br/index.php/blog/200-servicos/227-pje/7512-indisponibilidades-do-pje?start=1"},
    {"id": "208", "name": "TRT 8ª Região (PA/AP)", "acronym": "TRT8",
     "url": "https://www.trt8.jus.br/pje/indisponibilidade-do-sistema"},
    {"id": "209", "name": "TRT 9ª Região (PR)", "acronym": "TRT9",
     "url": "https://www.trt9.jus.br/portal/destaques.xhtml"},
    {"id": "210", "name": "TRT 10ª Região (DF/TO)", "acronym": "TRT10",
     "url": "https://www.trt10.jus.br/servicos/?pagina=pje/indisponibilidade/index.php"},
    {"id": "211", "name": "TRT 11ª Região (AM/RR)", "acronym": "TRT11",
     "url": "https://portal.trt11.jus.br/index.php/advogados/pagina-pje/33-pje/365-periodos-de-indisponibilidade-do-pje-jt"},
    {"id": "212", "name": "TRT 12ª Região (SC)", "acronym": "TRT12",
     "url": "https://portal.trt12.jus.br/pje/uso_indisponibilidade"},
    {"id": "213", "name": "TRT 13ª Região (PB)", "acronym": "TRT13",
     "url": "https://www.trt13.jus.br/pje/relatorio-de-indisponibilidade-do-pje"},
    {"id": "214", "name": "TRT 14ª Região (RO/AC)", "acronym": "TRT14",
     "url": "https://portal.trt14.jus.br/portal/pje/indisponibilidade"},
    {"id": "215", "name": "TRT 15ª Região (Campinas)", "acronym": "TRT15",
     "url": "https://trt15.jus.br/pje/indisponibilidade-pje"},
    {"id": "216", "name": "TRT 16ª Região (MA)", "acronym": "TRT16",
     "url": "https://www.trt16.jus.br/servicos/outros-servicos/calendario-indisponibilidade"},
    {"id": "217", "name": "TRT 17ª Região (ES)", "acronym": "TRT17",
     "url": "https://www.trt17.jus.br/web/servicos/w/indiponibilidade-sistema-pje"},
    {"id": "218", "name": "TRT 18ª Região (GO)", "acronym": "TRT18",
     "url": "https://www.trt18.jus.br/portal/servicos/pje/indisponibilidades-do-pje/"},
    {"id": "219", "name": "TRT 19ª Região (AL)", "acronym": "TRT19",
     "url": "https://site.trt19.jus.br/pjePeridosIndisponibilidades"},
    {"id": "220", "name": "TRT 20ª Região (SE)", "acronym": "TRT20",
     "url": "https://www.trt20.jus.br/pje/indisponibilidade"},
    {"id": "221", "name": "TRT 21ª Região (RN)", "acronym": "TRT21",
     "url": "https://www.trt21.jus.br/servicos/pje/indisponibilidade-sistema"},
    {"id": "222", "name": "TRT 22ª Região (PI)", "acronym": "TRT22",
     "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vT1ihmu1f1FyY-MGX2fo5ikUpRwf2QVq7KSZSANyf-r0deXMtoMM2L-pw_kFR6nFXXrdd4mdrFNKJ3F/pubhtml?gid=0&single=true"},
    {"id": "223", "name": "TRT 23ª Região (MT)", "acronym": "TRT23",
     "url": "https://portal.trt23.jus.br/portal/calendario-de-indisponibilidade-do-pje"},
    {"id": "224", "name": "TRT 24ª Região (MS)", "acronym": "TRT24",
     "url": "https://www.trt24.jus.br/indisponibilidade-do-pje"},

    # --- TRIBUNAIS REGIONAIS ELEITORAIS (TREs selecionados) ---
    {"id": "300", "name": "TSE (Nacional)", "acronym": "TSE",
     "url": "https://www.tse.jus.br/servicos-judiciais/processos/processo-judicial-eletronico/situacao-atual-dos-servicos-digitais-do-tse"},
    {"id": "301", "name": "TRE São Paulo", "acronym": "TRE-SP",
        "url": "https://www.tre-sp.jus.br/servicos-judiciais/indisponibilidade-pje"},
    {"id": "302", "name": "TRE Minas Gerais", "acronym": "TRE-MG",
        "url": "https://www.tse.jus.br/servicos-judiciais/processos/processo-judicial-eletronico/situacao-atual-dos-servicos-digitais-do-tse"},
    {"id": "303", "name": "TRE Rio de Janeiro", "acronym": "TRE-RJ",
        "url": "https://www.tre-rj.jus.br/servicos-judiciais/comunicados/comunicados"}
]

# --- PÁGINAS OFICIAIS DE NOTÍCIAS E ATOS NORMATIVOS ---
FONTES_OFICIAIS = [
    # Sistemas e CNJ
    {"nome": "Telegram - PJe News",
        "url": "https://t.me/s/pjenews", "tipo": "Notícias PJe"},
    {"nome": "PJe Legacy - Notas da Versão",
        "url": "https://docs.pje.jus.br/servicos-negociais/servico-pje-legacy/notas-da-versao", "tipo": "Release Notes"},
    {"nome": "CNJ - Notícias PDPJ-Br", "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/plataforma-digital-do-poder-judiciario-brasileiro-pdpj-br/noticias/", "tipo": "Notícias"},
    {"nome": "CNJ - Notícias Justiça 4.0",
        "url": "https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/justica-4-0/noticias/", "tipo": "Notícias"},
    {"nome": "CNJ - Atos Normativos",
        "url": "https://www.cnj.jus.br/atos_normativos/", "tipo": "Normativos"},

    # Tribunais Superiores e Conselhos
    {"nome": "STF - Notícias", "url": "https://noticias.stf.jus.br/", "tipo": "Notícias"},
    {"nome": "STJ - Últimas Notícias",
        "url": "https://www.stj.jus.br/sites/portalp/Comunicacao/Ultimas-noticias", "tipo": "Notícias"},
    {"nome": "TST - Notícias", "url": "https://www.tst.jus.br/noticias", "tipo": "Notícias"},
    {"nome": "CSJT - Normativos",
        "url": "https://www.csjt.jus.br/web/csjt/normativos", "tipo": "Normativos"},
    {"nome": "CSJT - Legislação e Atos",
        "url": "https://www.csjt.jus.br/web/csjt/legislacao-atos", "tipo": "Normativos"},

    # Tribunais de Justiça (Estaduais)
    {"nome": "TJSP - Notícias eproc",
        "url": "https://www.tjsp.jus.br/eproc/Noticias", "tipo": "Notícias eproc"},
    {"nome": "TJSP - Notícias Gerais",
        "url": "https://www.tjsp.jus.br/Noticias", "tipo": "Notícias"},
    {"nome": "TJSP - Comunicados (Precatórios)",
     "url": "https://www.tjsp.jus.br/Precatorios/Comunicados?tipoDestino=85", "tipo": "Comunicados"},
    {"nome": "TJMG - Notícias",
        "url": "https://www.tjmg.jus.br/portal-tjmg/noticias/", "tipo": "Notícias"},
    {"nome": "TJMG - Atos Normativos",
        "url": "https://www.tjmg.jus.br/portal-tjmg/atos-normativos/", "tipo": "Normativos"},
    {"nome": "TJRJ - Notícias",
        "url": "https://www.tjrj.jus.br/web/guest/noticias", "tipo": "Notícias"},
    {"nome": "TJPR - Notícias",
        "url": "https://www.tjpr.jus.br/noticias", "tipo": "Notícias"},
    {"nome": "TJPR - Legislação e Atos Normativos",
        "url": "https://www.tjpr.jus.br/legislacao-atos-normativos", "tipo": "Normativos"},
    {"nome": "TJRS - Notícias",
        "url": "https://www.tjrs.jus.br/novo/comunicacao/noticias-do-tjrs/noticias/", "tipo": "Notícias"},
    {"nome": "TJRS - Publicações Administrativas",
        "url": "https://www.tjrs.jus.br/novo/jurisprudencia-e-legislacao/publicacoes-administrativas-do-tjrs/", "tipo": "Normativos"},
    {"nome": "TJBA - Agência de Notícias",
        "url": "https://www.tjba.jus.br/portal/agencia-de-noticias/", "tipo": "Notícias"},

    # Tribunais Regionais Federais (TRFs)
    {"nome": "TRF1 - Notícias",
        "url": "https://www.trf1.jus.br/trf1/noticias/", "tipo": "Notícias"},
    {"nome": "TRF2 - Portal", "url": "https://www.trf2.jus.br/", "tipo": "Notícias"},
    {"nome": "TRF3 - Últimas Notícias",
        "url": "https://web.trf3.jus.br/noticias/Noticiar/ExibirUltimasNoticias", "tipo": "Notícias"},
    {"nome": "TRF4 - Notícias",
        "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=noticia_portal", "tipo": "Notícias"},
    {"nome": "TRF4 - Atos Normativos",
        "url": "https://www.trf4.jus.br/trf4/controlador.php?acao=ato_normativo_pesquisar", "tipo": "Normativos"},
    {"nome": "TRF5 - Notícias",
        "url": "https://www.trf5.jus.br/index.php/noticias", "tipo": "Notícias"},
    {"nome": "TRF6 - Notícias",
        "url": "https://portal.trf6.jus.br/noticias/", "tipo": "Notícias"},
    {"nome": "TRF6 - Atos Normativos",
        "url": "https://portal.trf6.jus.br/atos-normativos/", "tipo": "Normativos"},

    # Tribunais Regionais do Trabalho (TRTs)
    {"nome": "TRT1 - Últimas Notícias",
        "url": "https://www.trt1.jus.br/ultimas-noticias", "tipo": "Notícias"},
    {"nome": "TRT1 - Biblioteca Digital (Atos)",
     "url": "https://bibliotecadigital.trt1.jus.br/jspui/handle/1001/6", "tipo": "Normativos"},
    {"nome": "TRT2 - Notícias",
        "url": "https://ww2.trt2.jus.br/noticias/noticias", "tipo": "Notícias"},
    {"nome": "TRT3 - Notícias Institucionais",
        "url": "https://portal.trt3.jus.br/internet/conheca-o-trt/comunicacao/noticias-institucionais", "tipo": "Notícias"},
    {"nome": "TRT4 - Notícias",
        "url": "https://www.trt4.jus.br/portais/trt4/modulos/noticias/todas/0", "tipo": "Notícias"},
]

TERMOS_ESPECIFICOS = [
    '"2FA PJE"', '"MFA PJE"', '"dois fatores PJE"', '"duplo fator PJE"',
    '"duplo fator EPROC"', '"duplo fator ESAJ"', '"duplo fator PROJUDI"',
    '"PDPJ"', '"novo sistema tribunal"', '"mudança sistema tribunal"',
    '"migração sistema tribunal"', '"pje indisponibilidade"', '"pdpj indisponibilidade"',
    '"eproc indisponibilidade"', '"esaj indisponibilidade"',
    '"portaria CNJ 140/2024"', '"tribunal pdpj"', '"tribunal authenticator"',
    '"2FA se tornou obrigatória"', '"golpe do advogado"', '"migração TJPR EPROC"',
    '"Jus.br"', '"instabilidade pje"', '"instabilidade pdpj"', '"instabilidade eproc"',
    '"instabilidade esaj"', '"instabilidade projudi"', '"instabilidade TRT"',
    '"instabilidade dos principais tribunais EPROC"', '"cronograma de expansão"', '"desativação do sistema"', '"substituição de interface"', '"homologação de versão"',
    '"ambiente de produção"', '"Plataforma Digital"', '"Codex"', '"Integração MNI"', '"API Unificada"',
    '"SRE (Site Reliability Engineering)"', '"TOTP"', '"WebAuthn"', '"FIDO2"', '"Habilitação de Segundo Fator"',
    '"Single Sign-On (SSO)"', '"IDP (Identity Provider)"', '"Desafio Captcha"', '"hCaptcha"', '"reCAPTCHA Enterprise"', '"WAF (Web Application Firewall)"', '"Bloqueio de IP"', '"Bot Mitigation"', '"Cloudflare"', '"Akamai"',
    '"instabilidade"', '"indisponibilidade"', '"fora do ar"', '"erro de acesso"', '"Erro 403 Forbidden"',
    '"Timeout de Conexão"', '"Manutenção Emergencial"', '"Latência de Banco de Dados"', '"Incident Response"',
    '"Release Notes"', '"Hotfix"', '"Depreciação de API"', '"Breaking Changes"', '"Vulnerabilidade de Segurança"',
    '"Patch de Correção"', '"Mudança de DNS"', '"Certificado SSL/TLS"', '"CDN"', '"Data Center"',
    '"Migração para Nuvem"', '"AWS"', '"Azure"', '"Comunicado de TI"', '"Edital de Licitação de Tecnologia"',
    '"Ordem de Serviço SETIC"', '"Comitê Gestor"'
]

# ==============================================================================
# 2. MALHA FINA (Filtro rigoroso de Títulos em Python)
# ==============================================================================

# Removidos "jus.br", "migração" e "novo sistema" daqui para evitar falsos positivos
TERMOS_FORTES_TI = [
    "pje", "eproc", "projudi", "esaj", "pdpj", 
    "2fa", "mfa", "duplo fator", "dois fatores", "multifator", "authenticator", 
    "sso", "single sign-on", "captcha", "waf", "token", "ciberataque", 
    "instabilidade", "indisponibilidade", "golpe do advogado",
    "portaria nº 140", "resolução nº 335", "certificado digital",
    "ransomware", "ataque hacker", "manutenção programada", "fora do ar",
    "descontinuidade", "lentidão"
]

TERMOS_COMPOSTOS = [
    ["mudança", "sistema"],
    ["troca", "senha"],
    ["renovação", "senha"],
    ["redefinição", "senha"],
    ["código", "autenticação"],
    ["segurança", "digital"],
    ["credencial", "acesso"],
    ["código", "acesso"],
    ["migração", "sistema"],
    ["novo", "sistema"]
]

# Palavras que, se aparecerem, REPROVAM a notícia na hora (Corta o ruído administrativo)
TERMOS_BLOQUEADOS = [
    "estágio", "estagiário", "processo seletivo", "concurso", "vaga",
    "coptrel", "grêmio", "orçamentário", "orçamento", "feminicídio", "popruajud",
    "local de votação", "seções eleitorais", "mesária", "janela partidária",
    "título de eleitor", "eleições", "custas judiciais", "gestão de pessoas"
]

def validar_titulo_noticia(titulo):
    """Verifica se o título da notícia realmente fala sobre sistemas ou TI."""
    
    # O Google News adiciona " - Nome do Site" no final do título.
    # Vamos remover essa parte final para o script ler apenas o título real da notícia.
    titulo_limpo = titulo.rsplit(' - ', 1)[0].lower()
    
    # 1. FILTRO NEGATIVO: Se tiver termo de RH/Administrativo, bloqueia logo.
    if any(termo in titulo_limpo for termo in TERMOS_BLOQUEADOS):
        return False
        
    # 2. FILTRO EXATO DE TI (Usa Regex \b para garantir que é a palavra inteira)
    # Isso impede que "sso" dê match em "processo" ou "pje" em "laje".
    for termo in TERMOS_FORTES_TI:
        padrao = r'\b' + re.escape(termo) + r'\b'
        if re.search(padrao, titulo_limpo):
            return True
            
    # 3. FILTRO DE TERMOS COMPOSTOS
    for par in TERMOS_COMPOSTOS:
        padrao1 = r'\b' + re.escape(par[0]) + r'\b'
        padrao2 = r'\b' + re.escape(par[1]) + r'\b'
        if re.search(padrao1, titulo_limpo) and re.search(padrao2, titulo_limpo):
            return True
            
    return False
# ==============================================================================
# 3. MOTOR DE BUSCA E EXTRAÇÃO
# ==============================================================================


def extrair_noticias_do_feed(url_rss, data_limite, links_ja_coletados, todas_noticias):
    """Lê o RSS, valida a data, a duplicidade e passa pelo filtro de título."""
    feed = feedparser.parse(url_rss)
    for entry in feed.entries:
        if hasattr(entry, 'published_parsed'):
            data_publicacao = datetime.fromtimestamp(
                time.mktime(entry.published_parsed))

            # Condição tripla: Data Ok + Link Novo + Título Relevante
            if data_publicacao >= data_limite and entry.link not in links_ja_coletados:
                if validar_titulo_noticia(entry.title):
                    todas_noticias.append({
                        'titulo': entry.title,
                        'link': entry.link,
                        'data_obj': data_publicacao,
                        'fonte': entry.source.title if hasattr(entry, 'source') else "Google News"
                    })
                    links_ja_coletados.add(entry.link)


def buscar_noticias_semanais():
    todas_noticias = []
    links_ja_coletados = set()
    ## Alterado para buscar notícias dos últimos 3 dias
    data_limite = datetime.now() - timedelta(days=3)

    # ==============================================================================
    # O SEGREDO ESTÁ AQUI: Adicionamos o "site:jus.br" para forçar o Google
    # a procurar APENAS em domínios oficiais da justiça (eliminando G1, Conjur, etc).
    # ==============================================================================
    filtro_dominio = "(site:jus.br OR site:csjt.jus.br)"

    # ==============================================================================
    # O SEGREDO ESTÁ AQUI: Rede Larga de TI, SRE e Segurança (Fase 1)
    # ==============================================================================
    termos_base_google = (
        '('
        '"PJe" OR "eproc" OR "projudi" OR "e-SAJ" OR "PDPJ" OR '
        '"indisponibilidade" OR "instabilidade" OR "manutenção" OR "fora do ar" OR "lentidão" OR '
        '"2FA" OR "MFA" OR "SSO" OR "ciberataque" OR "hacker" OR "vulnerabilidade" OR "token" OR '
        '"migração" OR "atualização" OR "versão" OR "API" OR "nuvem" OR "datacenter"'
        ')'
    )

    siglas = [tribunal["acronym"] for tribunal in TRIBUNAIS]
    tamanho_lote = 10
    lotes_siglas = [siglas[i:i + tamanho_lote]
                    for i in range(0, len(siglas), tamanho_lote)]

    print(
        f"Iniciando Fase 1: Varredura de {len(siglas)} Tribunais APENAS em fontes oficiais...")
    for i, lote in enumerate(lotes_siglas, 1):
        query_tribunais = "(" + \
            " OR ".join(f'"{sigla}"' for sigla in lote) + ")"

        # Junta os termos base + as siglas dos tribunais + o filtro de domínios oficiais
        query_final = f"{termos_base_google} AND {query_tribunais} AND {filtro_dominio}"
        query_codificada = urllib.parse.quote(query_final)

        url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        extrair_noticias_do_feed(url_rss, data_limite,
                                 links_ja_coletados, todas_noticias)
        time.sleep(1.5)

    print("Iniciando Fase 2: Busca por frases exatas de TI e Segurança APENAS em fontes oficiais...")
    tamanho_lote_termos = 6
    lotes_termos = [TERMOS_ESPECIFICOS[i:i + tamanho_lote_termos]
                    for i in range(0, len(TERMOS_ESPECIFICOS), tamanho_lote_termos)]

    for i, lote in enumerate(lotes_termos, 1):
        query_frases = "(" + " OR ".join(lote) + ")"

        # Junta as frases específicas + o filtro de domínios oficiais
        query_final = f"{query_frases} AND {filtro_dominio}"
        query_codificada = urllib.parse.quote(query_final)

        url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        extrair_noticias_do_feed(url_rss, data_limite,
                                 links_ja_coletados, todas_noticias)
        time.sleep(1.5)

    # Ordena cronologicamente
    todas_noticias.sort(key=lambda x: x['data_obj'], reverse=True)
    return todas_noticias

# ==============================================================================
# 4. GERAÇÃO DE E-MAIL (TEXTO E HTML) E ENVIO
# ==============================================================================


def gerar_corpos_email(noticias):
    hoje = datetime.now().strftime("%d/%m/%Y")
    uma_semana_atras = (datetime.now() - timedelta(days=2)).strftime("%d/%m/%Y")

    texto_puro = f"MAST - Monitoramento Automatizado de Sistemas e Tribunais ({uma_semana_atras} a {hoje})\n\n"

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #2c3e50;">Monitoramento Automatizado de Sistemas e Tribunais (MAST)</h2>
        <p>Período: <strong>{uma_semana_atras}</strong> até <strong>{hoje}</strong></p>
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

            # 1. Procura de qual tribunal é essa notícia para pegar a URL oficial
            link_oficial_html = ""
            link_oficial_texto = ""
            for tribunal in TRIBUNAIS:
                if tribunal['acronym'].lower() in titulo_lower:
                    link_oficial_html = f"<br><a href='{tribunal['url']}' style='display: inline-block; margin-top: 8px; padding: 5px 10px; background-color: #e8f4f8; color: #2980b9; text-decoration: none; border-radius: 4px; font-size: 0.85em;'>🔍 Checar Status Oficial do {tribunal['acronym']}</a>"
                    #link_oficial_texto = f"\n   Status Oficial: {tribunal['url']}"
                    break  # Para de procurar assim que achar o primeiro

            # 2. Adiciona ao Texto Puro
            texto_puro += f"{i}. {noticia['titulo']}\n   Data: {data_formatada}\n   Link da Notícia: {noticia['link']}{link_oficial_texto}\n\n"

            # 3. Adiciona ao HTML
            html += f"""
            <li style="margin-bottom: 20px; padding: 15px; border-left: 4px solid #3498db; background-color: #f9f9f9;">
                <h3 style="margin: 0 0 10px 0;">
                    <a href="{noticia['link']}" style="color: #2c3e50; text-decoration: none;">{noticia['titulo']}</a>
                </h3>
                <p style="margin: 0; font-size: 0.9em; color: #7f8c8d;">
                    📅 {data_formatada} &nbsp;|&nbsp; 📰 Fonte: {noticia['fonte']}
                </p>
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


def enviar_email(texto_puro, html, total_noticias):
    remetente = os.environ.get('EMAIL_REMETENTE')
    senha = os.environ.get('EMAIL_SENHA')
    destinatario = os.environ.get('EMAIL_DESTINATARIO')

    if not remetente or not senha:
        print("Erro: Credenciais não configuradas no GitHub Secrets.")
        return

    # O MIMEMultipart('alternative') diz ao cliente de e-mail para tentar ler o HTML,
    # e se não conseguir, usar o texto puro.
    msg = MIMEMultipart('alternative')
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = f"Monitoramento Automatizado de Sistemas e Tribunais - {datetime.now().strftime('%d/%m/%Y')} ({total_noticias} alertas)"

    # Anexa as duas versões
    parte1 = MIMEText(texto_puro, 'plain', 'utf-8')
    parte2 = MIMEText(html, 'html', 'utf-8')
    msg.attach(parte1)
    msg.attach(parte2)

    try:
        print("Conectando ao servidor SMTP...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        print(
            f"E-mail HTML enviado com sucesso para {destinatario}! ({total_noticias} alertas)")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")


if __name__ == "__main__":
    noticias_filtradas = buscar_noticias_semanais()
    texto, html = gerar_corpos_email(noticias_filtradas)

    # Exibe no log do GitHub Actions quantos itens passaram pela malha fina e o corpo do texto
    print(
        f"Total de notícias validadas pela malha fina: {len(noticias_filtradas)}\n")
    print("=== CORPO DO E-MAIL GERADO ===")
    print(texto)
    print("==============================")

    enviar_email(texto, html, len(noticias_filtradas))
