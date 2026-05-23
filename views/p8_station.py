"""Page 8 - Fiche station (detail partagee)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import apply_time_filters, load_nb2_network_stats
from ui.components import header, section, status_badge
from ui.page_helpers import load_dashboard_df
from ui.utils import merged_active_filters


def _apply_station_date_filter(df: pd.DataFrame, date_from, date_to) -> pd.DataFrame:
    if df.empty or not date_from or not date_to or "timestamp" not in df.columns:
        return df
    return apply_time_filters(df, {"date_range": (date_from, date_to)})


def _station_alerts_table(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """Build alert history from columns actually present in the station slice."""
    if df.empty:
        return df
    work = df.copy()
    if "anomalie_score_ensemble" in work.columns:
        seuil = float(load_nb2_network_stats().get("seuil_ensemble") or 0.25)
        scores = pd.to_numeric(work["anomalie_score_ensemble"], errors="coerce")
        work = work[scores > seuil]
    if "timestamp" in work.columns:
        work = work.sort_values("timestamp", ascending=False)
    work = work.head(limit)

    display_map = {
        "timestamp": "Horodatage",
        "anomalie_score_ensemble": "Score",
        "nb_votes_anomalie": "Votes",
        "mode_operation": "Mode",
        "score_qos": "QoS",
        "consommation_kwh": "Conso kWh",
    }
    cols = [c for c in display_map if c in work.columns]
    if not cols:
        return work.head(limit)
    return work[cols].rename(columns={c: display_map[c] for c in cols})


def page_station_detail():
    security_middleware.enforce()
    back_index = 1 if st.session_state.get("role") == "admin" else 7
    back_label = "Carte" if back_index == 1 else "Monitoring"
    if st.button(f"Retour — {back_label}", key="station_back_nav"):
        st.session_state["_nav_override"] = back_index
        st.rerun()

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
        st.warning(f"Station {station_id} introuvable pour les filtres actifs.")
        return

    latest = sdf.sort_values("timestamp").iloc[-1] if "timestamp" in sdf.columns else sdf.iloc[-1]
    mode = str(latest.get("mode_operation", "NORMAL"))
    gov = str(latest.get("gouvernorat", "—"))
    tech = str(latest.get("technologie", "—"))

    header(f"Station {station_id}", f"{gov} | {tech}")
    status_badge(mode, "error" if mode == "CRITIQUE" else "warning" if mode == "ATTENTION" else "success")

    with section("Periode d'analyse"):
        c1, c2 = st.columns(2)
        ts_series = pd.to_datetime(sdf["timestamp"], errors="coerce") if "timestamp" in sdf.columns else pd.Series(dtype="datetime64[ns]")
        ts_min = ts_series.min().date() if not ts_series.dropna().empty else None
        ts_max = ts_series.max().date() if not ts_series.dropna().empty else None
        global_range = merged_active_filters().get("date_range")
        if global_range and len(global_range) == 2:
            ts_min = ts_min or global_range[0]
            ts_max = ts_max or global_range[1]
        if "station_date_from" not in st.session_state and ts_min:
            st.session_state["station_date_from"] = ts_min
        if "station_date_to" not in st.session_state and ts_max:
            st.session_state["station_date_to"] = ts_max
        date_kw = {"min_value": ts_min, "max_value": ts_max} if ts_min and ts_max else {}
        with c1:
            date_from = st.date_input("Debut", key="station_date_from", **date_kw)
        with c2:
            date_to = st.date_input("Fin", key="station_date_to", **date_kw)
        sdf_view = _apply_station_date_filter(sdf, date_from, date_to)
        if sdf_view.empty:
            st.warning("Aucune mesure sur la periode selectionnee.")
            return
        st.caption(f"{len(sdf_view):,} mesures · {date_from} → {date_to}")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    with section("Consommation 7 jours + prediction 24h"):
        if "timestamp" in sdf_view.columns and "consommation_kwh" in sdf_view.columns:
            chart_df = sdf_view.copy()
            chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"], errors="coerce")
            tmax = chart_df["timestamp"].max()
            week = chart_df[chart_df["timestamp"] >= tmax - pd.Timedelta(days=7)] if pd.notna(tmax) else chart_df
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
        alert_tbl = _station_alerts_table(sdf_view, limit=10)
        if not alert_tbl.empty:
            st.dataframe(alert_tbl, width="stretch", hide_index=True)
        else:
            st.info("Aucune alerte sur la periode (score anomalie sous le seuil NB2).")

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
