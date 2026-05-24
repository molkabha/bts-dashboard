from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from security.middleware import security_middleware
from services.calendar_tn import calendar_label
from services.data_service import init_db
from services.simulation_events import persist_alert_ack
from ui.components import header
from ui.formatting import display_text, resolve_row_action
from ui.page_helpers import mode_explanation
from ui.utils import active_filter_label, download_df_button

from views import simulation_common as sim
from views import simulation_ui as ui


def _unack_alerts_count() -> int:
    acked = st.session_state.get("sim_ack_refs", set())
    return sum(
        1 for a in (st.session_state.get("sim_alerts") or [])
        if a.get("alert_ref") not in acked
    )


def _toolbar(stations: list[str]) -> list[str]:
    sim.init_sim_stations(stations)
    c1, c2, c3, c4 = st.columns([2.2, 1, 0.7, 1.6])
    with c1:
        st.multiselect("Stations a simuler", stations, key="sim_stations")
    with c2:
        st.date_input("Date", value=datetime.now().date(), key="sim_date")
    with c3:
        st.selectbox(
            "Debut",
            list(range(24)),
            format_func=lambda h: f"{h:02d}h",
            key="sim_start_hour",
        )
    with c4:
        b1, b2, b3 = st.columns(3)
        with b1:
            start = st.button("Demarrer", type="primary", use_container_width=True)
        with b2:
            step = st.button("+1 h", use_container_width=True)
        with b3:
            stop = st.button("Stop", use_container_width=True)

    selected = sim.resolve_selected_stations(stations)
    base_date, start_hour, num_days = sim.sim_params()

    if start:
        st.session_state.update({
            "sim_running": True,
            "sim_tick": 0,
            "sim_data": pd.DataFrame(),
            "sim_alerts": [],
            "sim_decisions": [],
            "sim_ack_refs": set(),
            "sim_advance": True,
        })
        st.session_state["sim_total_ticks"] = sim.total_ticks(base_date, start_hour, num_days)
        st.rerun()
    if step and st.session_state.get("sim_running"):
        st.session_state["sim_advance"] = True
        st.rerun()
    if stop:
        sim.reset_simulation()
        st.rerun()

    return selected


def _ops_table(latest: pd.DataFrame) -> pd.DataFrame:
    if latest.empty:
        return pd.DataFrame()
    t = latest.copy()
    t["Station"] = t["station_id"].astype(str)
    t["Mode"] = t.get("mode_operation", "NORMAL").astype(str)
    t["Conso (kWh)"] = sim._num(t, "consommation_kwh", 0).round(2)
    t["QoS"] = sim._num(t, "score_qos", 0).round(2)
    t["Anomalie"] = sim._num(t, "anomalie_score_ensemble", 0).round(2)
    t["Action"] = t.apply(lambda r: resolve_row_action(r, prefer_rl=True), axis=1)
    return t[["Station", "Mode", "Conso (kWh)", "QoS", "Anomalie", "Action"]]


def _render_journal(selected: list[str], latest_ts) -> None:
    alerts = st.session_state.get("sim_alerts", [])
    decisions = st.session_state.get("sim_decisions", [])
    acked = st.session_state.get("sim_ack_refs", set())

    pending = [a for a in alerts if a.get("alert_ref") not in acked]
    if pending:
        st.markdown("**Alertes a verifier**")
        for item in pending[-6:]:
            st.warning(f"**{item.get('station_id')}** — {item.get('message', '')}")
            ref = item.get("alert_ref", "")
            x1, x2 = st.columns(2)
            with x1:
                if st.button("Acquitter", key=f"aok_{ref}", use_container_width=True):
                    user = st.session_state.get("username") or st.session_state.get("user", "")
                    init_db()
                    persist_alert_ack(user, str(item.get("station_id")), ref, "acquitte")
                    acked.add(ref)
                    st.session_state["sim_ack_refs"] = acked
                    st.rerun()
            with x2:
                if st.button("Faux positif", key=f"afp_{ref}", use_container_width=True):
                    user = st.session_state.get("username") or st.session_state.get("user", "")
                    init_db()
                    persist_alert_ack(user, str(item.get("station_id")), ref, "faux_positif")
                    acked.add(ref)
                    st.session_state["sim_ack_refs"] = acked
                    st.rerun()
    else:
        st.caption("Aucune alerte en attente.")

    if decisions:
        st.markdown("**Actions appliquees**")
        df = pd.DataFrame(decisions).tail(20)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%d/%m %H:%M")
        show = df[["timestamp", "station_id", "action", "message"]].rename(columns={
            "timestamp": "Heure",
            "station_id": "Station",
            "action": "Action",
            "message": "Detail",
        })
        st.dataframe(show, use_container_width=True, hide_index=True)
    else:
        st.caption("Aucune action enregistree pour l instant.")


def page_simulation():
    security_middleware.enforce()
    header(
        "Simulation",
        "Parc BTS a une date donnee, heure par heure",
    )
    st.caption(active_filter_label())
    sim.maybe_autorefresh()

    role = st.session_state.get("role", "")
    stations = sim.station_options(role)
    if not stations:
        st.warning("Aucune station disponible sur votre perimetre.")
        return

    selected = _toolbar(stations)

    with st.expander("Options avancees", expanded=False):
        o1, o2, o3 = st.columns(3)
        with o1:
            st.slider("Duree (jours)", 1, 7, int(st.session_state.get("sim_num_days", 1)), key="sim_num_days")
            st.select_slider("Pas", [1, 2, 5], value=2, key="sim_speed")
        with o2:
            st.slider("Sensibilite anomalies", 0.5, 2.0, sim.sensitivity(), 0.1, key="sim_anomaly_sensitivity")
        with o3:
            st.checkbox("Avance automatique", key="sim_auto")
            if st.session_state.get("sim_auto"):
                st.slider("Intervalle (s)", 1, 10, int(st.session_state.get("sim_auto_interval", 3)), key="sim_auto_interval")
        if st.button("Calculer toute la journee", use_container_width=True):
            d, h, n = sim.sim_params()
            sim.run_full_period(selected, d, h, n)
            st.rerun()
        export = st.session_state.get("sim_data")
        if isinstance(export, pd.DataFrame) and not export.empty:
            download_df_button(export, "simulation.csv", "Telecharger les donnees")

    sim.process_tick(selected)

    _, latest, latest_ts, sim_date = sim.latest_snapshot()
    if latest.empty:
        ui.empty_state(
            "Pret a demarrer",
            "Selectionnez vos stations, la date et l heure de debut, puis cliquez sur Demarrer. "
            "Utilisez +1 h pour avancer dans la journee.",
        )
        return

    hour_label = pd.Timestamp(latest_ts).strftime("%H:%M") if latest_ts is not None else "—"
    tick = int(st.session_state.get("sim_tick", 0))
    total = int(st.session_state.get("sim_total_ticks") or 0)
    n_alert = _unack_alerts_count()

    st.info(
        f"**{hour_label}** · {calendar_label(sim_date)} · "
        f"{len(selected)} station(s) · progression {tick}/{total}" if total else
        f"**{hour_label}** · {calendar_label(sim_date)} · {len(selected)} station(s)"
    )
    if total > 0:
        st.progress(min(1.0, tick / max(total, 1)))

    conso = float(sim._num(latest, "consommation_kwh", 0).sum())

    m1, m2, m3 = st.columns(3)
    m1.metric("Heure simulee", hour_label)
    m2.metric("Consommation reseau", f"{conso:.1f} kWh")
    m3.metric("Alertes ouvertes", str(n_alert))

    st.subheader("Etat du parc")
    table = _ops_table(latest)
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=min(56 + 36 * len(table), 400),
    )

    station_ids = table["Station"].tolist() if not table.empty else []
    if station_ids:
        pick = st.selectbox("Detail d une station", station_ids, key="sim_detail_station")
        row = sim.row_by_station(latest, pick)
        ui.decision_block(
            pick,
            display_text(row.get("mode_operation"), "NORMAL"),
            resolve_row_action(row, prefer_rl=False),
            mode_explanation(row),
        )

    tab_courbe, tab_journal, tab_carte = st.tabs(["Courbe", "Journal", "Carte"])

    with tab_courbe:
        sim_data, _, _, _ = sim.latest_snapshot()
        if sim_data.empty:
            st.caption("Pas encore de donnees.")
        else:
            sim.build_chart(sim_data, sim.plot_template(), None)

    with tab_journal:
        _render_journal(selected, latest_ts)

    with tab_carte:
        sim.render_mini_map(latest)
