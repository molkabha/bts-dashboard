"""Page 8 - Fiche station (admin)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import apply_time_filters, load_nb2_network_stats
from ui.components import header, status_badge
from ui.formatting import display_text, format_dataframe_for_display
from ui.page_helpers import load_dashboard_df
from ui.utils import merged_active_filters


def _apply_station_date_filter(df: pd.DataFrame, date_from, date_to) -> pd.DataFrame:
    if df.empty or not date_from or not date_to or "timestamp" not in df.columns:
        return df
    return apply_time_filters(df, {"date_range": (date_from, date_to)})


def page_station_detail():
    security_middleware.enforce(role="admin")
    if st.button("Retour Carte", key="station_back_nav"):
        st.session_state["_nav_override"] = 1
        st.rerun()

    station_id = st.session_state.get("selected_station_detail")
    if not station_id:
        st.info("Choisissez une station depuis la page Carte.")
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
    mode = display_text(latest.get("mode_operation"), "NORMAL")
    header(
        f"Station {station_id}",
        f"{display_text(latest.get('gouvernorat'), '')} · {display_text(latest.get('technologie'), '')}".strip(" · "),
    )
    status_badge(mode, "error" if mode == "CRITIQUE" else "warning" if mode == "ATTENTION" else "success")

    ts_series = pd.to_datetime(sdf["timestamp"], errors="coerce") if "timestamp" in sdf.columns else pd.Series(dtype="datetime64[ns]")
    ts_min = ts_series.min().date() if not ts_series.dropna().empty else None
    ts_max = ts_series.max().date() if not ts_series.dropna().empty else None
    c1, c2 = st.columns(2)
    with c1:
        date_from = st.date_input("Debut", value=ts_min, key="station_date_from")
    with c2:
        date_to = st.date_input("Fin", value=ts_max, key="station_date_to")
    sdf_view = _apply_station_date_filter(sdf, date_from, date_to)
    if sdf_view.empty:
        st.warning("Aucune mesure sur cette période.")
        return

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    if "timestamp" in sdf_view.columns and "consommation_kwh" in sdf_view.columns:
        chart_df = sdf_view.copy()
        chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"], errors="coerce")
        tmax = chart_df["timestamp"].max()
        week = chart_df[chart_df["timestamp"] >= tmax - pd.Timedelta(days=7)] if pd.notna(tmax) else chart_df
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=week["timestamp"], y=week["consommation_kwh"], name="Réel"))
        if "conso_predite" in week.columns:
            fig.add_trace(go.Scatter(x=week["timestamp"], y=week["conso_predite"], name="Prédit", line=dict(dash="dot")))
        fig.update_layout(template=template, height=280, margin=dict(l=0, r=0, t=8, b=0))
        st.plotly_chart(fig, width="stretch")

    if "anomalie_score_ensemble" in sdf_view.columns:
        seuil = float(load_nb2_network_stats().get("seuil_ensemble") or 0.25)
        scores = pd.to_numeric(sdf_view["anomalie_score_ensemble"], errors="coerce")
        alerts = sdf_view[scores > seuil].sort_values("timestamp", ascending=False).head(8)
        if alerts.empty:
            st.caption("Aucune alerte sur la période.")
        else:
            cols = [c for c in ["timestamp", "anomalie_score_ensemble", "mode_operation"] if c in alerts.columns]
            st.dataframe(format_dataframe_for_display(alerts[cols]), width="stretch", hide_index=True)
