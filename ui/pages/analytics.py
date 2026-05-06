"""Analytics and monitoring dashboard."""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from ui.layout import header, section
from security.middleware import security_middleware
from services.data_service import load_filtered_main_data, compute_filtered_kpis

def analytics_page():
    security_middleware.enforce()
    header("Analytique", "Analyses approfondies des performances énergétiques")
    
    cols = ["timestamp", "station_id", "consommation_kwh", "conso_predite", "economie_rl_kwh", "score_qos", "type_zone", "technologie"]
    df = load_filtered_main_data(cols)
    
    if df.empty:
        st.info("📊 **Données insuffisantes**")
        st.warning("Veuillez importer des données pour afficher les analyses.")
        return
        
    kpi = compute_filtered_kpis(df)
    
    with section("Performance Globale"):
        c1, c2 = st.columns(2)
        
        # Consommation vs Prédiction
        fig_conso = go.Figure()
        df_daily = df.set_index("timestamp").resample("D").mean(numeric_only=True).reset_index()
        fig_conso.add_trace(go.Scatter(x=df_daily["timestamp"], y=df_daily["consommation_kwh"], name="Réel", line=dict(color="#007bff")))
        if "conso_predite" in df_daily.columns:
            fig_conso.add_trace(go.Scatter(x=df_daily["timestamp"], y=df_daily["conso_predite"], name="Prédit", line=dict(dash="dash", color="#6c757d")))
        fig_conso.update_layout(title="Évolution de la consommation (moyenne journalière)", margin=dict(l=0, r=0, t=30, b=0))
        c1.plotly_chart(fig_conso, use_container_width=True)
        
        # Répartition par Zone
        fig_zone = px.pie(df, names="type_zone", values="consommation_kwh", title="Consommation par type de zone")
        fig_zone.update_layout(margin=dict(l=0, r=0, t=30, b=0))
        c2.plotly_chart(fig_zone, use_container_width=True)

    with section("Efficacité et Économies"):
        c1, c2 = st.columns(2)
        
        # Économies cumulées
        df["eco_cum"] = df["economie_rl_kwh"].fillna(0).cumsum()
        fig_eco = px.area(df, x="timestamp", y="eco_cum", title="Économies cumulées (RL)", color_discrete_sequence=["#28a745"])
        fig_eco.update_layout(margin=dict(l=0, r=0, t=30, b=0))
        c1.plotly_chart(fig_eco, use_container_width=True)
        
        # QoS vs Économies
        fig_qos = px.scatter(df.sample(min(1000, len(df))), x="score_qos", y="economie_rl_kwh", color="technologie", 
                             title="Corrélation QoS vs Économies (Echantillon)")
        fig_qos.update_layout(margin=dict(l=0, r=0, t=30, b=0))
        c2.plotly_chart(fig_qos, use_container_width=True)
