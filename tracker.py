"""
tracker.py

Responsável por:

- Comparar o snapshot atual com o último estado conhecido (last_state.json)
- Detectar início e fim de sessões de carregamento por conector
- Detectar tentativas de carregamento que ficam em "Preparing"
  (autenticação/handshake) e não evoluem para "Charging"
- Gravar sessões concluídas em sessions.csv
- Gravar tentativas falhas em attempts.csv
- Atualizar contagem diária em metrics.csv

Regra de negócio do projeto fica toda aqui.
"""

from config import (
    LAST_STATE_FILE,
    SESSIONS_FILE,
    METRICS_FILE,
    ATTEMPTS_FILE,
    get_station_price,
)

from utils import (
    load_last_state,
    save_last_state,
    append_csv_row,
    read_csv_rows,
    write_csv_rows,
    parse_api_timestamp,
    now_utc,
    log,
)

SESSIONS_FIELDNAMES = [
    "station_id",
    "connector_id",
    "connector_name",
    "start_time",
    "end_time",
    "duration_minutes",
    "power_kw",
    "estimated_kwh",
    "price_kwh",
    "estimated_revenue_brl",
    "status",
]

METRICS_FIELDNAMES = [
    "date",
    "station_id",
    "sessions",
    "estimated_revenue_brl",
    "failed_attempts",
]

ATTEMPTS_FIELDNAMES = [
    "station_id",
    "connector_id",
    "connector_name",
    "prep_start",
    "prep_end",
    "duration_seconds",
    "outcome",
]

CHARGING_STATE = "Charging"
PREPARING_STATE = "Preparing"


def _blank_connector_state(current_state: str, connector: dict) -> dict:

    """Estado padrão pra conectores sem sessão/tentativa em andamento."""

    return {
        "state": current_state,
        "connector_name": connector.get("name"),
        "start_time": None,
        "power_kw": None,
        "prep_start": None,
    }


def process_snapshot(payload: dict):

    """
    Recebe o payload retornado pelo Collector e atualiza
    sessions.csv / attempts.csv / metrics.csv / last_state.json
    conforme necessário.
    """

    if not payload:
        return

    station_id = payload["station_id"]

    full_state = load_last_state(LAST_STATE_FILE)

    station_prev_state = full_state.get(station_id, {})

    station_new_state = {}

    for connector in payload["connectors"]:

        conn_id = str(connector["id"])

        current_state = connector["state"]

        prev = station_prev_state.get(conn_id, {})

        prev_state = prev.get("state")

        # -----------------------------------------------------
        # 1) Início de uma sessão de carregamento (-> Charging)
        #    Cobre tanto Available -> Charging quanto
        #    Preparing -> Charging (autenticação bem-sucedida).
        # -----------------------------------------------------

        if current_state == CHARGING_STATE and prev_state != CHARGING_STATE:

            start_time = connector.get("started_on") or payload["timestamp"]

            station_new_state[conn_id] = {
                "state": current_state,
                "connector_name": connector.get("name"),
                "start_time": start_time,
                "power_kw": connector.get("power"),
                "prep_start": None,
            }

            log(
                f"[{station_id}] Conector {conn_id} iniciou carregamento "
                f"({start_time})."
            )

        # -----------------------------------------------------
        # 2) Sessão de carregamento em andamento
        # -----------------------------------------------------

        elif current_state == CHARGING_STATE and prev_state == CHARGING_STATE:

            station_new_state[conn_id] = {
                "state": current_state,
                "connector_name": connector.get("name"),
                "start_time": prev.get("start_time"),
                "power_kw": prev.get("power_kw", connector.get("power")),
                "prep_start": None,
            }

        # -----------------------------------------------------
        # 3) Fim de uma sessão de carregamento (Charging -> outro)
        # -----------------------------------------------------

        elif current_state != CHARGING_STATE and prev_state == CHARGING_STATE:

            start_dt = parse_api_timestamp(prev.get("start_time"))

            end_dt = now_utc()

            power_kw = prev.get("power_kw") or connector.get("power") or 0

            if start_dt:
                duration_minutes = round(
                    (end_dt - start_dt).total_seconds() / 60, 1
                )
                duration_hours = duration_minutes / 60
            else:
                duration_minutes = None
                duration_hours = 0

            # Estimativa: assume que o conector operou na potência nominal
            # durante toda a sessão. É uma aproximação — a API não retorna
            # o kWh real consumido, só a potência máxima do conector.
            estimated_kwh = round(power_kw * duration_hours, 2)

            price_kwh = get_station_price(station_id)

            estimated_revenue = round(estimated_kwh * price_kwh, 2)

            row = {
                "station_id": station_id,
                "connector_id": conn_id,
                "connector_name": connector.get("name"),
                "start_time": prev.get("start_time"),
                "end_time": end_dt.isoformat(),
                "duration_minutes": duration_minutes,
                "power_kw": power_kw,
                "estimated_kwh": estimated_kwh,
                "price_kwh": price_kwh,
                "estimated_revenue_brl": estimated_revenue,
                "status": "completed",
            }

            append_csv_row(SESSIONS_FILE, SESSIONS_FIELDNAMES, row)

            update_daily_metrics(
                station_id,
                end_dt.date().isoformat(),
                revenue=estimated_revenue,
                sessions_delta=1,
            )

            log(
                f"[{station_id}] Conector {conn_id} encerrou carregamento "
                f"(duração: {duration_minutes} min, "
                f"receita estimada: R$ {estimated_revenue})."
            )

            station_new_state[conn_id] = _blank_connector_state(
                current_state, connector
            )

        # -----------------------------------------------------
        # 4) Início de uma tentativa (-> Preparing)
        # -----------------------------------------------------

        elif current_state == PREPARING_STATE and prev_state != PREPARING_STATE:

            station_new_state[conn_id] = {
                "state": current_state,
                "connector_name": connector.get("name"),
                "start_time": None,
                "power_kw": None,
                "prep_start": now_utc().isoformat(),
            }

            log(
                f"[{station_id}] Conector {conn_id} iniciou autenticação "
                f"(Preparing)."
            )

        # -----------------------------------------------------
        # 5) Tentativa em andamento (continua Preparing)
        # -----------------------------------------------------

        elif current_state == PREPARING_STATE and prev_state == PREPARING_STATE:

            station_new_state[conn_id] = {
                "state": current_state,
                "connector_name": connector.get("name"),
                "start_time": None,
                "power_kw": None,
                "prep_start": prev.get("prep_start"),
            }

        # -----------------------------------------------------
        # 6) Tentativa falhou (Preparing -> algo que não é Charging)
        # -----------------------------------------------------

        elif prev_state == PREPARING_STATE and current_state != CHARGING_STATE:

            prep_start_dt = parse_api_timestamp(prev.get("prep_start"))

            end_dt = now_utc()

            if prep_start_dt:
                duration_seconds = round(
                    (end_dt - prep_start_dt).total_seconds(), 1
                )
            else:
                duration_seconds = None

            row = {
                "station_id": station_id,
                "connector_id": conn_id,
                "connector_name": connector.get("name"),
                "prep_start": prev.get("prep_start"),
                "prep_end": end_dt.isoformat(),
                "duration_seconds": duration_seconds,
                "outcome": "failed",
            }

            append_csv_row(ATTEMPTS_FILE, ATTEMPTS_FIELDNAMES, row)

            update_daily_metrics(
                station_id,
                end_dt.date().isoformat(),
                revenue=0,
                sessions_delta=0,
                failed_attempts_delta=1,
            )

            log(
                f"[{station_id}] Conector {conn_id}: tentativa de "
                f"carregamento FALHOU (ficou {duration_seconds}s em "
                f"Preparing e voltou para {current_state})."
            )

            station_new_state[conn_id] = _blank_connector_state(
                current_state, connector
            )

        # -----------------------------------------------------
        # Sem mudança relevante (ex: sempre Available, ou primeira vez visto)
        # -----------------------------------------------------

        else:

            station_new_state[conn_id] = _blank_connector_state(
                current_state, connector
            )

    full_state[station_id] = station_new_state

    save_last_state(LAST_STATE_FILE, full_state)


def update_daily_metrics(
    station_id: str,
    date_str: str,
    revenue: float = 0,
    sessions_delta: int = 0,
    failed_attempts_delta: int = 0,
):

    """
    Faz upsert em metrics.csv: incrementa sessões concluídas, receita
    estimada e/ou tentativas falhas do dia/estação informados (cria a
    linha se não existir).
    """

    rows = read_csv_rows(METRICS_FILE)

    found = False

    for row in rows:

        if row["date"] == date_str and row["station_id"] == station_id:

            row["sessions"] = str(int(row.get("sessions") or 0) + sessions_delta)

            current_revenue = float(row.get("estimated_revenue_brl") or 0)

            row["estimated_revenue_brl"] = round(current_revenue + revenue, 2)

            row["failed_attempts"] = str(
                int(row.get("failed_attempts") or 0) + failed_attempts_delta
            )

            found = True

            break

    if not found:

        rows.append(
            {
                "date": date_str,
                "station_id": station_id,
                "sessions": str(sessions_delta),
                "estimated_revenue_brl": revenue,
                "failed_attempts": str(failed_attempts_delta),
            }
        )

    write_csv_rows(METRICS_FILE, METRICS_FIELDNAMES, rows)