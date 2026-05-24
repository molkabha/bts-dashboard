from __future__ import annotations

import html
from datetime import date, datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import PLOTLY_DARK, PLOTLY_LIGHT, mode_color, mode_kpi_class
from security.middleware import security_middleware
from services.calendar_tn import calendar_context
from services.data_service import engineer_assigned_stations
from services.nb_metrics import effective_economie_kwh, harmonize_nb3_economies
from services.nb_replay import load_replay_source, replay_batch, replay_timestamps
from services.simulation_events import (
    classify_tick_rows,
    events_to_dataframe,
    merge_event_log,
)
from services.synthetic_bts import hourly_snapshot, scenario_timestamps
from ui.components import header, kpi_card
from ui.formatting import display_text, resolve_row_action
from ui.page_helpers import load_dashboard_df, mode_explanation
from ui.utils import active_filter_label, download_df_button


def _num(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def _station_options(role: str) -> list[str]:
    df = load_dashboard_df(["station_id"])
    if df.empty or "station_id" not in df.columns:
        if role == "admin":
            from services.data_service import available_stations
            return available_stations()
        return engineer_assigned_stations()
    stations = sorted(df["station_id"].dropna().astype(str).unique().tolist())
    if role != "admin":
        assigned = {str(s) for s in engineer_assigned_stations()}
        stations = [s for s in stations if s in assigned]
    return stations


def _replay_window(source_df, selected_stations, sim_mode, sim_base_date, start_hour):
    on_date = None
    start_dt = None
    if sim_mode == "Une journee":
        on_date = datetime.combine(sim_base_date, datetime.min.time())
        start_dt = on_date.replace(hour=start_hour)
    elif isinstance(source_df, pd.DataFrame) and "timestamp" in source_df.columns:
        ts = pd.to_datetime(source_df["timestamp"], errors="coerce").dropna()
        if not ts.empty:
            start_dt = ts.min().to_pydatetime()
    return on_date, start_dt


def _total_ticks(
    data_source: str,
    source_df,
    selected_stations,
    sim_mode,
    sim_base_date,
    start_hour,
) -> int:
    if data_source == "Scenario":
        return len(scenario_timestamps(sim_base_date, start_hour))
    on_date, start_dt = _replay_window(source_df, selected_stations, sim_mode, sim_base_date, start_hour)
    stamps = replay_timestamps(
        source_df, selected_stations, start_dt,
        on_date=on_date if sim_mode == "Une journee" else None,
    )
    return len(stamps)


def _advance_scenario(
    selected_stations: list[str],
    sim_base_date: date,
    start_hour: int,
    tick: int,
    steps: int,
) -> pd.DataFrame:
    frames = []
    for step in range(max(1, steps)):
        h = start_hour + tick + step
        if h >= 24:
            break
        batch = hourly_snapshot(sim_base_date, h, selected_stations)
        if not batch.empty:
            frames.append(batch)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _advance_replay(
    source_df,
    selected_stations,
    sim_mode,
    sim_base_date,
    start_hour,
    tick: int,
    steps: int,
) -> pd.DataFrame:
    on_date, start_dt = _replay_window(source_df, selected_stations, sim_mode, sim_base_date, start_hour)
    on_date_arg = on_date if sim_mode == "Une journee" else None
    frames = []
    current_tick = tick
    for _ in range(max(1, steps)):
        processed, _ = replay_batch(
            source_df, selected_stations, current_tick,
            start_dt=start_dt, on_date=on_date_arg,
        )
        if processed.empty:
            break
        frames.append(processed)
        current_tick += 1
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _append_sim_data(processed: pd.DataFrame, max_rows: int) -> None:
    processed = harmonize_nb3_economies(processed)
    existing = st.session_state.get("sim_data", pd.DataFrame())
    if isinstance(existing, pd.DataFrame) and not existing.empty:
        st.session_state["sim_data"] = pd.concat([existing, processed], ignore_index=True).tail(max_rows)
    else:
        st.session_state["sim_data"] = processed


def _record_events(processed: pd.DataFrame) -> None:
    alerts, decisions = classify_tick_rows(processed)
    st.session_state["sim_alerts"] = merge_event_log(
        st.session_state.get("sim_alerts", []), alerts,
    )
    st.session_state["sim_decisions"] = merge_event_log(
        st.session_state.get("sim_decisions", []), decisions,
    )


def _advance_simulation(
    data_source: str,
    source_df,
    selected_stations,
    sim_mode,
    sim_base_date,
    start_hour,
    steps: int,
) -> bool:
    tick = int(st.session_state.get("sim_tick", 0))
    max_rows = 72 * len(selected_stations)

    if data_source == "Scenario":
        if start_hour + tick >= 24:
            st.session_state["sim_running"] = False
            return False
        processed = _advance_scenario(selected_stations, sim_base_date, start_hour, tick, steps)
        if processed.empty:
            st.session_state["sim_running"] = False
            return False
        _append_sim_data(processed, max_rows)
        _record_events(processed)
        hours_done = int(processed["timestamp"].drop_duplicates().shape[0]) if "timestamp" in processed.columns else 1
        st.session_state["sim_tick"] = tick + max(1, hours_done)
        return True

    on_date, start_dt = _replay_window(source_df, selected_stations, sim_mode, sim_base_date, start_hour)
    on_date_arg = on_date if sim_mode == "Une journee" else None
    stamps = replay_timestamps(source_df, selected_stations, start_dt, on_date=on_date_arg)
    if tick >= len(stamps):
        st.session_state["sim_running"] = False
        return False

    processed = _advance_replay(
        source_df, selected_stations, sim_mode, sim_base_date, start_hour, tick, steps,
    )
    if processed.empty:
        st.session_state["sim_running"] = False
        return False
    _append_sim_data(processed, max_rows)
    _record_events(processed)
    st.session_state["sim_tick"] = tick + len(processed["timestamp"].drop_duplicates())
    return True


def _replay_source_df() -> pd.DataFrame:
    cached = st.session_state.get("sim_source_df")
    if isinstance(cached, pd.DataFrame):
        return cached
    source_df = load_replay_source()
    st.session_state["sim_source_df"] = source_df
    return source_df


def _primary_row(latest_all: pd.DataFrame) -> pd.Series:
    if latest_all.empty:
        return pd.Series(dtype=object)
    if len(latest_all) == 1:
        return latest_all.iloc[0]
    prio = {"CRITIQUE": 0, "ATTENTION": 1, "NORMAL": 2, "ECO": 3}
    work = latest_all.copy()
    if "mode_operation" in work.columns:
        work["_p"] = work["mode_operation"].astype(str).map(lambda m: prio.get(m, 9))
        work = work.sort_values("_p")
    return work.iloc[0]


def _render_calendar_banner(sim_base_date: date) -> None:
    ctx = calendar_context(sim_base_date)
    flags = []
    if ctx.get("est_ramadan"):
        flags.append("Ramadan")
    if ctx.get("est_ferie"):
        flags.append("Ferie")
    if ctx.get("est_vendredi"):
        flags.append("Vendredi")
    if ctx.get("est_weekend"):
        flags.append("Week-end")
    label = ", ".join(flags) if flags else "Jour ouvre"
    st.caption(f"{sim_base_date.isoformat()} — {label}")


def _render_alerts_panel() -> None:
    st.subheader("Alertes")
    alerts = events_to_dataframe(st.session_state.get("sim_alerts", []))
    if alerts.empty:
        st.caption("Aucune alerte pour l instant.")
        return
    show = alerts[["timestamp", "station_id", "severity", "message"]].copy()
    show["timestamp"] = show["timestamp"].astype(str).str[:19]
    st.dataframe(show, width="stretch", hide_index=True, height=220)


def _render_decisions_panel() -> None:
    st.subheader("Decisions")
    decisions = events_to_dataframe(st.session_state.get("sim_decisions", []))
    if decisions.empty:
        st.caption("Aucune decision enregistree.")
        return
    show = decisions[["timestamp", "station_id", "mode", "action", "economie_kwh", "message"]].copy()
    show["timestamp"] = show["timestamp"].astype(str).str[:19]
    if "economie_kwh" in show.columns:
        show["economie_kwh"] = pd.to_numeric(show["economie_kwh"], errors="coerce").round(3)
    st.dataframe(show, width="stretch", hide_index=True, height=220)


def page_simulation():
    security_middleware.enforce()
    header("Simulation", "Scenario a date ou replay historique avec journal alertes et decisions")
    st.caption(active_filter_label())

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    role = st.session_state.get("role", "")
    stations = _station_options(role)
    if not stations:
        st.warning("Aucune station assignee.")
        return

    col_ctrl, col_main, col_events = st.columns([1, 2, 1.4])

    with col_ctrl:
        default_pick = [s for s in (st.session_state.get("sim_stations") or stations[:1]) if s in stations] or stations[:1]
        selected_stations = st.multiselect("Stations", stations, default=default_pick, key="sim_stations")
        data_source = st.radio(
            "Source",
            ["Scenario", "Historique"],
            key="sim_data_source",
            horizontal=True,
        )
        sim_mode = "Une journee"
        if data_source == "Historique":
            sim_mode = st.radio("Periode", ["Filtre actif", "Une journee"], key="sim_mode", horizontal=True)

        sim_base_date = datetime.now().date()
        start_hour = 0
        if data_source == "Scenario" or sim_mode == "Une journee":
            sim_base_date = st.date_input("Jour", value=datetime.now().date(), key="sim_date")
            start_hour = st.slider("Heure debut", 0, 23, 0, key="sim_start_hour")
            if data_source == "Scenario":
                _render_calendar_banner(sim_base_date)

        st.select_slider("Pas", options=[1, 2, 5], value=2, key="sim_speed")
        c1, c2, c3 = st.columns(3)
        if c1.button("Lancer", type="primary", use_container_width=True):
            source_df = load_replay_source() if data_source == "Historique" else pd.DataFrame()
            st.session_state.update({
                "sim_running": True,
                "sim_tick": 0,
                "sim_data": pd.DataFrame(),
                "sim_alerts": [],
                "sim_decisions": [],
                "sim_source_df": source_df,
                "sim_advance": True,
            })
            st.session_state["sim_total_ticks"] = _total_ticks(
                data_source, source_df, selected_stations, sim_mode, sim_base_date, start_hour,
            )
        if c2.button("Avancer", use_container_width=True) and st.session_state.get("sim_running"):
            st.session_state["sim_advance"] = True
        if c3.button("Reinitialiser", use_container_width=True):
            for key in (
                "sim_data", "sim_running", "sim_tick", "sim_source_df", "sim_total_ticks",
                "sim_alerts", "sim_decisions",
            ):
                st.session_state.pop(key, None)
            st.rerun()
        total = int(st.session_state.get("sim_total_ticks") or 0)
        tick = int(st.session_state.get("sim_tick", 0))
        if total > 0:
            st.progress(min(1.0, tick / max(total, 1)), text=f"{tick}/{total}")
        sim_export = st.session_state.get("sim_data")
        if isinstance(sim_export, pd.DataFrame) and not sim_export.empty:
            download_df_button(sim_export, "simulation.csv", "Exporter")

    with col_events:
        _render_alerts_panel()
        st.divider()
        _render_decisions_panel()

    with col_main:
        if not selected_stations:
            st.info("Selectionnez au moins une station.")
            return

        if st.session_state.pop("sim_advance", False) and st.session_state.get("sim_running"):
            source_df = _replay_source_df() if data_source == "Historique" else pd.DataFrame()
            _advance_simulation(
                data_source, source_df, selected_stations, sim_mode,
                sim_base_date, start_hour, int(st.session_state.get("sim_speed", 1)),
            )

        sim_data = st.session_state.get("sim_data")
        if not isinstance(sim_data, pd.DataFrame) or sim_data.empty:
            st.info("Lancez la simulation avec le bouton Lancer.")
            return

        sim_data = harmonize_nb3_economies(sim_data)
        latest_ts = sim_data["timestamp"].max()
        latest_all = sim_data[sim_data["timestamp"] == latest_ts]
        row = _primary_row(latest_all)
        eco = float(effective_economie_kwh(latest_all).sum())
        conso = float(_num(latest_all, "consommation_kwh", 0).sum())
        mode = display_text(row.get("mode_operation"), "NORMAL")
        action = resolve_row_action(row, prefer_rl=False)

        st.caption(str(latest_ts)[:19])

        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Conso", f"{conso:.2f} kWh", "", "blue")
        with c2:
            kpi_card("Economie", f"{eco * settings.PRIX_KWH_TN:.2f} DT", f"{eco:.2f} kWh", "green" if eco > 0 else "gray")
        with c3:
            kpi_card("Mode", mode, "", mode_kpi_class(mode))

        color = mode_color(mode)
        st.markdown(
            f"""
<div class="decision-card" style="border-left-color:{color};">
  <div class="dc-mode" style="color:{color};">{html.escape(str(row.get('station_id', '—')))}</div>
  <div class="dc-action">{html.escape(action)}</div>
  <div class="dc-reason">{html.escape(mode_explanation(row))}</div>
</div>""",
            unsafe_allow_html=True,
        )

        hist = sim_data.copy()
        hist["conso"] = _num(hist, "consommation_kwh", 0)
        hist["eco"] = effective_economie_kwh(hist)
        agg = hist.groupby("timestamp", as_index=False).agg(conso=("conso", "sum"), eco=("eco", "sum")).tail(36)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["conso"], name="Mesuree", line=dict(color="#94a3b8")))
        fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["conso"] - agg["eco"], name="Optimisee", line=dict(color="#059669")))
        fig.update_layout(template=template, height=260, margin=dict(l=0, r=0, t=8, b=0))
        st.plotly_chart(fig, width="stretch")
