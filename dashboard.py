"""
dashboard.py

Painel Streamlit para visualizar o histórico de uso dos eletropostos
monitorados pelo EV Monitor.
"""

import json
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from config import (
    STATION_IDS,
    STATIONS,
    SESSIONS_FILE,
    METRICS_FILE,
    ATTEMPTS_FILE,
    LAST_STATE_FILE,
    get_station_name,
    get_station_price,
)

# Todos os timestamps são calculados e armazenados em UTC (é o jeito
# correto de calcular duração/energia). Convertemos para o horário de
# Recife só na hora de EXIBIR na tela.
LOCAL_TZ = ZoneInfo("America/Recife")


def to_local(series):
    return series.dt.tz_convert(LOCAL_TZ)

st.set_page_config(
    page_title="EV Monitor",
    page_icon="🔌",
    layout="wide",
)

# ---------------------------------------------------------------
# CSS responsivo — empilha colunas verticalmente em telas estreitas
# (celular), evita que cards/métricas fiquem espremidos, e ajusta
# tipografia/espaçamento pra caber melhor.
# ---------------------------------------------------------------

st.markdown(
    """
    <style>
    @media (max-width: 680px) {

        /* empilha qualquer st.columns() verticalmente */
        [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            gap: 0.5rem !important;
        }
        [data-testid="stColumn"] {
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }

        /* título menor pra caber numa linha */
        h1 {
            font-size: 1.5rem !important;
        }
        h2, h3 {
            font-size: 1.15rem !important;
        }

        /* menos espaço em branco nas laterais */
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 2rem !important;
        }

        /* métricas (st.metric) ocupando a largura toda, texto legível */
        [data-testid="stMetric"] {
            width: 100% !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🔌 EV Monitor — Painel de Eletropostos")


# ---------------------------------------------------------------
# Atualização automática
# ---------------------------------------------------------------

auto_refresh = st.sidebar.checkbox("Atualização automática", value=True)

refresh_interval = st.sidebar.selectbox(
    "Intervalo de atualização",
    options=[30, 60, 120, 300],
    index=1,
    format_func=lambda s: f"{s}s",
    disabled=not auto_refresh,
)

if auto_refresh:

    components.html(
        f"""
        <script>
            setTimeout(function() {{
                window.parent.location.reload();
            }}, {refresh_interval * 1000});
        </script>
        """,
        height=0,
    )

    st.sidebar.caption(f"🔄 Atualizando a cada {refresh_interval}s")

st.sidebar.divider()


# ---------------------------------------------------------------
# Carregamento de dados
# ---------------------------------------------------------------

SESSIONS_COLUMNS = [
    "station_id", "connector_id", "connector_name",
    "start_time", "end_time", "duration_minutes",
    "power_kw", "estimated_kwh", "price_kwh",
    "estimated_revenue_brl", "status",
]

METRICS_COLUMNS = [
    "date", "station_id", "sessions",
    "estimated_revenue_brl", "failed_attempts",
]

ATTEMPTS_COLUMNS = [
    "station_id", "connector_id", "connector_name",
    "prep_start", "prep_end", "duration_seconds", "outcome",
]


def _outdated_schema_warning(filename: str):
    st.warning(
        f"⚠️ `{filename}` está com um formato antigo (de uma versão "
        f"anterior do projeto) e foi ignorado. Apague o arquivo em "
        f"`data/{filename}` e reinicie o scheduler.py para recriá-lo "
        f"no formato atual.",
        icon="⚠️",
    )


@st.cache_data(ttl=20)
def load_sessions():

    if not SESSIONS_FILE.exists() or SESSIONS_FILE.stat().st_size == 0:
        return pd.DataFrame(columns=SESSIONS_COLUMNS)

    df = pd.read_csv(SESSIONS_FILE)

    if "station_id" not in df.columns:
        _outdated_schema_warning("sessions.csv")
        return pd.DataFrame(columns=SESSIONS_COLUMNS)

    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce", utc=True)
    df["end_time"] = pd.to_datetime(df["end_time"], errors="coerce", utc=True)

    return df


@st.cache_data(ttl=20)
def load_metrics():

    if not METRICS_FILE.exists() or METRICS_FILE.stat().st_size == 0:
        return pd.DataFrame(columns=METRICS_COLUMNS)

    df = pd.read_csv(METRICS_FILE)

    if "station_id" not in df.columns:
        _outdated_schema_warning("metrics.csv")
        return pd.DataFrame(columns=METRICS_COLUMNS)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    return df


@st.cache_data(ttl=20)
def load_attempts():

    if not ATTEMPTS_FILE.exists() or ATTEMPTS_FILE.stat().st_size == 0:
        return pd.DataFrame(columns=ATTEMPTS_COLUMNS)

    df = pd.read_csv(ATTEMPTS_FILE)

    if "station_id" not in df.columns:
        _outdated_schema_warning("attempts.csv")
        return pd.DataFrame(columns=ATTEMPTS_COLUMNS)

    df["prep_start"] = pd.to_datetime(df["prep_start"], errors="coerce", utc=True)
    df["prep_end"] = pd.to_datetime(df["prep_end"], errors="coerce", utc=True)

    return df


def load_last_state():

    if not LAST_STATE_FILE.exists() or LAST_STATE_FILE.stat().st_size == 0:
        return {}

    try:
        return json.loads(LAST_STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


sessions_df = load_sessions()
metrics_df = load_metrics()
attempts_df = load_attempts()
last_state = load_last_state()


# ---------------------------------------------------------------
# Filtro de estação
# ---------------------------------------------------------------

station_labels = {sid: f"{get_station_name(sid)} ({sid})" for sid in STATION_IDS}

station_options = ["Todas"] + STATION_IDS

selected_station = st.sidebar.selectbox(
    "Estação",
    station_options,
    format_func=lambda sid: "Todas" if sid == "Todas" else station_labels[sid],
)

st.sidebar.divider()
st.sidebar.caption("Preço por kWh")
for sid in STATION_IDS:
    st.sidebar.write(f"**{get_station_name(sid)}**: R$ {get_station_price(sid):.2f}")

if selected_station != "Todas":
    sessions_view = sessions_df[sessions_df["station_id"] == selected_station]
    metrics_view = metrics_df[metrics_df["station_id"] == selected_station]
    attempts_view = attempts_df[attempts_df["station_id"] == selected_station]
else:
    sessions_view = sessions_df
    metrics_view = metrics_df
    attempts_view = attempts_df


# ---------------------------------------------------------------
# Estado atual dos conectores
# ---------------------------------------------------------------

st.subheader("Estado atual dos conectores")

stations_to_show = (
    STATION_IDS if selected_station == "Todas" else [selected_station]
)

cols = st.columns(len(stations_to_show))

for col, station_id in zip(cols, stations_to_show):

    with col:

        st.markdown(f"**{get_station_name(station_id)}**")
        st.caption(f"{station_id} — R$ {get_station_price(station_id):.2f}/kWh")

        state = last_state.get(station_id, {})

        if not state:
            st.caption("Sem dados ainda.")
            continue

        for conn_id, info in state.items():

            status = info.get("state", "Desconhecido")

            if status == "Charging":
                emoji = "⚡"
            elif status == "Available":
                emoji = "🟢"
            elif status == "Preparing":
                emoji = "🟡"
            else:
                emoji = "⚪"

            st.write(f"{emoji} Conector {conn_id} ({info.get('connector_name', '')}) — {status}")


st.divider()


# ---------------------------------------------------------------
# Sessões em andamento (ainda não finalizaram)
# ---------------------------------------------------------------

st.subheader("🔵 Sessões em andamento")

ongoing_rows = []

for station_id in stations_to_show:

    state = last_state.get(station_id, {})

    for conn_id, info in state.items():

        if info.get("state") != "Charging" or not info.get("start_time"):
            continue

        start_dt = pd.to_datetime(info["start_time"], utc=True, errors="coerce")

        if pd.isna(start_dt):
            continue

        now = pd.Timestamp.now(tz="UTC")

        elapsed_minutes = round((now - start_dt).total_seconds() / 60, 1)

        power_kw = info.get("power_kw") or 0

        estimated_kwh_so_far = round(power_kw * elapsed_minutes / 60, 2)

        price_kwh = get_station_price(station_id)

        estimated_revenue_so_far = round(estimated_kwh_so_far * price_kwh, 2)

        ongoing_rows.append(
            {
                "posto": get_station_name(station_id),
                "station_id": station_id,
                "connector_id": conn_id,
                "connector_name": info.get("connector_name"),
                "start_time": to_local(pd.Series([start_dt])).iloc[0],
                "elapsed_minutes": elapsed_minutes,
                "power_kw": power_kw,
                "estimated_kwh_so_far": estimated_kwh_so_far,
                "estimated_revenue_so_far": estimated_revenue_so_far,
            }
        )

if not ongoing_rows:
    st.info("Nenhum conector carregando no momento.")
else:

    ongoing_df = pd.DataFrame(ongoing_rows).sort_values(
        "elapsed_minutes", ascending=False
    )

    st.dataframe(ongoing_df, use_container_width=True, hide_index=True)

    st.caption(
        "⚠️ kWh e receita aqui são estimativas em tempo real (assumindo "
        "potência máxima do conector) — só viram registro definitivo em "
        "'Histórico de sessões' quando o carregamento terminar."
    )


# ---------------------------------------------------------------
# Métricas — sessões por dia
# ---------------------------------------------------------------

st.subheader("Sessões por dia")

if metrics_view.empty:
    st.info("Ainda não há sessões concluídas registradas.")
else:

    chart_data = (
        metrics_view.groupby(["date", "station_id"])["sessions"]
        .sum()
        .reset_index()
        .pivot(index="date", columns="station_id", values="sessions")
        .fillna(0)
    )

    st.bar_chart(chart_data)

    total_sessions = int(metrics_view["sessions"].sum())

    total_revenue = metrics_view["estimated_revenue_brl"].sum()

    total_failed = int(metrics_view["failed_attempts"].sum()) if "failed_attempts" in metrics_view else 0

    col1, col2, col3 = st.columns(3)

    col1.metric("Total de sessões concluídas", total_sessions)

    col2.metric("Receita estimada", f"R$ {total_revenue:,.2f}")

    total_attempts = total_sessions + total_failed

    conversion = (total_sessions / total_attempts * 100) if total_attempts else None

    col3.metric(
        "Tentativas com falha (Preparing)",
        total_failed,
        delta=f"{conversion:.0f}% de conversão" if conversion is not None else None,
        delta_color="off",
    )

    if selected_station == "Todas" and not metrics_view.empty:

        st.caption("Receita estimada por posto")

        revenue_by_station = (
            metrics_view.groupby("station_id")["estimated_revenue_brl"]
            .sum()
            .sort_values(ascending=False)
        )

        revenue_by_station.index = revenue_by_station.index.map(get_station_name)

        st.bar_chart(revenue_by_station)


st.divider()


# ---------------------------------------------------------------
# Tabela de sessões
# ---------------------------------------------------------------

st.subheader("Histórico de sessões")

if sessions_view.empty:
    st.info("Nenhuma sessão registrada ainda.")
else:

    display_df = sessions_view.sort_values("end_time", ascending=False).copy()

    display_df["start_time"] = to_local(display_df["start_time"])
    display_df["end_time"] = to_local(display_df["end_time"])

    if not display_df.empty:
        avg_duration = display_df["duration_minutes"].mean()
        total_kwh = display_df["estimated_kwh"].sum()
        total_rev = display_df["estimated_revenue_brl"].sum()
        st.caption(
            f"Duração média: {avg_duration:.1f} min | "
            f"Energia estimada total: {total_kwh:.1f} kWh | "
            f"Receita estimada total: R$ {total_rev:,.2f}"
        )

    display_df["posto"] = display_df["station_id"].map(get_station_name)

    st.dataframe(display_df, use_container_width=True, hide_index=True)


st.divider()


# ---------------------------------------------------------------
# Tentativas de carregamento com falha (ficaram em "Preparing")
# ---------------------------------------------------------------

st.subheader("⚠️ Tentativas de carregamento com falha")

st.caption(
    "Conector ficou em estado 'Preparing' (autenticação/handshake) e "
    "voltou para outro estado sem começar a carregar. Útil pra "
    "identificar conectores com problema de autenticação/cartão/app."
)

if attempts_view.empty:
    st.info("Nenhuma tentativa com falha registrada. 🎉")
else:

    attempts_by_connector = (
        attempts_view.groupby(["station_id", "connector_id", "connector_name"])
        .size()
        .reset_index(name="falhas")
        .sort_values("falhas", ascending=False)
    )

    attempts_by_connector["posto"] = attempts_by_connector["station_id"].map(
        get_station_name
    )

    st.caption("Ranking de conectores com mais falhas")

    st.dataframe(
        attempts_by_connector[
            ["posto", "station_id", "connector_id", "connector_name", "falhas"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.caption("Histórico completo de tentativas com falha")

    attempts_display = attempts_view.sort_values(
        "prep_end", ascending=False
    ).copy()

    attempts_display["prep_start"] = to_local(attempts_display["prep_start"])
    attempts_display["prep_end"] = to_local(attempts_display["prep_end"])

    attempts_display["posto"] = attempts_display["station_id"].map(get_station_name)

    st.dataframe(attempts_display, use_container_width=True, hide_index=True)