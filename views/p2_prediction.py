"""Page 2 - Predictions IA (LightGBM)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from config.theme import PLOTLY_LIGHT, PLOTLY_DARK
from security.middleware import security_middleware
from services.data_service import load_nb1_production_metrics
from ui.components import header, kpi_card, section
from ui.page_helpers import load_dashboard_df
from ui.utils import session_outputs

FEATURE_LABELS_FR = {
    "heure": "Heure de la journee",
    "trafic_data_mbps": "Trafic data",
    "taux_charge_data": "Charge data",
    "temperature_ambiante": "Temperature exterieure",
    "charge_cpu_pct": "Charge processeur",
    "taux_charge_voix": "Trafic voix",
    "nb_utilisateurs_actifs": "Utilisateurs actifs",
    "mois": "Saisonnalite mensuelle",
    "jour_semaine": "Jour de la semaine",
    "puissance_emission_dbm": "Puissance emission",
    "humidite_relative_pct": "Humidite",
    "rayonnement_solaire_wm2": "Ensoleillement",
}


def page_prediction():
    security_middleware.enforce()
    header("Predictions IA", "LightGBM — prevision consommation et explicabilite locale")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    outputs = session_outputs()
    nb1 = outputs.get("nb1", {})

    df = load_dashboard_df()
    if df.empty:
        st.warning("Donnees insuffisantes pour l'analyse predictive.")
        return

    stations = sorted(df["station_id"].dropna().unique().astype(str).tolist()) if "station_id" in df.columns else []
    c1, c2 = st.columns(2)
    with c1:
        station = st.selectbox("Station", stations, key="pred_station") if stations else None
    with c2:
        horizon = st.selectbox("Horizon de prediction", ["6h", "12h", "24h"], index=2, key="pred_horizon")
    horizon_h = {"6h": 6, "12h": 12, "24h": 24}[horizon]

    nb1_metrics = load_nb1_production_metrics()
    model_name = str(nb1_metrics.get("model", "LightGBM"))
    best_r2 = nb1_metrics.get("r2")
    best_rmse = nb1_metrics.get("rmse")
    best_mae = nb1_metrics.get("mae")

    k1, k2, k3 = st.columns(3)
    with k1:
        kpi_card("R2", f"{float(best_r2):.3f}" if best_r2 is not None else "—", model_name, "green")
    with k2:
        kpi_card("RMSE", f"{float(best_rmse):.3f} kWh" if best_rmse is not None else "—", "Test NB1", "blue")
    with k3:
        kpi_card("MAE", f"{float(best_mae):.3f} kWh" if best_mae is not None else "—", "Test NB1", "gray")

    with section(f"Courbe predite vs reelle ({horizon})"):
        if station and "timestamp" in df.columns:
            sdf = df[df["station_id"].astype(str) == station].sort_values("timestamp").tail(horizon_h * 4)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["consommation_kwh"], name="Reel", line=dict(width=2.5)))
            if "conso_predite" in sdf.columns:
                fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["conso_predite"], name="Predit", line=dict(dash="dot")))
            if {"pred_q10", "pred_q90"}.issubset(sdf.columns):
                fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["pred_q90"], line=dict(width=0), showlegend=False))
                fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["pred_q10"], fill="tonexty",
                                         fillcolor="rgba(217,119,6,0.15)", line=dict(width=0), name="IC Q10-Q90"))
            fig.update_layout(template=template, height=340, margin=dict(l=0, r=0, t=20, b=0), hovermode="x unified")
            st.plotly_chart(fig, width="stretch")

    with section("Top 5 facteurs (langage metier)"):
        shap_data = nb1.get("feature_importance", nb1.get("shap_values", {}))
        if shap_data:
            items = sorted(shap_data.items(), key=lambda x: abs(float(x[1])), reverse=True)[:5]
            labels = [FEATURE_LABELS_FR.get(k, k) for k, _ in items]
            values = [abs(float(v)) for _, v in items]
            fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker_color="#1e3a8a"))
            fig.update_layout(template=template, yaxis=dict(autorange="reversed"), height=220,
                              margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Importance des variables disponible dans resultats_modeles.json (NB1).")
