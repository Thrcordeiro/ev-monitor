"""
collector.py

Responsável por:

- Consultar a API de uma estação
- Validar a resposta
- Adicionar timestamp
- Salvar snapshot em JSONL (uma pasta por estação)

Nenhuma regra de negócio fica aqui.
"""

from datetime import datetime

import httpx

from config import (
    API_URL,
    SNAPSHOT_DIR,
)

from utils import (
    save_snapshot,
    snapshot_filename,
    log,
)


def _null_if_empty(value):

    """
    A API do Tupi às vezes retorna string vazia em vez de null
    quando um campo não tem valor. Normaliza pra None de verdade,
    senão as colunas ficam com tipo misto (int + '') e quebram a
    serialização Arrow no dashboard.
    """

    return None if value == "" else value


class Collector:

    def __init__(self, station_id: str):

        self.station_id = station_id

        self.url = f"{API_URL}/{station_id}"

        self.headers = {
            "User-Agent": "EV-Monitor/1.0"
        }

    def collect(self):

        """
        Consulta a API e salva um snapshot para esta estação.
        """

        try:

            log(f"Consultando estação {self.station_id}...")

            response = httpx.get(
                self.url,
                headers=self.headers,
                timeout=30
            )

            response.raise_for_status()

            station = response.json()

            # =====================================================
            # Resumo dos conectores
            # =====================================================

            connectors = []

            for plug in station.get("connectedPlugs", []):

                connectors.append(
                    {
                        "id": _null_if_empty(plug.get("connectorID")),
                        "name": _null_if_empty(plug.get("name")),
                        "power": _null_if_empty(plug.get("power")),
                        "state": _null_if_empty(plug.get("stateName")),
                        "started_user": _null_if_empty(plug.get("startedUserID")),
                        "started_on": _null_if_empty(plug.get("startChargingOn"))
                    }
                )

            # =====================================================
            # Snapshot
            # =====================================================

            payload = {

                "timestamp": datetime.now().isoformat(),

                "station_id": station.get("stationID") or self.station_id,

                "station_name": station.get("name"),

                "station_state": station.get("stateName"),

                "connectors": connectors,

                # JSON ORIGINAL
                "data": station

            }

            station_dir = SNAPSHOT_DIR / self.station_id

            station_dir.mkdir(exist_ok=True, parents=True)

            file = station_dir / snapshot_filename()

            save_snapshot(
                file,
                payload
            )

            log(f"Snapshot de {self.station_id} salvo com sucesso.")

            return payload

        except httpx.HTTPStatusError as e:

            log(
                f"[{self.station_id}] Erro HTTP {e.response.status_code}"
            )

        except httpx.RequestError as e:

            log(
                f"[{self.station_id}] Erro de conexão: {e}"
            )

        except Exception as e:

            log(
                f"[{self.station_id}] Erro inesperado: {e}"
            )

        return None


if __name__ == "__main__":

    from config import STATION_IDS

    for sid in STATION_IDS:
        Collector(sid).collect()