"""
config.py

Centraliza todas as configurações do projeto.

As variáveis podem ser alteradas no arquivo .env sem necessidade
de modificar o restante do código.
"""

from pathlib import Path
from dotenv import load_dotenv
import os

# -------------------------------------------------------------------
# Carrega as variáveis do .env
# -------------------------------------------------------------------

load_dotenv()

# -------------------------------------------------------------------
# API
# -------------------------------------------------------------------

API_URL = os.getenv(
    "API_URL",
    "https://api.tupinambaenergia.com.br/station"
)

# -------------------------------------------------------------------
# Estações monitoradas
# -------------------------------------------------------------------
#
# Fonte única de verdade: id da estação (o mesmo usado na URL da API),
# nome amigável pra exibir no dashboard, e preço cobrado por kWh
# (usado pra estimar receita — ver tracker.py).

STATIONS = {
    "CPZON22": {
        "name": "Posto Enseada",
        "price_kwh": 2.00,
    },
    "CPMADRI001": {
        "name": "Orange Energy - Posto Bultrins",
        "price_kwh": 1.49,
    },
    "CPONENG30": {
        "name": "Galeria Dona Maria",
        "price_kwh": 2.00,
    },
    "1125951818": {
        "name": "Fênix",
        "price_kwh": 1.49,
    },
}

STATION_IDS = list(STATIONS.keys())


def get_station_name(station_id: str) -> str:
    return STATIONS.get(station_id, {}).get("name", station_id)


def get_station_price(station_id: str) -> float:
    return STATIONS.get(station_id, {}).get("price_kwh", 0.0)

# -------------------------------------------------------------------
# Intervalo entre consultas
# -------------------------------------------------------------------

INTERVAL = int(
    os.getenv("INTERVAL", "300")
)

# -------------------------------------------------------------------
# Diretórios do projeto
# -------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

SNAPSHOT_DIR = DATA_DIR / "snapshots"

LOG_DIR = BASE_DIR / "logs"

# cria automaticamente caso não existam

DATA_DIR.mkdir(exist_ok=True)

SNAPSHOT_DIR.mkdir(exist_ok=True)

LOG_DIR.mkdir(exist_ok=True)

# cria uma subpasta de snapshots por estação

for _station_id in STATION_IDS:
    (SNAPSHOT_DIR / _station_id).mkdir(exist_ok=True, parents=True)

# -------------------------------------------------------------------
# Arquivos
# -------------------------------------------------------------------

SESSIONS_FILE = DATA_DIR / "sessions.csv"

METRICS_FILE = DATA_DIR / "metrics.csv"

# registra tentativas de carregamento que ficaram em "Preparing"
# (autenticação/handshake) e não evoluíram para "Charging"
ATTEMPTS_FILE = DATA_DIR / "attempts.csv"

LOG_FILE = LOG_DIR / "monitor.log"

# agora é um único arquivo com o estado de TODAS as estações,
# indexado por station_id
LAST_STATE_FILE = DATA_DIR / "last_state.json"