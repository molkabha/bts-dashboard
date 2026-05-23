"""Page Simulation — replay horaire (ingenieur)."""

from __future__ import annotations

import html
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import MODE_COLORS, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import engineer_assigned_stations
from services.nb_metrics import effective_economie_kwh, harmonize_nb3_economies
from services.nb_replay import load_replay_source, replay_batch, replay_timestamps
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


def _advance_replay(source_df, selected_stations, sim_mode, sim_base_date, start_hour, steps) -> bool:
    on_date, start_dt = _replay_window(source_df, selected_stations, sim_mode, sim_base_date, start_hour)
    on_date_arg = on_date if sim_mode == "Une journee" else None
    max_rows = 72 * len(selected_stations)
    replay_ok = False

    for _ in range(max(1, steps)):
        tick = int(st.session_state.get("sim_tick", 0))
        processed, _ = replay_batch(
            source_df, selected_stations, tick,
            start_dt=start_dt, on_date=on_date_arg,
        )
        if processed.empty:
            st.session_state["sim_running"] = False
            break
        processed = harmonize_nb3_economies(processed)
        existing = st.session_state.get("sim_data", pd.DataFrame())
        if isinstance(existing, pd.DataFrame) and not existing.empty:
            st.session_state["sim_data"] = pd.concat([existing, processed], ignore_index=True).tail(max_rows)
        else:
            st.session_state["sim_data"] = processed
        st.session_state["sim_tick"] = tick + 1
        replay_ok = True
    return replay_ok


def _replay_source_df() -> pd.DataFrame:
    """Return cached replay source; never use `or` on a DataFrame (ambiguous truth value)."""
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


def page_simulation():
    security_middleware.enforce()
    header("Simulation", "Avancez pas à pas sur vos stations assignées")
    st.caption(active_filter_label())

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    role = st.session_state.get("role", "")
    stations = _station_options(role)
    if not stations:
        st.warning("Aucune station assignée.")
        return

    col_ctrl, col_main = st.columns([1, 2.5])

    with col_ctrl:
        default_pick = [s for s in (st.session_state.get("sim_stations") or stations[:1]) if s in stations] or stations[:1]
        selected_stations = st.multiselect("Stations", stations, default=default_pick, key="sim_stations")
        sim_mode = st.radio("Periode", ["Filtre actif", "Une journee"], key="sim_mode", horizontal=True)
        sim_base_date = datetime.now().date()
        start_hour = 0
        if sim_mode == "Une journee":
            bounds = load_dashboard_df(["timestamp"])
            if not bounds.empty and "timestamp" in bounds.columns:
                ts = pd.to_datetime(bounds["timestamp"], errors="coerce").dropna()
                if not ts.empty:
                    sim_base_date = st.date_input("Jour", value=ts.min().date(), key="sim_date")
            start_hour = st.slider("Heure debut", 0, 23, 0, key="sim_start_hour")
        st.select_slider("Pas", options=[1, 2, 5], value=2, key="sim_speed")
        c1, c2, c3 = st.columns(3)
        if c1.button("Lancer", type="primary", use_container_width=True):
            source_df = load_replay_source()
            st.session_state.update({
                "sim_running": True, "sim_tick": 0, "sim_data": pd.DataFrame(),
                "sim_source_df": source_df, "sim_advance": True,
            })
            on_date, start_dt = _replay_window(source_df, selected_stations, sim_mode, sim_base_date, start_hour)
            st.session_state["sim_total_ticks"] = len(replay_timestamps(
                source_df, selected_stations, start_dt,
                on_date=on_date if sim_mode == "Une journee" else None,
            ))
        if c2.button("Avancer", use_container_width=True) and st.session_state.get("sim_running"):
            st.session_state["sim_advance"] = True
        if c3.button("Réinitialiser", use_container_width=True):
            for key in ("sim_data", "sim_running", "sim_tick", "sim_source_df", "sim_total_ticks"):
                st.session_state.pop(key, None)
            st.rerun()
        total = int(st.session_state.get("sim_total_ticks") or 0)
        tick = int(st.session_state.get("sim_tick", 0))
        if total > 0:
            st.progress(min(1.0, tick / total), text=f"{tick}/{total}")
        sim_export = st.session_state.get("sim_data")
        if isinstance(sim_export, pd.DataFrame) and not sim_export.empty:
            download_df_button(sim_export, "simulation.csv", "Exporter")

    with col_main:
        if not selected_stations:
            st.info("Selectionnez au moins une station.")
            return

        if st.session_state.pop("sim_advance", False) and st.session_state.get("sim_running"):
            source_df = _replay_source_df()
            _advance_replay(
                source_df, selected_stations, sim_mode, sim_base_date, start_hour,
                int(st.session_state.get("sim_speed", 1)),
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
            kpi_card("Mode", mode, "", "eco" if mode == "ECO" else "orange")

        color = MODE_COLORS.get(mode, "#64748b")
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
        fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["conso"], name="Mesurée", line=dict(color="#94a3b8")))
        fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["conso"] - agg["eco"], name="Optimisée", line=dict(color="#059669")))
        fig.update_layout(template=template, height=260, margin=dict(l=0, r=0, t=8, b=0))
        st.plotly_chart(fig, width="stretch")
