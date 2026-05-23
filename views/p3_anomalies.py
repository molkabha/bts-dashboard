"""Page 3 - Detection d'anomalies (NB2)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import PLOTLY_LIGHT, PLOTLY_DARK
from security.middleware import security_middleware
from services.data_service import load_nb2_network_stats
from ui.components import header, kpi_card, section
from ui.page_helpers import load_dashboard_df


def _anomaly_type(score: float, qos: float) -> str:
    if qos < 0.7:
        return "QoS"
    if score > 0.5:
        return "Energetique"
    return "Mixte"


def page_anomalies():
    security_middleware.enforce()
    header("Detection d'anomalies", "Score consensus — vote pondere final")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    df = load_dashboard_df(["ecart_pct", "label_ensemble_score"])
    if df.empty:
        st.warning("Aucune donnee disponible.")
        return

    nb2_stats = load_nb2_network_stats()
    seuil = float(nb2_stats.get("seuil_ensemble") or 0.25)
    pct_reseau = nb2_stats.get("pct_anomalies_reseau")

    anom_col = "anomalie_score_ensemble"
    df = df.copy()
    df["_score"] = pd.to_numeric(df.get(anom_col, 0), errors="coerce").fillna(0)
    anom_df = df[df["_score"] > seuil]

    score_consensus = float(df["_score"].mean())
    k1, k2, k3 = st.columns(3)
    with k1:
        kpi_card("Score consensus", f"{score_consensus:.2f}", "Vote pondere final NB2", "orange")
    with k2:
        kpi_card("Anomalies actives", str(len(anom_df)), f"Seuil NB2 > {seuil:.2f}", "red")
    with k3:
        kpi_card("Stations touchees", str(anom_df["station_id"].nunique()) if not anom_df.empty else "0", "", "blue")

    with section("Scatter operationnel"):
        if {"ecart_pct", anom_col, "mode_operation"}.issubset(df.columns):
            scatter_df = df.copy()
            scatter_df["ecart_pct"] = pd.to_numeric(scatter_df["ecart_pct"], errors="coerce").fillna(0)
            scatter_df["score"] = pd.to_numeric(scatter_df[anom_col], errors="coerce").fillna(0)
            fig = px.scatter(
                scatter_df, x="ecart_pct", y="score", color="mode_operation",
                hover_data=["station_id"],
                labels={"ecart_pct": "Ecart %", "score": "Score anomalie ensemble"},
                title="Ecart consommation vs score anomalie",
                color_discrete_map={"ECO": "#059669", "NORMAL": "#2563eb", "ATTENTION": "#d97706", "CRITIQUE": "#c8102e"},
            )
            fig.update_layout(template=template, height=320, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, width="stretch")

    with section("Timeline anomalies (24h)"):
        if "timestamp" in anom_df.columns and not anom_df.empty:
            ts = anom_df.copy()
            ts["timestamp"] = pd.to_datetime(ts["timestamp"], errors="coerce")
            cutoff = ts["timestamp"].max() - pd.Timedelta(hours=24)
            ts = ts[ts["timestamp"] >= cutoff]
            timeline = ts.groupby(["timestamp", "station_id"])["_score"].max().reset_index()
            fig = px.line(timeline, x="timestamp", y="_score", color="station_id",
                          title="Dernieres 24h par station")
            fig.update_layout(template=template, height=280, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, width="stretch")

    with st.expander("Performance detecteurs (NB2)"):
        detecteurs = nb2_stats.get("detecteurs", {})
        if detecteurs:
            rows = []
            for name, stats in detecteurs.items():
                if isinstance(stats, dict):
                    rows.append({
                        "Detecteur": name,
                        "Anomalies %": stats.get("pct_test", stats.get("pct_anomalies")),
                        "Accord metier %": stats.get("accord_metier_%"),
                    })
            if rows:
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        if pct_reseau is not None:
            st.caption(f"Taux anomalies reseau (NB3 KPI) : {float(pct_reseau):.2f}%")

