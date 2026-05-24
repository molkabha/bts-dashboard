from __future__ import annotations

import html
from datetime import datetime

import pandas as pd
import streamlit as st

from config.settings import settings
from config.theme import mode_color, mode_kpi_class
from security.middleware import security_middleware
from services.calendar_tn import calendar_label
from services.nb_metrics import effective_economie_kwh
from ui.components import header, kpi_card
from ui.formatting import display_text, resolve_row_action
from ui.page_helpers import mode_explanation
from ui.utils import active_filter_label, download_df_button

from views import simulation_common as sim


def _render_top_bar(stations: list[str]) -> list[str]:
    sim.init_sim_stations(stations)
    c1, c2, c3 = st.columns([2.2, 1.2, 1])
    with c1:
        st.multiselect("Stations", stations, key="sim_stations")
    with c2:
        st.date_input("Jour", value=datetime.now().date(), key="sim_date")
        d = st.session_state.get("sim_date") or datetime.now().date()
        st.caption(calendar_label(d))
    with c3:
        sim.render_compact_status()
    return sim.resolve_selected_stations(stations)


def _tab_pilotage(selected_stations: list[str]) -> None:
    sim_base_date, start_hour, num_days = sim.sim_params()
    c1, c2 = st.columns(2)
    with c1:
        st.slider("Heure debut", 0, 23, start_hour, key="sim_start_hour")
        st.slider("Nombre de jours", 1, 7, num_days, key="sim_num_days")
    with c2:
        st.slider(
            "Sensibilite anomalies",
            0.5, 2.0, sim.sensitivity(), 0.1, key="sim_anomaly_sensitivity",
        )
        st.select_slider("Pas (heures)", options=[1, 2, 5], value=2, key="sim_speed")
    st.checkbox("Lecture auto", key="sim_auto")
    if st.session_state.get("sim_auto"):
        st.slider("Intervalle (s)", 1, 10, int(st.session_state.get("sim_auto_interval", 3)), key="sim_auto_interval")

    sim_base_date, start_hour, num_days = sim.sim_params()
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("Lancer", type="primary", use_container_width=True):
        st.session_state.update({
            "sim_running": True,
            "sim_tick": 0,
            "sim_data": pd.DataFrame(),
            "sim_alerts": [],
            "sim_decisions": [],
            "sim_ack_refs": set(),
            "sim_advance": True,
        })
        st.session_state["sim_total_ticks"] = sim.total_ticks(sim_base_date, start_hour, num_days)
        st.rerun()
    if b2.button("Avancer", use_container_width=True) and st.session_state.get("sim_running"):
        st.session_state["sim_advance"] = True
        st.rerun()
    if b3.button("Reset", use_container_width=True):
        sim.reset_simulation()
        st.rerun()
    if b4.button("Periode complete", use_container_width=True):
        sim.run_full_period(selected_stations, sim_base_date, start_hour, num_days)
        st.rerun()

    total = int(st.session_state.get("sim_total_ticks") or 0)
    tick = int(st.session_state.get("sim_tick", 0))
    if total > 0:
        st.progress(min(1.0, tick / max(total, 1)), text=f"{tick}/{total}")
    export = st.session_state.get("sim_data")
    if isinstance(export, pd.DataFrame) and not export.empty:
        download_df_button(export, "simulation.csv", "Exporter donnees")


def _tab_temps_reel(selected_stations: list[str]) -> None:
    sim_data, latest_all, latest_ts, sim_base_date = sim.latest_snapshot()
    if latest_all.empty:
        st.info("Lancez la simulation depuis l onglet Pilotage.")
        return

    n_alerts = len(st.session_state.get("sim_alerts", []))
    n_decisions = len(st.session_state.get("sim_decisions", []))
    sim.status_banner(latest_ts, sim_base_date, n_alerts, n_decisions)

    focus_choices = [s for s in selected_stations if s in set(latest_all["station_id"].astype(str))]
    if not focus_choices:
        focus_choices = sim.clean_station_list(latest_all["station_id"].unique())
    focus = focus_choices[0] if len(focus_choices) == 1 else st.selectbox(
        "Station focus", focus_choices, key="sim_focus_station",
    )
    row = sim.row_by_station(latest_all, focus)
    scope = latest_all if len(selected_stations) > 1 else latest_all[
        latest_all["station_id"].astype(str) == focus
    ]
    eco = float(effective_economie_kwh(scope).sum())
    conso = float(sim._num(scope, "consommation_kwh", 0).sum())
    mode = display_text(row.get("mode_operation"), "NORMAL")
    action = resolve_row_action(row, prefer_rl=False)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Conso", f"{conso:.2f} kWh", "", "blue")
    with c2:
        kpi_card("Economie", f"{eco * settings.PRIX_KWH_TN:.2f} DT", f"{eco:.2f} kWh", "green" if eco > 0 else "gray")
    with c3:
        kpi_card("Mode", mode, "", mode_kpi_class(mode))
    with c4:
        kpi_card("Alertes", str(n_alerts), "", "red" if n_alerts else "gray")

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
    sim.render_station_table(latest_all)
    sim.build_chart(sim_data, sim.plot_template(), focus if len(selected_stations) > 1 else None)


def page_simulation():
    security_middleware.enforce()
    header("Simulation", "Pilotage du scenario et suivi operationnel")
    st.caption(active_filter_label())
    sim.maybe_autorefresh()

    role = st.session_state.get("role", "")
    stations = sim.station_options(role)
    if not stations:
        st.warning("Aucune station assignee.")
        return

    selected_stations = _render_top_bar(stations)
    sim.process_tick(selected_stations)

    tab_pilot, tab_live, tab_alerts, tab_dec, tab_map = st.tabs([
        "Pilotage",
        "Temps reel",
        "Alertes",
        "Decisions",
        "Carte",
    ])

    with tab_pilot:
        _tab_pilotage(selected_stations)
    with tab_live:
        _tab_temps_reel(selected_stations)
    with tab_alerts:
        _, _, latest_ts, _ = sim.latest_snapshot()
        sim.render_alerts_panel(latest_ts, selected_stations)
    with tab_dec:
        _, _, latest_ts, _ = sim.latest_snapshot()
        sim.render_decisions_panel(latest_ts, selected_stations)
    with tab_map:
        sim.render_mini_map(sim.latest_snapshot()[1])
