import streamlit as st
import pandas as pd
from security.middleware import security_middleware
from services.data_service import (
    load_top_anomalies, apply_admin_dimension_filters, apply_time_filters
)
from ui.layout import header
from ui.components_filters import render_admin_global_filters
from ui.utils import download_df_button

def admin_anomalies_page():
    security_middleware.enforce()
    header("Anomalies NB2", "Detection non supervisee, stations critiques et alertes reseau")
    
    outputs = st.session_state.get("data", {})
    if not outputs:
        from services.data_service import load_outputs
        outputs = load_outputs()
    nb2 = outputs.get("nb2", {})
    
    if nb2:
        st.dataframe(pd.DataFrame.from_dict(nb2, orient="index").reset_index(names="modele"), width="stretch")
        
    with st.spinner("Lecture du top anomalies NB2..."):
        df_raw = load_top_anomalies(1000)
        
        # Display filter UI
        render_admin_global_filters(df_raw)
        
        df = apply_admin_dimension_filters(df_raw)
        filters = st.session_state.get("admin_time_filters", {})
        if filters:
            df = apply_time_filters(df, {
                "date_range": filters.get("date_range"),
                "hours": filters.get("hours"),
                "months": None, "day_type": "Tous", "days": None
            })
        
    if isinstance(df, pd.DataFrame) and not df.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            stations = sorted(df["station_id"].dropna().unique()) if "station_id" in df.columns else []
            sel_stations = st.multiselect("Stations", stations, default=stations[:20])
        with c2:
            techs = sorted(df["technologie"].dropna().unique()) if "technologie" in df.columns else []
            sel_techs = st.multiselect("Technologies", techs, default=techs)
        with c3:
            min_score = st.slider("Score anomalie minimum", 0.0, 1.0, 0.25, 0.01)
            
        if sel_stations and "station_id" in df.columns:
            df = df[df["station_id"].isin(sel_stations)]
        if sel_techs and "technologie" in df.columns:
            df = df[df["technologie"].isin(sel_techs)]
        if "anomalie_score_ensemble" in df.columns:
            df = df[df["anomalie_score_ensemble"] >= min_score]
            
        cols = [
            "timestamp", "station_id", "technologie", "consommation_kwh", "conso_predite",
            "ecart_pct", "anomalie_score_ensemble", "nb_votes_anomalie", "niveau_anomalie", "type_anomalie"
        ]
        cols = [c for c in cols if c in df.columns]
        
        st.dataframe(df[cols].head(500), width="stretch", hide_index=True)
        download_df_button(df[cols].head(500), "anomalies_nb2_filtrees.csv", "Exporter anomalies")
