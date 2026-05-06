import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from security.middleware import security_middleware
from services.data_service import (
    load_filtered_main_data, station_summary_from_df, apply_admin_dimension_filters,
    apply_station_criticite_filter
)
from ui.layout import header, kpi_card, section
from ui.utils import download_df_button

def admin_stations_page():
    security_middleware.enforce()
    header("Stations", "Inventaire filtre, criticite et details operationnels")
    
    cols = [
        "timestamp", "station_id", "gouvernorat", "type_zone", "technologie",
        "consommation_kwh", "conso_predite", "score_qos", "anomalie_score_ensemble",
        "mode_operation", "economie_rl_kwh"
    ]
    
    df = apply_admin_dimension_filters(load_filtered_main_data(cols))
    
    if df.empty:
        st.warning("Aucune station disponible pour les filtres selectionnes.")
        return
        
    # Use session data for scores if available
    outputs = st.session_state.get("data", {})
    if not outputs:
        scores = apply_station_criticite_filter(station_summary_from_df(df))
    else:
        scores = apply_station_criticite_filter(outputs.get("scores", station_summary_from_df(df)))
    
    if scores.empty:
        st.warning("Aucune station ne correspond a la criticite selectionnee.")
        return
        
    selected = st.selectbox("Station", scores.sort_values("score_criticite", ascending=False)["station_id"].astype(str).tolist())
    
    st.dataframe(scores.sort_values("score_criticite", ascending=False), width="stretch", hide_index=True)
    download_df_button(scores, "inventaire_stations_filtrees.csv", "Exporter stations")
    
    station_df = df[df["station_id"].astype(str) == str(selected)].copy()
    if station_df.empty:
        return
        
    section(f"Detail station: {selected}")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Conso moyenne", f"{station_df['consommation_kwh'].mean():.2f} kWh", selected)
    with c2:
        qos = station_df['score_qos'].mean() if 'score_qos' in station_df.columns else 0
        kpi_card("QoS moyen", f"{qos:.3f}", "NB1/NB2")
    with c3:
        anom = station_df['anomalie_score_ensemble'].mean() if 'anomalie_score_ensemble' in station_df.columns else 0
        kpi_card("Score anomalie", f"{anom:.3f}", "NB2", "orange" if anom > 0.25 else "green")
    with c4:
        eco = station_df["economie_rl_kwh"].fillna(0).sum() if "economie_rl_kwh" in station_df.columns else 0
        kpi_card("Economie RL", f"{eco:,.0f} kWh", "NB3", "green")
        
    sample = station_df.sort_values("timestamp").tail(240) if "timestamp" in station_df.columns else station_df.tail(240)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sample.get("timestamp", sample.index), y=sample["consommation_kwh"], name="Consommation"))
    if "conso_predite" in sample.columns:
        fig.add_trace(go.Scatter(x=sample.get("timestamp", sample.index), y=sample["conso_predite"], name="Prediction NB1"))
    if "anomalie_score_ensemble" in sample.columns:
        fig.add_trace(go.Scatter(x=sample.get("timestamp", sample.index), y=sample["anomalie_score_ensemble"], name="Score NB2", yaxis="y2"))
        fig.update_layout(yaxis2=dict(title="Score", overlaying="y", side="right"))
    st.plotly_chart(fig, width="stretch")
