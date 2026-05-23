"""Page 6 - Simulation temps reel (replay NB3)."""

from __future__ import annotations

import html
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from config.settings import settings
from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import engineer_assigned_stations, load_nb2_network_stats
from services.nb_metrics import effective_economie_kwh
from services.nb_replay import load_replay_source, replay_batch
from ui.components import header, kpi_card, section, live_indicator
from ui.page_helpers import load_dashboard_df
from ui.utils import active_filter_label, download_df_button


def _gauge(value: float, title: str, min_val: float, max_val: float, suffix: str = "") -> go.Figure:
    safe_val = float(value) if pd.notna(value) else min_val
    safe_val = max(min_val, min(max_val, safe_val))
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=safe_val,
        number={"suffix": suffix, "font": {"size": 22, "family": "Inter"}},
        title={"text": title, "font": {"size": 12, "family": "Inter"}},
        gauge={
            "axis": {"range": [min_val, max_val]},
            "bar": {"color": "#1e3a8a"},
            "steps": [
                {"range": [min_val, min_val + (max_val - min_val) * 0.5], "color": "#ecfdf5"},
                {"range": [min_val + (max_val - min_val) * 0.5, min_val + (max_val - min_val) * 0.8], "color": "#fef3c7"},
                {"range": [min_val + (max_val - min_val) * 0.8, max_val], "color": "#fee2e2"},
            ],
        },
    ))
    fig.update_layout(margin=dict(l=10, r=10, t=34, b=4), height=145,
                      paper_bgcolor="rgba(0,0,0,0)", font={"family": "Inter"})
    return fig


def _mode_color(mode: str) -> str:
    return {"ECO": "#059669", "NORMAL": "#2563eb", "ATTENTION": "#d97706", "CRITIQUE": "#c8102e"}.get(mode, "#64748b")


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


def _session_summary(sim_data: pd.DataFrame) -> None:
    conso = _num(sim_data, "consommation_kwh", 0)
    eco_best = effective_economie_kwh(sim_data)
    total_conso = float(conso.sum())
    total_eco = float(eco_best.sum())
    total_dt = total_eco * settings.PRIX_KWH_TN
    co2_kg = total_eco * settings.FACTEUR_CO2_TN
    nb_heures = int(sim_data["timestamp"].nunique()) if "timestamp" in sim_data.columns else len(sim_data)
    seuil = float(load_nb2_network_stats().get("seuil_ensemble") or 0.25)
    nb_anomalies = int((_num(sim_data, "anomalie_score_ensemble", 0) > seuil).sum())
    qos_moy = float(_num(sim_data, "score_qos", 0.75).mean())

    with section("Bilan de la session"):
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            kpi_card("Consommation totale", f"{total_conso:.1f} kWh", f"{nb_heures} pas horaires", "gray")
        with k2:
            kpi_card("Economie RL", f"{total_eco:.1f} kWh", f"{total_dt:.2f} DT", "green")
        with k3:
            kpi_card("CO2 evite", f"{co2_kg:.2f} kg", "", "blue")
        with k4:
            kpi_card("QoS moyenne", f"{qos_moy:.2f}", f"{nb_anomalies} alertes", "eco" if qos_moy > 0.75 else "danger")


def page_simulation():
    security_middleware.enforce()
    role = st.session_state.get("role", "")
    header("Simulation", "Replay horaire des donnees notebook (NB1/NB2/NB3)")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    st.caption(active_filter_label())

    stations = _station_options(role)
    if not stations:
        st.warning("Aucune station disponible pour les filtres actifs.")
        return

    col_ctrl, col_cockpit = st.columns([0.85, 2.15])

    with col_ctrl:
        with section("Controle"):
            default_pick = st.session_state.get("sim_stations") or stations[:1]
            default_pick = [s for s in default_pick if s in stations] or stations[:1]
            selected_stations = st.multiselect(
                "Station(s)",
                stations,
                default=default_pick,
                key="sim_stations",
            )

            sim_mode = st.radio(
                "Periode",
                ["Toutes les dates filtrees", "Une journee"],
                key="sim_mode",
                horizontal=True,
            )
            sim_base_date = datetime.now().date()
            start_hour = 0
            if sim_mode == "Une journee":
                bounds = load_dashboard_df(["timestamp"])
                if not bounds.empty and "timestamp" in bounds.columns:
                    ts = pd.to_datetime(bounds["timestamp"], errors="coerce").dropna()
                    if not ts.empty:
                        sim_base_date = st.date_input(
                            "Jour",
                            value=ts.min().date(),
                            min_value=ts.min().date(),
                            max_value=ts.max().date(),
                            key="sim_date",
                        )
                else:
                    sim_base_date = st.date_input("Jour", value=datetime.now().date(), key="sim_date")
                start_hour = st.slider("Heure de depart", 0, 23, 0, key="sim_start_hour")

            speed = st.select_slider(
                "Vitesse",
                options=[1, 2, 5, 10],
                value=2,
                format_func=lambda x: f"{x} pas / clic",
                key="sim_speed",
            )
            st.checkbox("Avancement automatique", value=False, key="sim_auto")

            bc1, bc2, bc3 = st.columns(3)
            with bc1:
                btn_start = st.button("Demarrer", type="primary", width="stretch")
            with bc2:
                btn_step = st.button("Pas suivant", width="stretch")
            with bc3:
                btn_reset = st.button("Reset", width="stretch")

            if btn_reset:
                for key in ("sim_data", "sim_running", "sim_tick", "sim_source_df", "sim_injection"):
                    st.session_state.pop(key, None)
                st.rerun()

            if btn_start:
                st.session_state["sim_running"] = True
                st.session_state["sim_tick"] = 0
                st.session_state["sim_data"] = pd.DataFrame()
                st.session_state["sim_source_df"] = load_replay_source()
                st.session_state["sim_advance"] = True

            if btn_step and st.session_state.get("sim_running"):
                st.session_state["sim_advance"] = True

            if role == "admin":
                with st.expander("Injection scenario", expanded=False):
                    if st.button("Pic chaleur", key="inj_heat", width="stretch"):
                        st.session_state["sim_injection"] = "heat"
                    if st.button("Surcharge trafic", key="inj_traffic", width="stretch"):
                        st.session_state["sim_injection"] = "traffic"

            sim_data = st.session_state.get("sim_data")
            if isinstance(sim_data, pd.DataFrame) and not sim_data.empty:
                with st.expander("Export", expanded=False):
                    download_df_button(sim_data, "session_simulation.csv", "Exporter CSV")

    with col_cockpit:
        if not selected_stations:
            st.info("Selectionnez au moins une station dans le panneau de controle.")
            return

        advance_manual = st.session_state.pop("sim_advance", False)
        advance_auto = False
        if st.session_state.get("sim_auto") and st.session_state.get("sim_running"):
            interval_ms = max(800, 350 * int(st.session_state.get("sim_speed", 2)))
            refresh_count = st_autorefresh(interval=interval_ms, key="sim_autorefresh")
            advance_auto = refresh_count > 0

        should_advance = (advance_manual or advance_auto) and st.session_state.get("sim_running")

        if should_advance:
            source_df = st.session_state.get("sim_source_df")
            if not isinstance(source_df, pd.DataFrame) or source_df.empty:
                source_df = load_replay_source()
                st.session_state["sim_source_df"] = source_df

            on_date = None
            start_dt = None
            if sim_mode == "Une journee":
                on_date = datetime.combine(sim_base_date, datetime.min.time())
                start_dt = on_date.replace(hour=start_hour)
            elif isinstance(source_df, pd.DataFrame) and "timestamp" in source_df.columns:
                ts = pd.to_datetime(source_df["timestamp"], errors="coerce").dropna()
                if not ts.empty:
                    start_dt = ts.min().to_pydatetime()

            steps = int(st.session_state.get("sim_speed", 1))
            max_rows = 72 * len(selected_stations)
            injection = st.session_state.get("sim_injection")
            replay_ok = False

            for _ in range(max(1, steps)):
                tick = int(st.session_state.get("sim_tick", 0))
                processed, _ = replay_batch(
                    source_df,
                    selected_stations,
                    tick,
                    start_dt=start_dt,
                    on_date=on_date if sim_mode == "Une journee" else None,
                )
                if processed.empty:
                    st.session_state["sim_running"] = False
                    break

                if injection == "heat":
                    if "temperature_ambiante" in processed.columns:
                        processed["temperature_ambiante"] = _num(processed, "temperature_ambiante", 25) + 15
                    processed["consommation_kwh"] = _num(processed, "consommation_kwh", 0) * 1.3
                elif injection == "traffic":
                    if "charge_cpu_pct" in processed.columns:
                        processed["charge_cpu_pct"] = (_num(processed, "charge_cpu_pct", 0) * 2).clip(0, 99)

                existing = st.session_state.get("sim_data", pd.DataFrame())
                if isinstance(existing, pd.DataFrame) and not existing.empty:
                    st.session_state["sim_data"] = pd.concat(
                        [existing, processed], ignore_index=True,
                    ).tail(max_rows)
                else:
                    st.session_state["sim_data"] = processed
                st.session_state["sim_tick"] = tick + 1
                replay_ok = True

            if injection:
                st.session_state.pop("sim_injection", None)

            if not replay_ok and not st.session_state.get("sim_running"):
                st.warning(
                    "Fin du replay ou aucune mesure pour ces stations / cette date. "
                    "Elargissez les filtres sidebar (dates, gouvernorat)."
                )

        sim_data = st.session_state.get("sim_data")
        if not isinstance(sim_data, pd.DataFrame) or sim_data.empty:
            st.info("Cliquez **Demarrer**, puis **Pas suivant** ou activez l'avancement automatique.")
            return

        if "timestamp" not in sim_data.columns:
            st.warning("Donnees replay sans horodatage.")
            return

        latest_ts = sim_data["timestamp"].max()
        latest_all = sim_data[sim_data["timestamp"] == latest_ts]

        st.markdown(
            f'<div class="cockpit-clock">{html.escape(str(latest_ts)[:19])}</div>',
            unsafe_allow_html=True,
        )
        live_indicator()

        avg_conso = float(_num(latest_all, "consommation_kwh", 0).sum())
        avg_cpu = float(_num(latest_all, "charge_cpu_pct", 0).mean())
        avg_temp = float(_num(latest_all, "temperature_ambiante", 25).mean())

        g1, g2, g3 = st.columns(3)
        with g1:
            st.plotly_chart(_gauge(avg_conso, "Consommation", 0, max(5.0, avg_conso * 1.5), " kWh"), width="stretch")
        with g2:
            st.plotly_chart(_gauge(avg_cpu, "CPU", 0, 100, "%"), width="stretch")
        with g3:
            st.plotly_chart(_gauge(avg_temp, "Temperature", 0, 55, " °C"), width="stretch")

        for _, row in latest_all.iterrows():
            sid = str(row.get("station_id", ""))
            mode = str(row.get("mode_operation", "NORMAL"))
            action = str(row.get("action_proposee", row.get("action_rl", "Supervision")))
            qos = float(row.get("score_qos", 0.75) or 0.75)
            eco = float(effective_economie_kwh(pd.DataFrame([row])).iloc[0])
            color = _mode_color(mode)
            station_label = f" — {html.escape(sid)}" if len(selected_stations) > 1 else ""
            st.markdown(
                f"""
<div class="decision-card" style="border-left-color:{color};">
  <div class="dc-mode" style="color:{color};">Mode : {html.escape(mode)}{station_label}</div>
  <div class="dc-action">Action : {html.escape(action)}</div>
  <div class="dc-reason">QoS : {qos:.2f} | CPU : {float(row.get('charge_cpu_pct', 0) or 0):.0f}%</div>
  <div class="dc-saving">Economie : {eco:.3f} kWh</div>
</div>""",
                unsafe_allow_html=True,
            )

        with section("Evolution consommation"):
            history = sim_data.copy()
            history["consommation_kwh"] = _num(history, "consommation_kwh", 0)
            history["economie_kwh"] = effective_economie_kwh(history)
            agg = history.groupby("timestamp").agg(
                baseline=("consommation_kwh", "sum"),
                eco=("economie_kwh", "sum"),
            ).reset_index().tail(48)
            agg["optimise"] = agg["baseline"] - agg["eco"]

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["baseline"], name="Baseline", line=dict(color="#94a3b8")))
            fig.add_trace(go.Scatter(
                x=agg["timestamp"], y=agg["optimise"], name="Avec optimisation",
                line=dict(color="#059669", width=2.5), fill="tonexty", fillcolor="rgba(5,150,105,0.12)",
            ))
            fig.update_layout(template=template, height=220, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified")
            st.plotly_chart(fig, width="stretch")

        _session_summary(sim_data)
