import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from security.middleware import security_middleware
from services.data_service import (
    load_station_data, apply_time_filters, engineer_assigned_stations
)
from config.settings import settings
from ui.layout import header, kpi_card
from ui.utils import metric_value

def engineer_monitoring_page(station: str):
    security_middleware.enforce()
    role = st.session_state.get("role")
    if role != "engineer":
        st.error("Acces refuse. Cette page est reservee aux engineers.")
        return
    
    # Verify engineer is assigned to this station
    assigned_stations = engineer_assigned_stations(st.session_state.get("user", ""))
    if station not in assigned_stations:
        st.error(f"Vous n'avez pas acces a la station {station}. Stations assignees: {', '.join(assigned_stations)}")
        return
        
    header("Monitoring station", "NB1 prediction, NB2 anomalie et NB3 decision")
    
    if not station:
        st.warning("Veuillez selectionner une station.")
        return
        
    df_station = load_station_data(station, tuple(settings.SIMULATION_COLUMNS))
    # Apply engineer specific time filters from session state
    filters = st.session_state.get("engineer_time_filters", {})
    if filters:
        df_station = apply_time_filters(df_station, {
            "date_range": filters.get("date_range"),
            "hours": filters.get("hours"),
            "months": None, "day_type": "Tous", "days": None
        })
        
    if df_station.empty:
        st.warning("Aucune donnee disponible pour cette station.")
        return
        
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Station", station, "assignee")
    with c2:
        val = f"{df_station['consommation_kwh'].mean():.2f} kWh" if "consommation_kwh" in df_station.columns else "N/D"
        kpi_card("Conso moyenne", val)
    with c3:
        qos = df_station['score_qos'].mean() if 'score_qos' in df_station.columns else 0
        kpi_card("QoS moyen", f"{qos:.3f}")
    with c4:
        anom = df_station['anomalie_score_ensemble'].mean() if 'anomalie_score_ensemble' in df_station.columns else 0
        kpi_card("Score anomalie", f"{anom:.3f}", color="orange" if anom > 0.25 else "green")
        
    tab_timeline, tab_nb1, tab_nb2, tab_nb3 = st.tabs(["Timeline", "NB1", "NB2", "NB3"])
    
    with tab_timeline:
        sample = df_station.sort_values("timestamp").tail(240) if "timestamp" in df_station.columns else df_station.tail(240)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sample.get("timestamp", sample.index), y=sample["consommation_kwh"], name="Consommation"))
        if "conso_predite" in sample.columns:
            fig.add_trace(go.Scatter(x=sample.get("timestamp", sample.index), y=sample["conso_predite"], name="Prediction NB1"))
        if "anomalie_score_ensemble" in sample.columns:
            fig.add_trace(go.Scatter(x=sample.get("timestamp", sample.index), y=sample["anomalie_score_ensemble"], name="Score NB2", yaxis="y2"))
            fig.update_layout(yaxis2=dict(title="Score NB2", overlaying="y", side="right"))
        st.plotly_chart(fig, width="stretch")
        
    with tab_nb1:
        st.dataframe(df_station[settings.NB1_COLUMNS].sort_values("timestamp", ascending=False).head(500) if all(c in df_station.columns for c in settings.NB1_COLUMNS) else df_station.head(500), width="stretch", hide_index=True)
        
    with tab_nb2:
        if all(c in df_station.columns for c in settings.ANOMALY_COLUMNS):
            st.dataframe(df_station[settings.ANOMALY_COLUMNS].sort_values("anomalie_score_ensemble", ascending=False).head(300), width="stretch", hide_index=True)
        else:
            st.dataframe(df_station.head(300), width="stretch", hide_index=True)
            
    with tab_nb3:
        if all(c in df_station.columns for c in settings.NB3_COLUMNS):
            st.dataframe(df_station[settings.NB3_COLUMNS].sort_values("timestamp", ascending=False).head(500), width="stretch", hide_index=True)
        else:
            st.dataframe(df_station.head(500), width="stretch", hide_index=True)
