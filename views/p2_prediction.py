"""Page NB1 — Prediction de consommation (modeles supervises)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import load_nb1_models_comparison, load_nb1_production_metrics
from ui.components import header, kpi_card, section
from ui.page_helpers import load_dashboard_df
from ui.utils import active_filter_label, session_outputs

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
    header(
        "NB1 — Prediction",
        "Comparaison des modeles supervises et prevision horaire de consommation",
    )

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    outputs = session_outputs()
    nb1 = outputs.get("nb1", {})
    st.caption(active_filter_label())

    models_df = load_nb1_models_comparison()
    prod = load_nb1_production_metrics()
    prod_name = str(prod.get("model", "—"))

    with section("Comparaison des modeles (test NB1)"):
        if models_df.empty:
            st.info("Export `resultats_modeles.json` indisponible — publiez les artefacts NB1.")
        else:
            chart_df = models_df.copy()
            chart_df["R2"] = pd.to_numeric(chart_df["R2"], errors="coerce")
            fig = px.bar(
                chart_df.sort_values("R2"),
                x="R2",
                y="Modele",
                orientation="h",
                color="Modele",
                color_discrete_sequence=px.colors.qualitative.Set2,
                title="Score R2 par modele",
            )
            if "Production" in chart_df.columns:
                prod_models = chart_df.loc[chart_df["Production"], "Modele"].astype(str).tolist()
                for trace, model in zip(fig.data, chart_df.sort_values("R2")["Modele"].astype(str)):
                    if model in prod_models:
                        trace.marker.line = dict(color="#059669", width=3)
            fig.update_layout(template=template, height=max(220, 44 * len(chart_df)), showlegend=False,
                              margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, width="stretch")

            display = models_df.copy()
            for col in ("RMSE", "MAE", "MAPE %"):
                if col in display.columns:
                    display[col] = pd.to_numeric(display[col], errors="coerce").round(4)
            display["R2"] = pd.to_numeric(display["R2"], errors="coerce").round(4)
            st.dataframe(display, width="stretch", hide_index=True)
            st.caption(f"Modele retenu en production : **{prod_name}** (bordure verte sur le graphique).")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Modele prod.", prod_name, "Deploye pour l'inference", "green")
    with k2:
        r2 = prod.get("r2")
        kpi_card("R2 test", f"{float(r2):.3f}" if r2 is not None else "—", prod_name, "blue")
    with k3:
        rmse = prod.get("rmse")
        kpi_card("RMSE", f"{float(rmse):.3f} kWh" if rmse is not None else "—", "Erreur quadratique", "gray")
    with k4:
        mae = prod.get("mae")
        kpi_card("MAE", f"{float(mae):.3f} kWh" if mae is not None else "—", "Erreur absolue", "gray")

    df = load_dashboard_df()
    if df.empty:
        st.warning("Dataset filtre vide — ajustez la barre laterale.")
        return

    stations = sorted(df["station_id"].dropna().unique().astype(str).tolist()) if "station_id" in df.columns else []
    c1, c2 = st.columns(2)
    with c1:
        station = st.selectbox("Station", stations, key="pred_station") if stations else None
    with c2:
        horizon = st.selectbox("Horizon", ["6h", "12h", "24h"], index=2, key="pred_horizon")
    horizon_h = {"6h": 6, "12h": 12, "24h": 24}[horizon]

    with section(f"Reel vs predit ({horizon})"):
        if station and "timestamp" in df.columns:
            sdf = df[df["station_id"].astype(str) == station].sort_values("timestamp").tail(horizon_h * 4)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["consommation_kwh"], name="Reel", line=dict(width=2.5)))
            if "conso_predite" in sdf.columns:
                fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["conso_predite"], name="Predit", line=dict(dash="dot")))
            if {"pred_q10", "pred_q90"}.issubset(sdf.columns):
                fig.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["pred_q90"], line=dict(width=0), showlegend=False))
                fig.add_trace(go.Scatter(
                    x=sdf["timestamp"], y=sdf["pred_q10"], fill="tonexty",
                    fillcolor="rgba(217,119,6,0.15)", line=dict(width=0), name="IC Q10-Q90",
                ))
            fig.update_layout(template=template, height=340, margin=dict(l=0, r=0, t=20, b=0), hovermode="x unified")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Selectionnez une station pour afficher la courbe.")

    with section("Variables les plus influentes (SHAP / importance)"):
        shap_data = nb1.get("feature_importance", nb1.get("shap_values", {}))
        if shap_data:
            items = sorted(shap_data.items(), key=lambda x: abs(float(x[1])), reverse=True)[:8]
            labels = [FEATURE_LABELS_FR.get(k, k) for k, _ in items]
            values = [abs(float(v)) for _, v in items]
            fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker_color="#1e3a8a"))
            fig.update_layout(template=template, yaxis=dict(autorange="reversed"), height=260,
                              margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Importance des variables : cle `feature_importance` dans resultats_modeles.json.")
