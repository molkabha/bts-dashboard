"""Page NB2 — Anomalies."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import MODE_COLORS, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import load_nb2_network_stats
from ui.components import header, kpi_card, section
from ui.display import PAGE_ANOMALIES
from ui.page_helpers import load_dashboard_df
from ui.utils import active_filter_label


def _detector_rows(nb2_stats: dict) -> pd.DataFrame:
    detecteurs = nb2_stats.get("detecteurs", {})
    if not isinstance(detecteurs, dict):
        return pd.DataFrame()
    skip = {"ensemble", "seuil_ensemble", "threshold_ensemble", "kpi_reseau", "seuil", "threshold", "optimal_threshold"}
    rows = []
    for name, stats in detecteurs.items():
        if name in skip or not isinstance(stats, dict):
            continue
        if not any(k in stats for k in ("pct_test", "pct_anomalies", "seuil")):
            continue
        rows.append({
            "Detecteur": str(name),
            "Anomalies %": stats.get("pct_test", stats.get("pct_anomalies")),
            "Seuil": stats.get("seuil", stats.get("seuil_test")),
        })
    return pd.DataFrame(rows)


def page_anomalies():
    security_middleware.enforce(role="admin")
    header(PAGE_ANOMALIES, "Detecteurs et alertes sur le filtre actif")
    st.caption(active_filter_label())

    df = load_dashboard_df(["ecart_pct", "score_qos", "gouvernorat"])
    if df.empty:
        st.warning("Aucune donnee pour les filtres actifs.")
        return

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    nb2_stats = load_nb2_network_stats()
    seuil = float(nb2_stats.get("seuil_ensemble") or 0.25)
    anom_col = "anomalie_score_ensemble"
    work = df.copy()
    work["_score"] = pd.to_numeric(work.get(anom_col, 0), errors="coerce").fillna(0)
    anom_df = work[work["_score"] > seuil]

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Score moyen", f"{work['_score'].mean():.2f}", "", "orange")
    with c2:
        kpi_card("Alertes", str(len(anom_df)), f"> {seuil:.2f}", "red")
    with c3:
        kpi_card("Stations", str(anom_df["station_id"].nunique()) if not anom_df.empty else "0", "", "blue")

    det_df = _detector_rows(nb2_stats)
    if not det_df.empty:
        with section("Detecteurs"):
            st.dataframe(det_df, width="stretch", hide_index=True)

    with section("Alertes principales"):
        if anom_df.empty:
            st.success("Aucune alerte sur cette periode.")
        else:
            cols = [c for c in ["timestamp", "station_id", "_score", "ecart_pct", "mode_operation"] if c in anom_df.columns]
            show = anom_df[cols].sort_values("_score", ascending=False).head(25)
            show = show.rename(columns={
                "timestamp": "Date",
                "station_id": "Station",
                "_score": "Score",
                "ecart_pct": "Ecart %",
                "mode_operation": "Mode",
            })
            st.dataframe(show, width="stretch", hide_index=True)

    if {"ecart_pct", anom_col}.issubset(work.columns):
        with section("Vue d'ensemble"):
            scatter_df = work.copy()
            scatter_df["ecart_pct"] = pd.to_numeric(scatter_df["ecart_pct"], errors="coerce").fillna(0)
            scatter_df["score"] = pd.to_numeric(scatter_df[anom_col], errors="coerce").fillna(0)
            fig = px.scatter(
                scatter_df,
                x="ecart_pct",
                y="score",
                color="mode_operation" if "mode_operation" in scatter_df.columns else None,
                hover_data=["station_id"] if "station_id" in scatter_df.columns else None,
                labels={"ecart_pct": "Ecart %", "score": "Score"},
                color_discrete_map=MODE_COLORS,
            )
            fig.add_hline(y=seuil, line_dash="dash", line_color="#c8102e")
            fig.update_layout(template=template, height=300, margin=dict(l=0, r=0, t=8, b=0))
            st.plotly_chart(fig, width="stretch")
