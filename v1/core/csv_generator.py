# core/csv_generator.py
import logging
import os
import csv
from datetime import datetime

log = logging.getLogger(__name__)

_CABECALHO = [
    'Data da Notícia', 'Nome da Fonte', 'Título', 'Status',
    'Motivo da Decisão', 'Lista do Gatilho', 'Palavra Capturada', 'Link da Notícia',
]
# row contém 8 itens na ordem: data_noticia, nome_fonte, titulo_noticia,
# status, motivo, termo_base (Lista do Gatilho), palavra_encontrada (Palavra Capturada), link


def _escrever_csv(caminho: str, dados: list[tuple]) -> None:
    """Grava cabeçalho + linhas em um arquivo CSV UTF-8-sig."""
    with open(caminho, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(_CABECALHO)
        if dados:
            writer.writerows(dados)


def gerar_csv_relatorio(dados: list[tuple]) -> str:
    """
    Gera o CSV da rodada atual e salva uma cópia histórica com timestamp.

    Retorna o caminho do arquivo principal (Historico.csv) — usado como
    anexo no e-mail.

    Estrutura de arquivos:
      Historico.csv                          ← sobrescrito a cada run (para e-mail)
      historico/Historico_YYYY-MM-DD_HHMM.csv ← cópia permanente por execução
    """
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    # Arquivo principal (backward-compat com e-mail e GitHub Actions cache)
    caminho_csv = os.path.join(raiz, 'Historico.csv')

    # Cópia histórica com timestamp — nunca sobrescrita
    historico_dir = os.path.join(raiz, 'historico')
    os.makedirs(historico_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    caminho_historico = os.path.join(historico_dir, f"Historico_{timestamp}.csv")

    _escrever_csv(caminho_csv, dados)
    _escrever_csv(caminho_historico, dados)

    log.info("📊 CSV gerado: %s", caminho_csv)
    log.info("📦 Cópia histórica: %s", caminho_historico)
    return caminho_csv
