from __future__ import annotations

from datetime import datetime

import pandas as pd

import streamlit as st

from config.settings import settings

from security.middleware import security_middleware

from services.calendar_tn import calendar_label

from services.nb_metrics import effective_economie_kwh

from services.simulation_events import persist_alert_ack

from ui.components import header

from ui.formatting import display_text, resolve_row_action

from ui.page_helpers import mode_explanation

from views import simulation_common as sim

from views import simulation_ui as ui


def _unack_alerts_count() -> int:

    acked = st.session_state.get("sim_ack_refs", set())

    return sum(
        (
            1
            for a in st.session_state.get("sim_alerts") or []
            if a.get("alert_ref") not in acked
        )
    )


def _toolbar(stations: list[str]) -> list[str]:

    c_st, c_date, c_h, c_go, c_pause, c_stop = st.columns(
        [2.9, 1.05, 0.72, 0.68, 0.68, 0.68], vertical_alignment="bottom"
    )

    with c_st:

        sim.render_sim_station_picker(stations)

    with c_date:

        st.date_input("Date", key="sim_date")

    with c_h:

        st.selectbox(
            "Début",
            list(range(24)),
            format_func=lambda h: f"{h:02d}h",
            key="sim_start_hour",
        )

    with c_go:

        start = st.button("Démarrer", type="primary", use_container_width=True)

    with c_pause:

        if st.session_state.get("sim_paused"):

            pause_btn = st.button("Reprendre", use_container_width=True)

        else:

            pause_btn = st.button(
                "Pause",
                use_container_width=True,
                disabled=not st.session_state.get("sim_running"),
            )

    with c_stop:

        stop = st.button("Stop", use_container_width=True)

    selected = sim.resolve_selected_stations(stations)

    base_date, start_hour, num_days = sim.sim_params()

    if start:

        with st.spinner("Démarrage de la simulation (première heure)…"):

            st.session_state.update(
                {
                    "sim_running": True,
                    "sim_paused": False,
                    "sim_tick": 0,
                    "sim_data": pd.DataFrame(),
                    "sim_alerts": [],
                    "sim_decisions": [],
                    "sim_ack_refs": set(),
                    "sim_auto_interval": sim.SIM_AUTO_INTERVAL_DEFAULT_S,
                    "sim_schema_version": sim.SIM_SCHEMA_VERSION,
                }
            )

            st.session_state["sim_total_ticks"] = sim.total_ticks(
                base_date, start_hour, num_days
            )

            st.session_state.pop("_sim_ar_count", None)

            ok = sim.bootstrap_simulation(selected)

            if not ok:

                st.session_state["sim_running"] = False

        st.rerun()

    if pause_btn:

        st.session_state["sim_paused"] = not st.session_state.get("sim_paused")

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

    t["Prédit (kWh)"] = sim._num(t, "conso_predite", 0).round(2)

    t["Écart %"] = sim.ecart_pct_series(t).round(1)

    eco = effective_economie_kwh(t)

    t["Gain (DT)"] = (eco * settings.PRIX_KWH_TN).round(2)

    t["QoS"] = sim._num(t, "score_qos", 0).round(2)

    t["Anomalie"] = sim._num(t, "anomalie_score_ensemble", 0).round(2)

    t["Action"] = t.apply(lambda r: resolve_row_action(r, prefer_rl=True), axis=1)

    return t[
        [
            "Station",
            "Mode",
            "Conso (kWh)",
            "Prédit (kWh)",
            "Écart %",
            "Gain (DT)",
            "QoS",
            "Anomalie",
            "Action",
        ]
    ]


def _alert_button_key(prefix: str, alert_ref: str) -> str:

    safe = alert_ref.replace("|", "_").replace(" ", "_").replace(":", "_")

    return f"{prefix}_{safe}"[:120]


def _ack_sim_alert(ref: str, station_id: str, verdict: str) -> None:

    user = st.session_state.get("username") or st.session_state.get("user", "")

    persist_alert_ack(user, station_id, ref, verdict)

    acked = st.session_state.get("sim_ack_refs", set())

    if not isinstance(acked, set):

        acked = set(acked)

    acked.add(ref)

    st.session_state["sim_ack_refs"] = acked


try:

    _journal_run = st.fragment

except AttributeError:

    def _journal_run(fn):

        return fn


@_journal_run
def _render_journal(selected: list[str], latest_ts) -> None:

    alerts = st.session_state.get("sim_alerts", [])

    decisions = st.session_state.get("sim_decisions", [])

    acked = st.session_state.get("sim_ack_refs", set())

    if not isinstance(acked, set):

        acked = set(acked)

    pending = [a for a in alerts if a.get("alert_ref") not in acked]

    use_full_rerun = not hasattr(st, "fragment")

    if pending:

        st.markdown("**Alertes à vérifier**")

        st.caption(
            "Traité : alerte prise en charge · Ignorer : pas utile / fausse alerte"
        )

        for item in pending[-6:]:

            st.warning(f"**{item.get('station_id')}** — {item.get('message', '')}")

            ref = str(item.get("alert_ref", ""))

            station_id = str(item.get("station_id", ""))

            x1, x2 = st.columns(2)

            with x1:

                if st.button(
                    "Traité",
                    key=_alert_button_key("aok", ref),
                    use_container_width=True,
                ):

                    _ack_sim_alert(ref, station_id, "acquitte")

                    if use_full_rerun:

                        st.rerun()

            with x2:

                if st.button(
                    "Ignorer",
                    key=_alert_button_key("afp", ref),
                    use_container_width=True,
                ):

                    _ack_sim_alert(ref, station_id, "faux_positif")

                    if use_full_rerun:

                        st.rerun()

    else:

        st.caption("Aucune alerte en attente.")

    if decisions:

        st.markdown("**Actions appliquées**")

        df = pd.DataFrame(decisions).tail(20)

        if "timestamp" in df.columns:

            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%d/%m %H:%M")

        cols = ["timestamp", "station_id", "action", "message"]

        if "economie_kwh" in df.columns:

            df = df.copy()

            df["gain_dt"] = (
                pd.to_numeric(df["economie_kwh"], errors="coerce").fillna(0)
                * settings.PRIX_KWH_TN
            )

            cols.append("gain_dt")

        show = df[cols].rename(
            columns={
                "timestamp": "Heure",
                "station_id": "Station",
                "action": "Action",
                "message": "Detail",
                "gain_dt": "Gain (DT)",
            }
        )

        if "Gain (DT)" in show.columns:

            show["Gain (DT)"] = pd.to_numeric(show["Gain (DT)"], errors="coerce").round(
                2
            )

        st.dataframe(show, use_container_width=True, hide_index=True)

    else:

        st.caption("Aucune action enregistrée pour l'instant.")


def page_simulation():

    security_middleware.enforce()

    header("Simulation", "Parc BTS à une date donnée, heure par heure")

    sim.purge_stale_sim_session()

    if "sim_date" not in st.session_state:

        st.session_state["sim_date"] = sim.default_sim_date()

    sim.ensure_sim_engine()

    role = st.session_state.get("role", "")

    stations = sim.station_options(role)

    if not stations:

        st.warning("Aucune station disponible sur votre périmètre.")

        return

    selected = _toolbar(stations)

    if st.session_state.pop("sim_full_day_request", False):

        day_selected = sim.resolve_selected_stations(stations)

        with st.spinner("Simulation de la journée en cours…"):

            sim.run_full_day_simulation(day_selected)

    with st.expander("Options avancees", expanded=False):

        o1, o2 = st.columns(2)

        with o1:

            st.slider(
                "Durée (jours)",
                1,
                7,
                int(st.session_state.get("sim_num_days", 1)),
                key="sim_num_days",
            )

        with o2:

            st.slider(
                "Intervalle (+1 h)",
                10,
                120,
                int(
                    st.session_state.get(
                        "sim_auto_interval", sim.SIM_AUTO_INTERVAL_DEFAULT_S
                    )
                ),
                5,
                key="sim_auto_interval",
                help="Avance automatique d'une heure toutes les N secondes (pause possible).",
            )

        if st.button(
            "Simuler la journée complète",
            type="secondary",
            use_container_width=True,
            key="sim_full_day_btn",
            help="Exécute toutes les heures de la journée (de l'heure de début à 23h) en une seule fois.",
        ):

            st.session_state["sim_full_day_request"] = True

            st.rerun()

        export = st.session_state.get("sim_data")

        if isinstance(export, pd.DataFrame) and (not export.empty):

            exp_date, _, _ = sim.sim_params()

            sim.render_simulation_exports(export, exp_date, selected)

    sim.maybe_autorefresh()

    sim.process_tick(selected)

    err = st.session_state.get("sim_bootstrap_error") or st.session_state.get(
        "sim_pipeline_error"
    )

    if err:

        st.error(str(err))

    sim_data, latest, latest_ts, sim_date = sim.latest_snapshot()

    if latest.empty:

        ui.empty_state(
            "Prêt à démarrer",
            "Sélectionnez vos stations, la date et l'heure de début, puis cliquez sur Démarrer. La simulation avance d'une heure toutes les 30 secondes (modifiable dans Options avancées). Utilisez Pause pour interrompre.",
        )

        return

    hour_label = (
        pd.Timestamp(latest_ts).strftime("%H:%M") if latest_ts is not None else "—"
    )

    tick = int(st.session_state.get("sim_tick", 0))

    total = int(st.session_state.get("sim_total_ticks") or 0)

    n_alert = _unack_alerts_count()

    pause_tag = " · **EN PAUSE**" if st.session_state.get("sim_paused") else ""

    if st.session_state.get("sim_running") and (not st.session_state.get("sim_paused")):

        interval = int(
            st.session_state.get("sim_auto_interval", sim.SIM_AUTO_INTERVAL_DEFAULT_S)
        )

        pause_tag = f"{pause_tag} · +1 h / {interval} s"

    st.info(
        f"**{hour_label}** · {calendar_label(sim_date)} · {len(selected)} station(s) · progression {tick}/{total}{pause_tag}"
        if total
        else f"**{hour_label}** · {calendar_label(sim_date)} · {len(selected)} station(s){pause_tag}"
    )

    if total > 0:

        st.progress(min(1.0, tick / max(total, 1)))

    conso = float(sim._num(latest, "consommation_kwh", 0).sum())

    pred = float(sim._num(latest, "conso_predite", 0).sum())

    ecart_net = (conso - pred) / pred * 100 if pred else 0.0

    gain_heure_dt = sim.kwh_to_dt(sim.total_gain_kwh(latest))

    gain_cumul_dt = (
        sim.kwh_to_dt(sim.total_gain_kwh(sim_data)) if not sim_data.empty else 0.0
    )

    gain_cumul_kwh = sim.total_gain_kwh(sim_data) if not sim_data.empty else 0.0

    m1, m2, m3, m4, m5 = st.columns(5)

    m1.metric("Heure simulée", hour_label)

    m2.metric(
        "Conso reseau", f"{conso:.1f} kWh", f"Pred {pred:.1f} · {ecart_net:+.1f} %"
    )

    m3.metric("Gain heure", f"{gain_heure_dt:.2f} DT")

    m4.metric("Gain cumule", f"{gain_cumul_dt:.2f} DT", f"{gain_cumul_kwh:.1f} kWh")

    m5.metric("Alertes ouvertes", str(n_alert))

    st.subheader("État du parc")

    table = _ops_table(latest)

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=min(56 + 36 * len(table), 400),
    )

    station_ids = table["Station"].tolist() if not table.empty else []

    chart_station: str | None = None

    if station_ids:

        chart_station = st.selectbox(
            "Détail d'une station", station_ids, key="sim_detail_station"
        )

        row = sim.row_by_station(latest, chart_station)

        eco_row = float(effective_economie_kwh(pd.DataFrame([row])).iloc[0])

        ecart_row = float(sim.ecart_pct_series(pd.DataFrame([row])).iloc[0])

        ui.decision_block(
            chart_station,
            display_text(row.get("mode_operation"), "NORMAL"),
            resolve_row_action(row, prefer_rl=False),
            mode_explanation(row),
            gain_dt=sim.kwh_to_dt(eco_row),
            gain_kwh=eco_row,
            ecart_pct=ecart_row,
        )

    tab_courbe, tab_journal, tab_carte = st.tabs(["Courbe", "Journal", "Carte"])

    with tab_courbe:

        if sim_data.empty:

            st.caption("Pas encore de données.")

        else:

            sim.build_chart(sim_data, sim.plot_template(), chart_station)

    with tab_journal:

        _render_journal(selected, latest_ts)

    with tab_carte:

        sim.render_mini_map(latest)
