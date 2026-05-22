"""Page 5 - Simulation Temps Reel."""

from __future__ import annotations

import html
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import PLOTLY_LIGHT, PLOTLY_DARK
from security.middleware import security_middleware
from services.data_service import available_stations, engineer_assigned_stations
from services.pipeline_service import simulate_nb_pipeline
from services.realtime_generator import generate_realtime_station_data
from ui.components import header, kpi_card, section, live_indicator
from ui.utils import download_df_button


def _gauge(value: float, title: str, min_val: float, max_val: float, suffix: str = "",
           steps: list | None = None) -> go.Figure:
    """Create a Plotly gauge chart."""
    if steps is None:
        steps = [
            {"range": [min_val, min_val + (max_val - min_val) * 0.5], "color": "#ecfdf5"},
            {"range": [min_val + (max_val - min_val) * 0.5, min_val + (max_val - min_val) * 0.8], "color": "#fef3c7"},
            {"range": [min_val + (max_val - min_val) * 0.8, max_val], "color": "#fee2e2"},
        ]
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": suffix, "font": {"size": 22, "family": "Inter"}},
        title={"text": title, "font": {"size": 12, "family": "Inter"}},
        gauge={
            "axis": {"range": [min_val, max_val]},
            "bar": {"color": "#1e3a8a"},
            "steps": steps,
            "threshold": {"line": {"color": "#c8102e", "width": 2}, "value": max_val * 0.85},
        },
    ))
    fig.update_layout(margin=dict(l=10, r=10, t=34, b=4), height=145,
                      paper_bgcolor="rgba(0,0,0,0)", font={"family": "Inter"})
    return fig


def _mode_color(mode: str) -> str:
    return {"ECO": "#059669", "NORMAL": "#2563eb", "ATTENTION": "#d97706", "CRITIQUE": "#c8102e"}.get(mode, "#64748b")


def _numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    value = df[column] if column in df.columns else pd.Series(default, index=df.index)
    return pd.to_numeric(value, errors="coerce").fillna(default)


def _session_summary(sim_data: pd.DataFrame, selected_stations: list[str]):
    """Render session summary KPIs from accumulated simulation data."""
    conso = _numeric_series(sim_data, "consommation_kwh", 0)
    eco_rl = _numeric_series(sim_data, "economie_rl_kwh", 0)
    eco_expert = _numeric_series(sim_data, "economie_estimee_kwh", 0)
    eco_best = eco_rl.where(eco_rl > eco_expert, eco_expert)

    total_conso = conso.sum()
    total_eco = eco_best.sum()
    total_dt = total_eco * settings.PRIX_KWH_TN
    co2_evite_kg = total_eco * settings.FACTEUR_CO2_TN  # kg
    nb_heures = sim_data["timestamp"].nunique() if "timestamp" in sim_data.columns else len(sim_data)
    nb_anomalies = int((_numeric_series(sim_data, "anomalie_score_ensemble", 0) > 0.25).sum())
    qos_moy = _numeric_series(sim_data, "score_qos", 0.82).mean()

    with section("Bilan de la Session"):
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            kpi_card("Consommation Totale", f"{total_conso:.1f} kWh", f"{nb_heures}h simulees", "gray")
        with k2:
            kpi_card("Economie RL", f"{total_eco:.1f} kWh", f"{total_dt:.2f} DT", "green")
        with k3:
            kpi_card("CO2 Evite", f"{co2_evite_kg:.2f} kg", "", "blue")
        with k4:
            anom_text = f"{nb_anomalies} anomalies" if nb_anomalies > 0 else "0 anomalie"
            kpi_card("QoS Moyenne", f"{qos_moy:.2f}", anom_text, "eco" if qos_moy > 0.75 else "danger")

        # Best RL agent
        if "meilleur_agent_rl" in sim_data.columns:
            agent_counts = sim_data["meilleur_agent_rl"].value_counts()
            if not agent_counts.empty:
                agent_labels = {
                    "q_learning": "Q-Learning",
                    "sarsa": "SARSA",
                    "double_q_learning": "Double Q-Learning",
                    "expected_sarsa": "Expected SARSA",
                    "q_learning_adaptatif": "Q-Learning Adaptatif",
                    "sarsa_lambda": "SARSA Lambda",
                    "dyna_q": "Dyna-Q",
                }
                best_name = agent_labels.get(agent_counts.index[0], agent_counts.index[0])
                best_pct = agent_counts.iloc[0] / len(sim_data) * 100
                st.caption(f"Agent RL dominant : **{best_name}** ({best_pct:.0f}% des decisions)")


def page_simulation():
    security_middleware.enforce()
    role = st.session_state.get("role")
    header("Simulation Temps Reel", "Flux BTS simule, decisions et economies en direct")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    stations = available_stations()
    if role != "admin":
        assigned = engineer_assigned_stations()
        stations = [s for s in stations if s in assigned]

    if not stations:
        st.warning("Aucune station assignee disponible.")
        return

    col_ctrl, col_cockpit = st.columns([0.85, 2.15])

    with col_ctrl:
        with section("Panneau de Controle"):
            selected_stations = st.multiselect("Station(s)", stations, key="sim_stations")
            if not selected_stations:
                st.info("Selectionner au moins une station.")
                return

            sim_mode = st.radio("Mode", ["Temps reel", "Date personnalisee"],
                                key="sim_mode", horizontal=True)
            if sim_mode == "Temps reel":
                start_hour = st.slider("Heure de depart", 0, 23, datetime.now().hour, key="sim_start_hour")
                sim_base_date = datetime.now().date()
            else:
                sim_base_date = st.date_input("Date", value=datetime.now().date(), key="sim_date")
                start_hour = st.slider("Heure de depart", 0, 23, 0, key="sim_start_hour_custom")

            speed = st.select_slider("Vitesse", options=[1, 10, 60, 600, 3600],
                                     format_func=lambda x: f"x{x}", key="sim_speed")

            bc1, bc2, bc3 = st.columns(3)
            with bc1:
                btn_start = st.button("Demarrer", type="primary", width="stretch")
            with bc2:
                btn_pause = st.button("Pause", width="stretch")
            with bc3:
                btn_reset = st.button("Reset", width="stretch")

        if btn_reset:
            for k in ["sim_data", "sim_running", "sim_tick"]:
                st.session_state.pop(k, None)
            st.rerun()

        if btn_pause:
            st.session_state["sim_running"] = False

        if btn_start:
            st.session_state["sim_running"] = True
            if "sim_data" not in st.session_state:
                st.session_state["sim_tick"] = 0
                st.session_state["sim_data"] = pd.DataFrame()

        # Event injection (Admin only)
        if role == "admin":
            with st.expander("Injection d'evenements avancee", expanded=False):
                ec1, ec2 = st.columns(2)
                with ec1:
                    if st.button("Pic chaleur", width="stretch", key="inj_heat"):
                        st.session_state["sim_injection"] = "heat"
                    if st.button("Surcharge trafic", width="stretch", key="inj_traffic"):
                        st.session_state["sim_injection"] = "traffic"
                with ec2:
                    if st.button("CPU bloque", width="stretch", key="inj_cpu"):
                        st.session_state["sim_injection"] = "cpu_stuck"
                    if st.button("Coupure electrique", width="stretch", key="inj_power"):
                        st.session_state["sim_injection"] = "power_cut"

        # Export
        sim_data = st.session_state.get("sim_data")
        if isinstance(sim_data, pd.DataFrame) and not sim_data.empty:
            with st.expander("Export session", expanded=False):
                download_df_button(sim_data, "session_simulation.csv", "Exporter CSV")

    with col_cockpit:
        # Generate simulation tick
        if st.session_state.get("sim_running") and selected_stations:
            tick = st.session_state.get("sim_tick", 0)
            start_dt = datetime.combine(sim_base_date, datetime.min.time()).replace(hour=start_hour)
            sim_time = start_dt + timedelta(hours=tick)

            new_data = pd.DataFrame()
            for station in selected_stations:
                st_data = generate_realtime_station_data(
                    station=station, periods=1, anomaly_rate=0.01,
                    seed=int(time.time()) + tick + hash(station) % 1000,
                    start_time=sim_time, freq_minutes=60,
                )
                new_data = pd.concat([new_data, st_data], ignore_index=True)

            # Apply injection
            injection = st.session_state.pop("sim_injection", None)
            if injection and not new_data.empty:
                if injection == "heat":
                    new_data["temperature_ambiante"] += 15
                    new_data["consommation_kwh"] *= 1.4
                elif injection == "traffic":
                    new_data["taux_charge_data"] = np.clip(new_data["taux_charge_data"] * 3, 0, 0.99)
                    new_data["charge_cpu_pct"] = np.clip(new_data["charge_cpu_pct"] * 1.8, 0, 99)
                elif injection == "cpu_stuck":
                    new_data["charge_cpu_pct"] = 95.0
                elif injection == "power_cut":
                    new_data["consommation_kwh"] *= 0.2

            processed = simulate_nb_pipeline(new_data, source="flux_temps_reel_genere")
            existing = st.session_state.get("sim_data", pd.DataFrame())
            if isinstance(existing, pd.DataFrame) and not existing.empty:
                max_rows = 48 * len(selected_stations)
                st.session_state["sim_data"] = pd.concat([existing, processed], ignore_index=True).tail(max_rows)
            else:
                st.session_state["sim_data"] = processed
            st.session_state["sim_tick"] = tick + 1

        sim_data = st.session_state.get("sim_data")
        if isinstance(sim_data, pd.DataFrame) and not sim_data.empty:
            latest_all = sim_data[sim_data["timestamp"] == sim_data["timestamp"].max()]

            # Clock + live indicator
            ts_display = html.escape(str(latest_all.iloc[0].get("timestamp", ""))[:19])
            st.markdown(f'<div class="cockpit-clock">{ts_display}</div>', unsafe_allow_html=True)
            live_indicator()

            # --- Gauges ---
            avg_conso = float(latest_all["consommation_kwh"].sum())
            avg_cpu = float(latest_all["charge_cpu_pct"].mean())
            avg_temp = float(latest_all["temperature_ambiante"].mean())

            g1, g2, g3 = st.columns(3)
            with g1:
                st.plotly_chart(
                    _gauge(
                        avg_conso,
                        "Consommation",
                        0,
                        15 *
                        len(selected_stations),
                        " kWh"),
                    width="stretch")
            with g2:
                st.plotly_chart(_gauge(avg_cpu, "CPU", 0, 100, "%"), width="stretch")
            with g3:
                st.plotly_chart(_gauge(avg_temp, "Temperature", 0, 55, " C"), width="stretch")

            # --- Decision card(s) ---
            for _, row in latest_all.iterrows():
                sid = str(row.get("station_id", ""))
                mode = str(row.get("mode_operation", "NORMAL"))
                action = str(row.get("action_proposee", row.get("action_principale", "Monitoring standard")))
                qos = float(row.get("score_qos", 0.82) or 0.82)
                eco_rl = float(row.get("economie_rl_kwh", 0) or 0)
                eco_exp = float(row.get("economie_estimee_kwh", 0) or 0)
                eco = max(eco_rl, eco_exp)
                best_agent = str(row.get("meilleur_agent_rl", ""))
                nb_votes = int(row.get("nb_votes_anomalie", 0) or 0)
                anom_score = float(row.get("anomalie_score_ensemble", 0) or 0)
                color = _mode_color(mode)

                anomaly_info = f" | Anomalie : {anom_score:.2f} ({nb_votes}/7 detecteurs)" if nb_votes > 0 else ""
                safe_sid = html.escape(sid)
                safe_mode = html.escape(mode)
                safe_action = html.escape(action)
                safe_agent = html.escape(best_agent)
                station_label = f" - {safe_sid}" if len(selected_stations) > 1 else ""

                st.markdown(f"""
<div class="decision-card" style="border-left-color:{color};">
  <div class="dc-mode" style="color:{color};">Mode : {safe_mode}{station_label}</div>
  <div class="dc-action">Action : {safe_action}</div>
  <div class="dc-reason">QoS : {qos:.2f} | CPU : {float(row.get('charge_cpu_pct', 0)):.0f}%{anomaly_info}</div>
  <div class="dc-saving">Economie RL ({safe_agent}) : +{eco:.3f} kWh</div>
</div>""", unsafe_allow_html=True)

            # --- Consumption chart ---
            with section("Evolution Consommation"):
                history = sim_data.copy()
                history["consommation_kwh"] = pd.to_numeric(history["consommation_kwh"], errors="coerce")
                if "economie_rl_kwh" in history.columns:
                    history["economie_rl_kwh"] = pd.to_numeric(history["economie_rl_kwh"], errors="coerce").fillna(0)
                else:
                    history["economie_rl_kwh"] = 0

                agg = history.groupby("timestamp").agg(
                    baseline=("consommation_kwh", "sum"),
                    eco=("economie_rl_kwh", "sum"),
                ).reset_index().tail(24)
                agg["optimise"] = agg["baseline"] - agg["eco"]

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=agg["timestamp"], y=agg["baseline"],
                    name="Baseline (sans IA)", line=dict(color="#94a3b8", width=2),
                ))
                fig.add_trace(go.Scatter(
                    x=agg["timestamp"], y=agg["optimise"],
                    name="Avec IA (RL)", line=dict(color="#059669", width=2.5),
                    fill="tonexty", fillcolor="rgba(5,150,105,0.12)",
                ))
                fig.update_layout(
                    template=template, margin=dict(l=0, r=0, t=10, b=0),
                    height=220, xaxis_title="", yaxis_title="kWh",
                    legend=dict(orientation="h", y=1.12), hovermode="x unified",
                )
                st.plotly_chart(fig, width="stretch")

            # --- Session summary ---
            _session_summary(sim_data, selected_stations)

            # Auto-refresh
            if st.session_state.get("sim_running"):
                delay = max(0.5, 5.0 / speed)
                time.sleep(min(delay, 1.0))
                st.rerun()
        else:
            st.info("Appuyez sur Demarrer pour lancer la simulation.")
