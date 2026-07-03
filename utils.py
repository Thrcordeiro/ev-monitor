"""
utils.py

Funções auxiliares usadas por todo o projeto.
"""

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from config import LOG_FILE

# --------------------------------------------------------
# Configuração do logger
# --------------------------------------------------------

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------
# Timestamp atual
# --------------------------------------------------------

def now():

    """
    Retorna data/hora atual (local, naive) — usado para exibição/log.
    """

    return datetime.now()


def now_utc():

    """
    Retorna data/hora atual em UTC (timezone-aware) — usado para
    cálculos de duração, já que a API retorna timestamps em UTC (Z).
    """

    return datetime.now(timezone.utc)


def parse_api_timestamp(value):

    """
    Converte um timestamp da API (ex: '2026-07-02T17:44:29.833Z')
    em um datetime timezone-aware (UTC). Retorna None se vazio/inválido.
    """

    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


# --------------------------------------------------------
# Nome do arquivo do mês
# --------------------------------------------------------

def snapshot_filename():

    """
    Exemplo

    2026-07.jsonl
    """

    return now().strftime("%Y-%m") + ".jsonl"


# --------------------------------------------------------
# Salvar snapshot
# --------------------------------------------------------

def save_snapshot(path: Path, payload: dict):

    """
    Salva um JSON por linha.

    JSONL é muito mais eficiente para append.
    """

    with open(path, "a", encoding="utf-8") as file:

        file.write(
            json.dumps(
                payload,
                ensure_ascii=False
            )
        )

        file.write("\n")


# --------------------------------------------------------
# Estado (last_state.json) — indexado por station_id
# --------------------------------------------------------

def load_last_state(path: Path) -> dict:

    """
    Carrega o dicionário completo de estado (todas as estações).
    Retorna {} se o arquivo não existir ou estiver vazio/corrompido.
    """

    if not path.exists():
        return {}

    try:
        content = path.read_text(encoding="utf-8").strip()

        if not content:
            return {}

        return json.loads(content)

    except json.JSONDecodeError:
        log(f"Aviso: {path} inválido, recomeçando estado do zero.")
        return {}


def save_last_state(path: Path, state: dict):

    """
    Salva o dicionário completo de estado (todas as estações).
    """

    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# --------------------------------------------------------
# CSV — append genérico com criação automática de header
# --------------------------------------------------------

def append_csv_row(path: Path, fieldnames: list, row: dict):

    """
    Adiciona uma linha a um CSV, criando o arquivo com header
    caso ainda não exista.
    """

    file_exists = path.exists() and path.stat().st_size > 0

    with open(path, "a", encoding="utf-8", newline="") as file:

        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


def read_csv_rows(path: Path) -> list:

    """
    Lê um CSV e retorna uma lista de dicts. Retorna [] se o
    arquivo não existir ou estiver vazio.
    """

    if not path.exists() or path.stat().st_size == 0:
        return []

    with open(path, "r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_csv_rows(path: Path, fieldnames: list, rows: list):

    """
    Sobrescreve um CSV inteiro com as linhas fornecidas.
    Usado para atualizar (upsert) o metrics.csv.
    """

    with open(path, "w", encoding="utf-8", newline="") as file:

        writer = csv.DictWriter(file, fieldnames=fieldnames)

        writer.writeheader()

        for row in rows:
            writer.writerow(row)


# --------------------------------------------------------
# Log amigável
# --------------------------------------------------------

def log(message):

    print(message)

    logger.info(message)