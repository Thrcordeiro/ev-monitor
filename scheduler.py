"""
scheduler.py

Loop principal do EV Monitor.

A cada INTERVAL segundos:
- Consulta todas as estações configuradas em STATION_IDS
- Processa cada snapshot (detecção de sessões via tracker.py)
"""

import time

from config import STATION_IDS, INTERVAL
from collector import Collector
from tracker import process_snapshot
from utils import log


def run_once():

    """
    Executa uma rodada de coleta para todas as estações configuradas.
    """

    for station_id in STATION_IDS:

        payload = Collector(station_id).collect()

        if payload:
            process_snapshot(payload)


def run_forever():

    log(f"Iniciando EV Monitor. Estações: {', '.join(STATION_IDS)}")

    log(f"Intervalo de coleta: {INTERVAL}s")

    while True:

        try:

            run_once()

        except Exception as e:

            log(f"Erro inesperado no ciclo do scheduler: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":

    run_forever()