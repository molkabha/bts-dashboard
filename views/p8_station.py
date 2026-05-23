"""Page 8 - Fiche station (detail partagee)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.theme import MODE_COLORS, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import load_top_anomalies
from ui.components import header, section, status_badge
from ui.page_helpers import load_dashboard_df
from ui.utils import apply_current_admin_filters


def page_station_detail():
    security_middleware.enforce()
    station_id = st.session_state.get("selected_station_detail")
    if not station_id:
        st.info("Selectionnez une station depuis la carte ou le tableau du parc.")
        return

    df = load_dashboard_df()
    if df.empty or "station_id" not in df.columns:
        st.warning("Donnees indisponibles.")
        return

    sdf = df[df["station_id"].astype(str) == str(station_id)]
    if sdf.empty:
        st.warning(f"Station {station_id} introuvable.")
        return

    latest = sdf.sort_values("timestamp").iloc[-1] if "timestamp" in sdf.columns else sdf.iloc[-1]
    mode = str(latest.get("mode_operation", "NORMAL"))
    gov = str(latest.get("gouvernorat", "—"))
    tech = str(latest.get("technologie", "—"))

    header(f"Station {station_id}", f"{gov} | {tech}")
    status_badge(mode, "error" if mode == "CRITIQUE" else "warning" if mode == "ATTENTION" else "success")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    with section("Consommation 7 jours + prediction 24h"):
        if "timestamp" in sdf.columns:
            sdf = sdf.copy()
            sdf["timestamp"] = pd.to_datetime(sdf["timestamp"], errors="coerce")
            week = sdf[sdf["timestamp"] >= sdf["timestamp"].max() - pd.Timedelta(days=7)]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=week["timestamp"], y=week["consommation_kwh"], name="Reel"))
            if "conso_predite" in week.columns:
                fig.add_trace(go.Scatter(x=week["timestamp"], y=week["conso_predite"], name="Predit", line=dict(dash="dot")))
            if {"pred_q10", "pred_q90"}.issubset(week.columns):
                fig.add_trace(go.Scatter(x=week["timestamp"], y=week["pred_q90"], line=dict(width=0), showlegend=False))
                fig.add_trace(go.Scatter(x=week["timestamp"], y=week["pred_q10"], fill="tonexty",
                                         fillcolor="rgba(30,58,138,0.12)", line=dict(width=0), name="IC Q10-Q90"))
            fig.update_layout(template=template, height=320, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, width="stretch")

    with section("Historique alertes (10 dernieres)"):
        alerts = apply_current_admin_filters(load_top_anomalies(limit=500))
        if not alerts.empty and "station_id" in alerts.columns:
            sa = alerts[alerts["station_id"].astype(str) == str(station_id)].head(10)
            if not sa.empty:
                st.dataframe(
                    sa[["timestamp", "anomalie_score_ensemble", "mode_operation", "score_qos"]].rename(
                        columns={"anomalie_score_ensemble": "Score", "mode_operation": "Mode", "score_qos": "QoS"}),
                    width="stretch", hide_index=True,
                )
            else:
                st.info("Aucune alerte recente pour cette station.")
        else:
            st.info("Aucune alerte enregistree.")

    with section("Actions rapides"):
        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button("Forcer mode ECO", width="stretch"):
                st.success(f"Mode ECO demande pour {station_id} (simulation).")
        with a2:
            if st.button("Creer ticket maintenance", width="stretch"):
                st.info("Ticket maintenance cree (simulation).")
        with a3:
            if st.button("Comparer a la moyenne gouvernorat", width="stretch"):
                gov_mean = df[df["gouvernorat"] == gov]["consommation_kwh"].mean() if gov != "—" else 0
                st.metric("vs moyenne gouvernorat", f"{float(latest.get('consommation_kwh', 0)):.1f} kWh",
                          f"{float(latest.get('consommation_kwh', 0) - gov_mean):+.1f} kWh")
