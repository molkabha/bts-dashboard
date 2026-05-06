from datetime import datetime, time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from security.middleware import security_middleware
from services.data_service import engineer_assigned_stations, load_station_data
from services.pipeline_service import simulate_nb_pipeline
from services.realtime_generator import generate_realtime_dataset
from ui.layout import header, section
from ui.realtime_api import render_api_response
from ui.utils import download_df_button


def selected_start_time(prefix: str) -> datetime:
    use_now = st.checkbox("Utiliser l'heure actuelle", value=True, key=f"{prefix}_now")
    if use_now:
        return datetime.now().replace(second=0, microsecond=0)
    c1, c2 = st.columns(2)
    with c1:
        day = st.date_input("Date de debut", value=datetime.now().date(), key=f"{prefix}_date")
    with c2:
        hour = st.time_input("Heure de debut", value=time(datetime.now().hour, 0), key=f"{prefix}_time")
    return datetime.combine(day, hour).replace(second=0, microsecond=0)


def engineer_simulation_page(station: str):
    security_middleware.enforce()
    role = st.session_state.get("role")
    if role != "engineer":
        st.error("Acces refuse. Cette page est reservee aux engineers.")
        return
        
    header("API temps reel station", "Snapshot capte a l'instant et dataset exportable")

    if not station:
        st.warning("Veuillez selectionner une station.")
        return

    # Verify engineer is assigned to this station
    assigned_stations = engineer_assigned_stations(st.session_state.get("user", ""))
    if station not in assigned_stations:
        st.error(f"Vous n'avez pas acces a la station {station}. Stations assignees: {', '.join(assigned_stations)}")
        return

    tab_rt, tab_manual = st.tabs(["Flux genere", "Saisie manuelle"])

    with tab_rt:
        st.info("Snapshot type API: mesures captees par la station a l'instant choisi, puis dataset exportable.")
        # Engineers can ONLY simulate their assigned stations
        selectable = [s for s in assigned_stations if s] or [station]
        if station not in selectable:
            selectable = [station]
            
        scope = st.radio(
            "Perimetre simulation",
            ["Station selectionnee", "Plusieurs stations assignees"] if len(selectable) > 1 else ["Station selectionnee"],
            horizontal=True,
        )
        if scope == "Station selectionnee" or len(selectable) <= 1:
            selected_stations = [station]
        else:
            default = [station] if station in selectable else selectable[:1]
            selected_stations = st.multiselect("Stations assignees", selectable, default=default)
        if not selected_stations:
            st.warning("Selectionnez au moins une station.")
            return

        c1, c2, c3 = st.columns(3)
        with c1:
            periods = st.number_input("Points par station", 1, 10080, 1, 1)
        with c2:
            freq_minutes = st.selectbox("Frequence", [5, 10, 15, 30, 60], index=0, format_func=lambda v: f"{v} min")
        with c3:
            seed = st.number_input("Seed", 0, 999999, 42, 1)
        anomaly_rate = st.slider("Taux anomalies", 0.0, 0.40, 0.08, 0.01)
        start_time = selected_start_time("engineer_rt")

        if st.button("Appeler API temps reel", type="primary"):
            df = generate_realtime_dataset(
                selected_stations,
                periods=int(periods),
                anomaly_rate=float(anomaly_rate),
                seed=int(seed),
                start_time=start_time,
                freq_minutes=int(freq_minutes),
            )
            st.session_state["engineer_realtime_result"] = simulate_nb_pipeline(df, source="flux_temps_reel_genere")

        result = st.session_state.get("engineer_realtime_result")
        if isinstance(result, pd.DataFrame) and not result.empty:
            render_api_response(result, station=station)
            section("Dataset recu")
            st.dataframe(result.head(500), width="stretch", hide_index=True)
            download_df_button(result, "dataset_temps_reel_station.csv")

            station_result = result[result["station_id"].astype(str) == str(station)] if "station_id" in result.columns else result
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=station_result.get("timestamp", station_result.index),
                    y=station_result["consommation_kwh"],
                    name="Conso generee",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=station_result.get("timestamp", station_result.index),
                    y=station_result["conso_predite"],
                    name="Prediction NB1",
                )
            )
            st.plotly_chart(fig, width="stretch")

    with tab_manual:
        with st.form("manual_station"):
            c1, c2, c3 = st.columns(3)
            with c1:
                heure = st.slider("Heure", 0, 23, 12)
                technologie = st.selectbox("Technologie", ["2G", "3G", "4G", "4G+"])
                conso = st.number_input("Consommation kWh", 0.0, 50.0, 3.5, 0.1)
            with c2:
                pred = st.number_input("Prediction NB1 kWh", 0.1, 50.0, 3.2, 0.1)
                cpu = st.slider("Charge CPU %", 0.0, 100.0, 45.0)
                qos = st.slider("Score QoS", 0.0, 1.0, 0.82, 0.01)
            with c3:
                voix = st.slider("Taux charge voix", 0.0, 1.0, 0.10, 0.01)
                data = st.slider("Taux charge data", 0.0, 1.0, 0.20, 0.01)
                secteurs = st.number_input("Secteurs actifs", 1, 8, 3)
            submit = st.form_submit_button("Simuler cette heure", type="primary")

        if submit:
            manual = pd.DataFrame(
                [
                    {
                        "station_id": station,
                        "heure": heure,
                        "technologie": technologie,
                        "consommation_kwh": conso,
                        "conso_predite": pred,
                        "charge_cpu_pct": cpu,
                        "score_qos": qos,
                        "optimisation_qos_autorisee": int(qos >= settings.QOS_SEUIL_DEFAULT),
                        "taux_charge_voix": voix,
                        "taux_charge_data": data,
                        "nb_utilisateurs_actifs": 100,
                        "nb_secteurs_actifs": secteurs,
                    }
                ]
            )
            result = simulate_nb_pipeline(manual, source="saisie_manuelle")
            st.dataframe(result, width="stretch", hide_index=True)
            st.info(f"Action recommandee: {result.iloc[0].get('action_proposee')}")
