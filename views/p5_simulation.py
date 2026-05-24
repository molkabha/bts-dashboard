from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from config.settings import settings
from security.middleware import security_middleware
from services.nb_metrics import effective_economie_kwh
from ui.components import header, section
from ui.formatting import display_text, resolve_row_action
from ui.page_helpers import mode_explanation
from ui.utils import active_filter_label, download_df_button

from views import simulation_common as sim
from views import simulation_ui as ui

VIEWS = ["Suivi", "Alertes", "Decisions", "Carte"]


def _sidebar_controls(stations: list[str]) -> list[str]:
    st.markdown('<div class="sim-sidebar-box">', unsafe_allow_html=True)

    ui.sidebar_label("Parc")
    sim.init_sim_stations(stations)
    st.multiselect("Stations", stations, key="sim_stations", label_visibility="collapsed")
    selected = sim.resolve_selected_stations(stations)

    ui.sidebar_divider()
    ui.sidebar_label("Scenario")
    st.date_input("Date", value=datetime.now().date(), key="sim_date", label_visibility="collapsed")
    st.slider("Heure de debut", 0, 23, int(st.session_state.get("sim_start_hour", 0)), key="sim_start_hour")
    st.slider("Duree (jours)", 1, 7, int(st.session_state.get("sim_num_days", 1)), key="sim_num_days")

    ui.sidebar_divider()
    ui.sidebar_label("Avancement")
    st.select_slider("Pas", options=[1, 2, 5], value=2, key="sim_speed", label_visibility="visible")
    st.slider("Sensibilite anomalies", 0.5, 2.0, sim.sensitivity(), 0.1, key="sim_anomaly_sensitivity")
    st.checkbox("Lecture auto", key="sim_auto")
    if st.session_state.get("sim_auto"):
        st.slider("Intervalle (s)", 1, 10, int(st.session_state.get("sim_auto_interval", 3)), key="sim_auto_interval")

    ui.sidebar_divider()
    ui.sidebar_label("Actions")
    sim_base_date, start_hour, num_days = sim.sim_params()

    if st.button("Lancer", type="primary", use_container_width=True):
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

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Avancer", use_container_width=True) and st.session_state.get("sim_running"):
            st.session_state["sim_advance"] = True
            st.rerun()
    with c2:
        if st.button("Reset", use_container_width=True):
            sim.reset_simulation()
            st.rerun()

    if st.button("Periode complete", use_container_width=True):
        sim.run_full_period(selected, sim_base_date, start_hour, num_days)
        st.rerun()

    total = int(st.session_state.get("sim_total_ticks") or 0)
    tick = int(st.session_state.get("sim_tick", 0))
    if total > 0:
        st.progress(min(1.0, tick / max(total, 1)))

    export = st.session_state.get("sim_data")
    if isinstance(export, pd.DataFrame) and not export.empty:
        download_df_button(export, "simulation.csv", "Exporter")

    st.markdown("</div>", unsafe_allow_html=True)
    return selected


def _metrics_strip(selected: list[str]) -> None:
    sim_data, latest_all, latest_ts, sim_base_date = sim.latest_snapshot()
    conso = 0.0
    eco = 0.0
    if not latest_all.empty:
        conso = float(sim._num(latest_all, "consommation_kwh", 0).sum())
        eco = float(effective_economie_kwh(latest_all).sum()) * settings.PRIX_KWH_TN
    ui.kpi_strip(
        bool(st.session_state.get("sim_running")),
        int(st.session_state.get("sim_tick", 0)),
        int(st.session_state.get("sim_total_ticks") or 0),
        len(st.session_state.get("sim_alerts", [])),
        len(st.session_state.get("sim_decisions", [])),
        conso,
        eco,
    )


def _view_suivi(selected: list[str]) -> None:
    sim_data, latest_all, latest_ts, sim_base_date = sim.latest_snapshot()
    if latest_all.empty:
        ui.empty_state(
            "Aucune donnee",
            "Choisissez vos stations a gauche, puis cliquez sur Lancer.",
        )
        return

    focus_choices = [s for s in selected if s in set(latest_all["station_id"].astype(str))]
    if not focus_choices:
        focus_choices = sim.clean_station_list(latest_all["station_id"].unique())

    top_l, top_r = st.columns([1, 1.2])
    with top_l:
        ui.hero_time(latest_ts, sim_base_date)
    with top_r:
        focus = focus_choices[0] if len(focus_choices) == 1 else st.selectbox(
            "Station", focus_choices, key="sim_focus_station", label_visibility="collapsed",
        )
        row = sim.row_by_station(latest_all, focus)
        ui.render_decision_card(row, resolve_row_action(row, prefer_rl=False), mode_explanation(row))

    chart_col, table_col = st.columns([1.55, 1])
    with chart_col:
        with section("Consommation horaire"):
            sim.build_chart(sim_data, sim.plot_template(), focus if len(selected) > 1 else None)
    with table_col:
        with section("Stations"):
            sim.render_station_table(latest_all)


def _view_alertes(selected: list[str]) -> None:
    _, _, latest_ts, _ = sim.latest_snapshot()
    sim.render_alerts_panel(latest_ts, selected)


def _view_decisions(selected: list[str]) -> None:
    _, _, latest_ts, _ = sim.latest_snapshot()
    sim.render_decisions_panel(latest_ts, selected)


def _view_carte() -> None:
    _, latest_all, _, _ = sim.latest_snapshot()
    if latest_all.empty:
        ui.empty_state("Carte vide", "Lancez la simulation pour afficher les modes sur la carte.")
        return
    sim.render_mini_map(latest_all)


def page_simulation():
    security_middleware.enforce()
    header("Simulation", "Scenario energetique par date et suivi operationnel")
    st.caption(active_filter_label())
    sim.maybe_autorefresh()

    role = st.session_state.get("role", "")
    stations = sim.station_options(role)
    if not stations:
        st.warning("Aucune station assignee.")
        return

    col_side, col_main = st.columns([1, 2.85], gap="large")

    with col_side:
        selected = _sidebar_controls(stations)

    with col_main:
        sim.process_tick(selected)
        _metrics_strip(selected)

        view = st.radio(
            "Affichage",
            VIEWS,
            horizontal=True,
            key="sim_view",
            label_visibility="collapsed",
        )

        if view == "Suivi":
            _view_suivi(selected)
        elif view == "Alertes":
            _view_alertes(selected)
        elif view == "Decisions":
            _view_decisions(selected)
        else:
            _view_carte()
