from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import (
    PLOTLY_DARK,
    PLOTLY_LIGHT,
    mode_color,
    mode_color_discrete_map,
    mode_kpi_class,
    normalize_mode_key,
)
from services.calendar_tn import calendar_label, scenario_timestamps
from services.data_service import engineer_assigned_stations, init_db
from services.nb_metrics import effective_economie_kwh, harmonize_nb3_economies
from services.simulation_events import (
    classify_tick_rows,
    events_to_dataframe,
    filter_events,
    merge_event_log,
    persist_alert_ack,
)
from services.synthetic_bts import generate_period, hourly_snapshot
from ui.formatting import display_text, resolve_row_action
from ui.page_helpers import get_station_map_data, load_dashboard_df, mode_explanation
from ui.utils import download_df_button

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

_INVALID_STATION = frozenset({"", "none", "nan", "<na>", "null"})
SIM_RESET_KEYS = (
    "sim_data", "sim_running", "sim_tick", "sim_total_ticks",
    "sim_alerts", "sim_decisions", "sim_ack_refs",
    "sim_data_source", "sim_mode", "sim_compare_hist", "sim_source_df",
)


def plot_template() -> str:
    return PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT


def maybe_autorefresh() -> None:
    if st.session_state.get("sim_auto") and st.session_state.get("sim_running") and st_autorefresh:
        interval = int(st.session_state.get("sim_auto_interval", 3)) * 1000
        st_autorefresh(interval=interval, key="sim_autorefresh")


def _num(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def valid_station_id(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if text.lower() in _INVALID_STATION:
        return None
    return text


def clean_station_list(ids) -> list[str]:
    out: list[str] = []
    for raw in ids:
        sid = valid_station_id(raw)
        if sid and sid not in out:
            out.append(sid)
    return sorted(out)


def station_options(role: str) -> list[str]:
    df = load_dashboard_df(["station_id"])
    if df.empty or "station_id" not in df.columns:
        if role == "admin":
            from services.data_service import available_stations
            return clean_station_list(available_stations())
        return clean_station_list(engineer_assigned_stations())
    stations = clean_station_list(df["station_id"].unique())
    if role != "admin":
        assigned = {str(s) for s in engineer_assigned_stations()}
        stations = [s for s in stations if s in assigned]
    return stations


def init_sim_stations(stations: list[str]) -> None:
    default_pick = [s for s in clean_station_list(stations[:1]) if s in stations]
    if "sim_stations" not in st.session_state:
        st.session_state["sim_stations"] = default_pick
        return
    cleaned = [s for s in clean_station_list(st.session_state["sim_stations"]) if s in stations]
    if not cleaned:
        st.session_state["sim_stations"] = default_pick


def resolve_selected_stations(stations: list[str]) -> list[str]:
    default_pick = [s for s in clean_station_list(stations[:1]) if s in stations]
    selected = clean_station_list(st.session_state.get("sim_stations") or [])
    selected = [s for s in selected if s in stations]
    return selected or default_pick


def sim_params() -> tuple[date, int, int]:
    sim_base_date = st.session_state.get("sim_date")
    if sim_base_date is None:
        sim_base_date = datetime.now().date()
    start_hour = int(st.session_state.get("sim_start_hour", 0))
    num_days = int(st.session_state.get("sim_num_days", 1))
    return sim_base_date, start_hour, num_days


def sensitivity() -> float:
    return float(st.session_state.get("sim_anomaly_sensitivity", 1.0))


def total_ticks(sim_base_date: date, start_hour: int, num_days: int) -> int:
    return len(scenario_timestamps(sim_base_date, start_hour, num_days))


def record_events(processed: pd.DataFrame) -> None:
    alerts, decisions = classify_tick_rows(processed, anomaly_sensitivity=sensitivity())
    st.session_state["sim_alerts"] = merge_event_log(st.session_state.get("sim_alerts", []), alerts)
    st.session_state["sim_decisions"] = merge_event_log(st.session_state.get("sim_decisions", []), decisions)


def append_sim_data(processed: pd.DataFrame, max_rows: int) -> None:
    processed = harmonize_nb3_economies(processed)
    existing = st.session_state.get("sim_data", pd.DataFrame())
    if isinstance(existing, pd.DataFrame) and not existing.empty:
        st.session_state["sim_data"] = pd.concat([existing, processed], ignore_index=True).tail(max_rows)
    else:
        st.session_state["sim_data"] = processed


def advance_scenario(
    selected_stations: list[str],
    sim_base_date: date,
    start_hour: int,
    tick: int,
    steps: int,
    num_days: int,
) -> tuple[pd.DataFrame, int]:
    frames = []
    stamps = scenario_timestamps(sim_base_date, start_hour, num_days)
    for step in range(max(1, steps)):
        idx = tick + step
        if idx >= len(stamps):
            break
        ts = stamps[idx]
        batch = hourly_snapshot(
            ts.date(), ts.hour, selected_stations,
            anomaly_sensitivity=sensitivity(),
        )
        if not batch.empty:
            frames.append(batch)
    if not frames:
        return pd.DataFrame(), 0
    return pd.concat(frames, ignore_index=True), len(frames)


def advance_simulation(
    selected_stations: list[str],
    sim_base_date: date,
    start_hour: int,
    steps: int,
    num_days: int,
) -> bool:
    tick = int(st.session_state.get("sim_tick", 0))
    max_rows = max(72, 24 * num_days) * len(selected_stations)
    stamps = scenario_timestamps(sim_base_date, start_hour, num_days)
    if tick >= len(stamps):
        st.session_state["sim_running"] = False
        return False
    processed, n = advance_scenario(
        selected_stations, sim_base_date, start_hour, tick, steps, num_days,
    )
    if processed.empty:
        st.session_state["sim_running"] = False
        return False
    append_sim_data(processed, max_rows)
    record_events(processed)
    st.session_state["sim_tick"] = tick + max(1, n)
    return True


def run_full_period(
    selected_stations: list[str],
    sim_base_date: date,
    start_hour: int,
    num_days: int,
) -> None:
    processed = generate_period(
        sim_base_date, start_hour, num_days, selected_stations,
        anomaly_sensitivity=sensitivity(),
    )
    if processed.empty:
        return
    max_rows = max(72, 24 * num_days) * len(selected_stations)
    st.session_state["sim_data"] = harmonize_nb3_economies(processed).tail(max_rows)
    st.session_state["sim_tick"] = (
        len(processed["timestamp"].drop_duplicates()) if "timestamp" in processed.columns else 0
    )
    st.session_state["sim_running"] = False
    record_events(processed)


def reset_simulation() -> None:
    for key in SIM_RESET_KEYS:
        st.session_state.pop(key, None)


def process_tick(selected_stations: list[str]) -> None:
    sim_base_date, start_hour, num_days = sim_params()
    auto = st.session_state.get("sim_auto") and st.session_state.get("sim_running")
    if st.session_state.pop("sim_advance", False) or auto:
        advance_simulation(
            selected_stations, sim_base_date, start_hour,
            int(st.session_state.get("sim_speed", 1)), num_days,
        )
        if auto and st.session_state.get("sim_running"):
            st.rerun()


def latest_snapshot() -> tuple[pd.DataFrame, pd.DataFrame, object, date]:
    sim_base_date, _, _ = sim_params()
    sim_data = st.session_state.get("sim_data")
    if not isinstance(sim_data, pd.DataFrame) or sim_data.empty:
        return pd.DataFrame(), pd.DataFrame(), None, sim_base_date
    sim_data = harmonize_nb3_economies(sim_data)
    latest_ts = sim_data["timestamp"].max()
    latest_all = sim_data[sim_data["timestamp"] == latest_ts]
    latest_all = latest_all[latest_all["station_id"].map(valid_station_id).notna()]
    return sim_data, latest_all, latest_ts, sim_base_date


def row_by_station(latest_all: pd.DataFrame, station_id: str) -> pd.Series:
    if latest_all.empty:
        return pd.Series(dtype=object)
    hit = latest_all[latest_all["station_id"].astype(str) == str(station_id)]
    if hit.empty:
        return latest_all.iloc[0]
    return hit.iloc[0]


def render_station_table(latest_all: pd.DataFrame) -> None:
    if latest_all.empty:
        return
    work = latest_all.copy()
    work["station_id"] = work["station_id"].map(valid_station_id)
    work = work.dropna(subset=["station_id"])
    work["Mode"] = work.get("mode_operation", "NORMAL").astype(str)
    work["Action"] = work.apply(lambda r: resolve_row_action(r, prefer_rl=True), axis=1)
    work["Conso"] = _num(work, "consommation_kwh", 0).round(2)
    work["QoS"] = _num(work, "score_qos", 0).round(2)
    work["Anomalie"] = _num(work, "anomalie_score_ensemble", 0).round(2)
    cols = ["station_id", "Mode", "Conso", "QoS", "Anomalie", "Action"]
    show = work[[c for c in cols if c in work.columns]]
    st.dataframe(show, width="stretch", hide_index=True, height=min(42 + 35 * len(show), 320))


def event_station_filter_options(selected_stations: list[str], events: list[dict]) -> list[str]:
    from_events = {valid_station_id(e.get("station_id")) for e in events}
    from_events.discard(None)
    return sorted(set(selected_stations) | from_events)


def render_alerts_panel(current_ts, selected_stations: list[str]) -> None:
    from views import simulation_ui as ui

    raw = st.session_state.get("sim_alerts", [])
    station_opts = event_station_filter_options(selected_stations, raw)
    if not station_opts and not raw:
        ui.empty_state("Aucune alerte", "Les alertes apparaitront lorsque le scenario detectera une anomalie.")
        return

    f1, f2, f3, f4 = st.columns(4)
    severities = ["Toutes", "ATTENTION", "CRITIQUE"]
    types = ["Toutes", "anomalie_sans_action", "qos_risque"]
    with f1:
        st_sel = station_opts[0] if len(station_opts) == 1 else st.selectbox(
            "Station", station_opts, key="sim_alert_station",
        )
    with f2:
        sev_sel = st.selectbox("Severite", severities, key="sim_alert_sev")
    with f3:
        type_sel = st.selectbox("Type", types, key="sim_alert_type")
    with f4:
        hour_only = st.checkbox("Heure courante", key="sim_alert_hour_only")

    filtered = filter_events(
        raw,
        station=st_sel,
        severity=sev_sel,
        event_type=type_sel,
        current_hour_only=hour_only,
        current_ts=pd.Timestamp(current_ts) if current_ts is not None else None,
    )
    acked = st.session_state.get("sim_ack_refs", set())
    pending = [e for e in filtered if e.get("alert_ref") not in acked][:12]

    from ui.components import section

    col_pending, col_journal = st.columns([1, 1.2])

    with col_pending:
        with section("A traiter"):
            if not pending:
                st.caption("Rien en attente.")
            for item in pending:
                ui.render_alert_card(item)
                ref = item.get("alert_ref", "")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("Acquitter", key=f"ack_ok_{ref}", use_container_width=True):
                        user = st.session_state.get("username") or st.session_state.get("user", "engineer")
                        init_db()
                        persist_alert_ack(user, str(item.get("station_id")), ref, "acquitte")
                        acked.add(ref)
                        st.session_state["sim_ack_refs"] = acked
                        st.rerun()
                with b2:
                    if st.button("Faux positif", key=f"ack_fp_{ref}", use_container_width=True):
                        user = st.session_state.get("username") or st.session_state.get("user", "engineer")
                        init_db()
                        persist_alert_ack(user, str(item.get("station_id")), ref, "faux_positif")
                        acked.add(ref)
                        st.session_state["sim_ack_refs"] = acked
                        st.rerun()

    df = events_to_dataframe(filtered)
    with col_journal:
        with section("Journal"):
            if df.empty:
                st.caption("Aucune entree.")
            else:
                show = df[["timestamp", "station_id", "severity", "type", "message"]].copy()
                show["timestamp"] = show["timestamp"].astype(str).str[:19]
                st.dataframe(show, width="stretch", hide_index=True, height=360)
                download_df_button(show, "alertes_simulation.csv", "Exporter")


def render_decisions_panel(current_ts, selected_stations: list[str]) -> None:
    from ui.components import section
    from views import simulation_ui as ui

    raw = st.session_state.get("sim_decisions", [])
    station_opts = event_station_filter_options(selected_stations, raw)
    if not station_opts and not raw:
        ui.empty_state("Aucune decision", "Les actions d optimisation s afficheront ici pendant le scenario.")
        return

    f1, f2 = st.columns(2)
    with f1:
        st_sel = station_opts[0] if len(station_opts) == 1 else st.selectbox(
            "Station", station_opts, key="sim_dec_station",
        )
    with f2:
        hour_only = st.checkbox("Heure courante", key="sim_dec_hour_only")

    filtered = filter_events(
        raw,
        station=st_sel,
        current_hour_only=hour_only,
        current_ts=pd.Timestamp(current_ts) if current_ts is not None else None,
    )
    df = events_to_dataframe(filtered)
    if df.empty:
        ui.empty_state("Aucun resultat", "Modifiez les filtres ou avancez la simulation.")
        return
    with section("Journal des decisions"):
        show = df[["timestamp", "station_id", "mode", "action", "economie_kwh", "message"]].copy()
        show["timestamp"] = show["timestamp"].astype(str).str[:19]
        if "economie_kwh" in show.columns:
            show["economie_kwh"] = pd.to_numeric(show["economie_kwh"], errors="coerce").round(3)
        st.dataframe(show, width="stretch", hide_index=True, height=280)
        download_df_button(show, "decisions_simulation.csv", "Exporter decisions")


def build_chart(sim_data: pd.DataFrame, template: str, focus_station: str | None) -> None:
    hist = sim_data.copy()
    hist["conso"] = _num(hist, "consommation_kwh", 0)
    hist["eco"] = effective_economie_kwh(hist)
    hist["pred"] = _num(hist, "conso_predite", hist["conso"])
    if focus_station:
        hist = hist[hist["station_id"].astype(str) == str(focus_station)]
    agg_map = {"conso": ("conso", "sum"), "eco": ("eco", "sum"), "pred": ("pred", "mean")}
    if "pred_q10" in hist.columns:
        agg_map["q10"] = ("pred_q10", "mean")
        agg_map["q90"] = ("pred_q90", "mean")
    agg = hist.groupby("timestamp", as_index=False).agg(**agg_map).tail(48)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["conso"], name="Mesuree", line=dict(color="#94a3b8")))
    if "q10" in agg.columns and "q90" in agg.columns:
        fig.add_trace(go.Scatter(
            x=pd.concat([agg["timestamp"], agg["timestamp"][::-1]]),
            y=pd.concat([agg["q90"], agg["q10"][::-1]]),
            fill="toself",
            fillcolor="rgba(30,58,138,0.12)",
            line=dict(width=0),
            name="Bande Q10-Q90",
            showlegend=True,
        ))
    fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["conso"] - agg["eco"], name="Optimisee", line=dict(color="#059669")))
    if "pred" in agg.columns:
        fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["pred"], name="Predite", line=dict(dash="dot", color="#1e40af")))
    alert_ts = [
        pd.Timestamp(e.get("timestamp"))
        for e in st.session_state.get("sim_alerts", [])
        if e.get("timestamp") is not None
    ]
    for ts in sorted(set(alert_ts))[-12:]:
        fig.add_vline(x=ts, line_width=1, line_dash="dash", line_color="#dc2626", opacity=0.35)
    fig.update_layout(template=template, height=360, margin=dict(l=0, r=0, t=8, b=0))
    st.plotly_chart(fig, width="stretch")


def render_mini_map(latest_all: pd.DataFrame) -> None:
    if latest_all.empty:
        st.info("Aucune donnee cartographique.")
        return
    map_df = get_station_map_data(latest_all)
    if map_df.empty or not {"latitude", "longitude"}.issubset(map_df.columns):
        st.info("Coordonnees GPS indisponibles.")
        return
    plot = map_df.copy()
    if "mode_operation" in latest_all.columns:
        modes = latest_all.set_index("station_id")["mode_operation"]
        plot["mode_actuel"] = plot["station_id"].map(modes).fillna("NORMAL")
    else:
        plot["mode_actuel"] = "NORMAL"
    plot["mode_actuel"] = plot["mode_actuel"].map(lambda m: normalize_mode_key(m) or "NORMAL")
    plot["latitude"] = pd.to_numeric(plot["latitude"], errors="coerce")
    plot["longitude"] = pd.to_numeric(plot["longitude"], errors="coerce")
    plot = plot.dropna(subset=["latitude", "longitude"])
    if plot.empty:
        st.info("Coordonnees GPS invalides.")
        return
    fig = px.scatter_mapbox(
        plot,
        lat="latitude",
        lon="longitude",
        color="mode_actuel",
        hover_name="station_id",
        zoom=5.5,
        center={"lat": plot["latitude"].mean(), "lon": plot["longitude"].mean()},
        color_discrete_map=mode_color_discrete_map(plot["mode_actuel"]),
        height=420,
    )
    fig.update_layout(mapbox_style="carto-positron", margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch")
