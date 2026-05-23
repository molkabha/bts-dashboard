"""Page NB1 — Prediction."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import load_nb1_models_comparison, load_nb1_production_metrics
from ui.components import header, kpi_card, section
from ui.display import PAGE_PREDICTION
from ui.page_helpers import load_dashboard_df
from ui.utils import active_filter_label, session_outputs

FEATURE_LABELS_FR = {
    "heure": "Heure",
    "trafic_data_mbps": "Trafic data",
    "temperature_ambiante": "Temperature",
    "charge_cpu_pct": "CPU",
    "taux_charge_voix": "Voix",
    "mois": "Mois",
    "jour_semaine": "Jour semaine",
}


def page_prediction():
    security_middleware.enforce(role="admin")
    header(PAGE_PREDICTION, "Modele retenu et courbe reel / predit")
    st.caption(active_filter_label())

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    nb1 = session_outputs().get("nb1", {})
    prod = load_nb1_production_metrics()
    prod_name = str(prod.get("model", "—"))
    r2 = prod.get("r2")
    rmse = prod.get("rmse")

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Modele", prod_name, "", "green")
    with c2:
        kpi_card("R2", f"{float(r2):.3f}" if r2 is not None else "—", "Jeu test", "blue")
    with c3:
        kpi_card("RMSE", f"{float(rmse):.3f} kWh" if rmse is not None else "—", "", "gray")

    models_df = load_nb1_models_comparison()
    with section("Comparaison des modeles"):
        if models_df.empty:
            st.info("Artefact resultats_modeles.json manquant.")
        else:
            chart_df = models_df.copy()
            chart_df["R2"] = pd.to_numeric(chart_df["R2"], errors="coerce")
            fig = px.bar(
                chart_df.sort_values("R2"),
                x="R2",
                y="Modele",
                orientation="h",
                color_discrete_sequence=["#1e3a8a"],
            )
            fig.update_layout(template=template, height=max(200, 40 * len(chart_df)), showlegend=False,
                              margin=dict(l=0, r=0, t=8, b=0))
            st.plotly_chart(fig, width="stretch")

    df = load_dashboard_df()
    if df.empty:
        st.warning("Aucune donnee pour les filtres actifs.")
        return

    stations = sorted(df["station_id"].dropna().unique().astype(str).tolist()) if "station_id" in df.columns else []
    c1, c2 = st.columns([2, 1])
    with c1:
        station = st.selectbox("Station", stations, key="pred_station") if stations else None
    with c2:
        horizon_h = {"6h": 6, "12h": 12, "24h": 24}[st.selectbox("Horizon", ["6h", "12h", "24h"], index=2, key="pred_horizon")]

    with section("Reel vs predit"):
        if station and "timestamp" in df.columns:
            sdf = df[df["station_id"].astype(str) == station].sort_values("timestamp").tail(horizon_h * 4)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["consommation_kwh"], name="Reel"))
            if "conso_predite" in sdf.columns:
                fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["conso_predite"], name="Predit", line=dict(dash="dot")))
            fig.update_layout(template=template, height=300, margin=dict(l=0, r=0, t=8, b=0))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Choisissez une station.")

    shap_data = nb1.get("feature_importance", nb1.get("shap_values", {}))
    if shap_data:
        with section("Variables cles"):
            items = sorted(shap_data.items(), key=lambda x: abs(float(x[1])), reverse=True)[:5]
            labels = [FEATURE_LABELS_FR.get(k, k) for k, _ in items]
            values = [abs(float(v)) for _, v in items]
            fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker_color="#1e3a8a"))
            fig.update_layout(template=template, yaxis=dict(autorange="reversed"), height=200, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, width="stretch")
