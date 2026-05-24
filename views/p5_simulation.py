from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from config.settings import settings
from config.theme import mode_kpi_class
from security.middleware import security_middleware
from services.nb_metrics import effective_economie_kwh
from ui.components import header, kpi_card, section
from ui.formatting import display_text, resolve_row_action
from ui.page_helpers import mode_explanation
from ui.utils import active_filter_label, download_df_button

from views import simulation_common as sim
from views import simulation_ui as sim_ui


def _render_top_bar(stations: list[str]) -> list[str]:
    sim.init_sim_stations(stations)
    sim_ui.render_toolbar_shell()
    c1, c2 = st.columns([2.4, 1])
    with c1:
        st.multiselect("Stations", stations, key="sim_stations", placeholder="Selectionnez une ou plusieurs stations")
    with c2:
        st.date_input("Date du scenario", value=datetime.now().date(), key="sim_date")
    selected = sim.resolve_selected_stations(stations)
    sim_date = st.session_state.get("sim_date") or datetime.now().date()
    n_alerts = len(st.session_state.get("sim_alerts", []))
    n_decisions = len(st.session_state.get("sim_decisions", []))
    head_l, head_r = st.columns([3, 1])
    with head_l:
        sim_ui.status_pills(
            bool(st.session_state.get("sim_running")),
            int(st.session_state.get("sim_tick", 0)),
            int(st.session_state.get("sim_total_ticks") or 0),
            len(selected),
            sim_date,
            n_alerts,
            n_decisions,
        )
    with head_r:
        sim_ui.live_badge(bool(st.session_state.get("sim_running")))
    sim_ui.close_toolbar_shell()
    return selected


def _tab_pilotage(selected_stations: list[str]) -> None:
    sim_base_date, start_hour, num_days = sim.sim_params()

    sim_ui.panel_open("Calendrier et pas de temps")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.slider("Heure de debut", 0, 23, start_hour, key="sim_start_hour")
    with c2:
        st.slider("Nombre de jours", 1, 7, num_days, key="sim_num_days")
    with c3:
        st.select_slider("Pas (heures)", options=[1, 2, 5], value=2, key="sim_speed")
    sim_ui.panel_close()

    sim_ui.panel_open("Detection et lecture automatique")
    c1, c2 = st.columns(2)
    with c1:
        st.slider(
            "Sensibilite anomalies",
            0.5, 2.0, sim.sensitivity(), 0.1, key="sim_anomaly_sensitivity",
            help="Plus la valeur est elevee, plus les alertes sont declenchees.",
        )
    with c2:
        st.checkbox("Lecture automatique", key="sim_auto")
        if st.session_state.get("sim_auto"):
            st.slider("Intervalle (secondes)", 1, 10, int(st.session_state.get("sim_auto_interval", 3)), key="sim_auto_interval")
    sim_ui.panel_close()

    sim_base_date, start_hour, num_days = sim.sim_params()
    sim_ui.panel_open("Commandes")
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
    if b3.button("Reinitialiser", use_container_width=True):
        sim.reset_simulation()
        st.rerun()
    if b4.button("Periode complete", use_container_width=True):
        sim.run_full_period(selected_stations, sim_base_date, start_hour, num_days)
        st.rerun()

    total = int(st.session_state.get("sim_total_ticks") or 0)
    tick = int(st.session_state.get("sim_tick", 0))
    if total > 0:
        st.progress(min(1.0, tick / max(total, 1)), text=f"Progression : {tick} / {total} pas")
    st.markdown(
        '<p class="sim-command-hint">Lancez le scenario puis utilisez Temps reel pour le suivi, '
        "Alertes et Decisions pour le journal operationnel.</p>",
        unsafe_allow_html=True,
    )
    export = st.session_state.get("sim_data")
    if isinstance(export, pd.DataFrame) and not export.empty:
        download_df_button(export, "simulation.csv", "Exporter les donnees")
    sim_ui.panel_close()


def _tab_temps_reel(selected_stations: list[str]) -> None:
    sim_data, latest_all, latest_ts, sim_base_date = sim.latest_snapshot()
    if latest_all.empty:
        sim_ui.empty_state(
            "Simulation non demarree",
            "Configurez le scenario dans Pilotage puis cliquez sur Lancer.",
        )
        return

    n_alerts = len(st.session_state.get("sim_alerts", []))
    n_decisions = len(st.session_state.get("sim_decisions", []))
    sim.status_banner(latest_ts, sim_base_date, n_alerts, n_decisions)

    focus_choices = [s for s in selected_stations if s in set(latest_all["station_id"].astype(str))]
    if not focus_choices:
        focus_choices = sim.clean_station_list(latest_all["station_id"].unique())
    focus = focus_choices[0] if len(focus_choices) == 1 else st.selectbox(
        "Station au focus", focus_choices, key="sim_focus_station",
    )
    row = sim.row_by_station(latest_all, focus)
    scope = latest_all if len(selected_stations) > 1 else latest_all[
        latest_all["station_id"].astype(str) == focus
    ]
    eco = float(effective_economie_kwh(scope).sum())
    conso = float(sim._num(scope, "consommation_kwh", 0).sum())
    mode = display_text(row.get("mode_operation"), "NORMAL")
    action = resolve_row_action(row, prefer_rl=False)

    with section("Indicateurs de l heure"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi_card("Consommation", f"{conso:.2f} kWh", "Periode courante", "blue")
        with c2:
            kpi_card("Economie", f"{eco * settings.PRIX_KWH_TN:.2f} DT", f"{eco:.2f} kWh", "green" if eco > 0 else "gray")
        with c3:
            kpi_card("Mode", mode, "Station focus", mode_kpi_class(mode))
        with c4:
            kpi_card("Alertes", str(n_alerts), "Cumul session", "red" if n_alerts else "gray")

    with section("Decision en cours"):
        sim_ui.render_decision_card(row, action, mode_explanation(row))

    with section("Vue par station"):
        sim.render_station_table(latest_all)

    with section("Courbe horaire"):
        sim.build_chart(sim_data, sim.plot_template(), focus if len(selected_stations) > 1 else None)


def page_simulation():
    security_middleware.enforce()
    header("Simulation", "Cockpit scenario — pilotage, suivi temps reel et journal operationnel")
    st.caption(active_filter_label())
    sim.maybe_autorefresh()

    role = st.session_state.get("role", "")
    stations = sim.station_options(role)
    if not stations:
        st.warning("Aucune station assignee.")
        return

    selected_stations = _render_top_bar(stations)
    sim.process_tick(selected_stations)

    n_alerts = len(st.session_state.get("sim_alerts", []))
    n_decisions = len(st.session_state.get("sim_decisions", []))
    tabs = st.tabs(sim_ui.tab_labels(n_alerts, n_decisions))

    with tabs[0]:
        _tab_pilotage(selected_stations)
    with tabs[1]:
        _tab_temps_reel(selected_stations)
    with tabs[2]:
        _, _, latest_ts, _ = sim.latest_snapshot()
        sim.render_alerts_panel(latest_ts, selected_stations)
    with tabs[3]:
        _, _, latest_ts, _ = sim.latest_snapshot()
        sim.render_decisions_panel(latest_ts, selected_stations)
    with tabs[4]:
        _, latest_all, _, _ = sim.latest_snapshot()
        if latest_all.empty:
            sim_ui.empty_state("Carte indisponible", "Demarrez la simulation pour afficher les modes sur la carte.")
        else:
            with section("Repartition geographique des modes"):
                sim.render_mini_map(latest_all)
