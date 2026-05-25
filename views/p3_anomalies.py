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
from ui.formatting import format_dataframe_for_display
from ui.page_helpers import load_dashboard_df
from ui.utils import active_filter_label, is_admin


def _detector_rows(nb2_stats: dict) -> pd.DataFrame:
    detecteurs = nb2_stats.get("detecteurs", {})
    if not isinstance(detecteurs, dict):
        return pd.DataFrame()
    skip = {
        "ensemble", "seuil_ensemble", "threshold_ensemble", "kpi_reseau",
        "seuil", "threshold", "optimal_threshold",
    }
    rows = []
    for name, stats in detecteurs.items():
        if name in skip or not isinstance(stats, dict):
            continue
        pct = stats.get("pct_test", stats.get("pct_anomalies"))
        if pct is None:
            continue
        rows.append({
            "Détecteur": str(name),
            "Anomalies %": pct,
        })
    return pd.DataFrame(rows)


def _priority_stations(work: pd.DataFrame, seuil: float, anom_col: str) -> pd.DataFrame:
    from services.data_service import filter_valid_station_rows

    work = filter_valid_station_rows(work)
    if work.empty or "station_id" not in work.columns:
        return pd.DataFrame()
    agg = work.groupby("station_id", as_index=False).agg(
        score=(anom_col, "max"),
        alertes=(anom_col, lambda s: int((pd.to_numeric(s, errors="coerce").fillna(0) > seuil).sum())),
    )
    if "gouvernorat" in work.columns:
        gov = work.groupby("station_id")["gouvernorat"].first()
        agg["gouvernorat"] = agg["station_id"].map(gov)
    if "mode_operation" in work.columns:
        mode = work.sort_values("timestamp").groupby("station_id")["mode_operation"].last() if "timestamp" in work.columns else work.groupby("station_id")["mode_operation"].first()
        agg["mode"] = agg["station_id"].map(mode)
    return agg.sort_values("score", ascending=False).head(15)


def page_anomalies():
    security_middleware.enforce()

    subtitle = "Score × heure et stations prioritaires"
    if not is_admin():
        subtitle = "Surveillance QoS de vos stations (sans scores ML)"
    header(PAGE_ANOMALIES, subtitle)
    st.caption(active_filter_label())

    df = load_dashboard_df(["ecart_pct", "score_qos", "gouvernorat", "heure"])
    if df.empty:
        st.warning("Aucune donnée pour les filtres actifs.")
        return

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    if is_admin():
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
            kpi_card("Mesures en alerte", str(len(anom_df)), f"Score > {seuil:.2f}", "red")
        with c3:
            n_st = int(anom_df["station_id"].nunique()) if not anom_df.empty and "station_id" in anom_df.columns else 0
            kpi_card("Stations touchées", str(n_st), "Au moins une alerte", "blue")

        det_df = _detector_rows(nb2_stats)
        if not det_df.empty:
            with section("Détecteurs NB2"):
                st.dataframe(det_df, width="stretch", hide_index=True)
                src = nb2_stats.get("seuil_ensemble_source", "")
                st.caption(
                    f"Seuil consensus (ensemble) appliqué aux alertes : {seuil:.3f}"
                    + (f" — source : {src}" if src else "")
                )

        with section("Stations prioritaires"):
            prio = _priority_stations(work, seuil, anom_col)
            if prio.empty:
                st.success("Aucune station prioritaire.")
            else:
                st.dataframe(format_dataframe_for_display(prio), width="stretch", hide_index=True)

        work["_heure"] = pd.to_numeric(work.get("heure", work["timestamp"].dt.hour if "timestamp" in work.columns else 0), errors="coerce").fillna(0)
        with section("Score × heure"):
            fig = px.scatter(
                work,
                x="_heure",
                y="_score",
                color="mode_operation" if "mode_operation" in work.columns else None,
                hover_data=["station_id"] if "station_id" in work.columns else None,
                labels={"_heure": "Heure", "_score": "Score anomalie"},
                color_discrete_map=MODE_COLORS,
            )
            fig.add_hline(y=seuil, line_dash="dash", line_color="#c8102e", annotation_text="Seuil")
            fig.update_layout(template=template, height=320, margin=dict(l=0, r=0, t=8, b=0))
            st.plotly_chart(fig, width="stretch")
    else:
        qos_seuil = 0.70
        work = df.copy()
        work["_qos"] = pd.to_numeric(work.get("score_qos", 0.75), errors="coerce").fillna(0.75)
        low_qos = work[work["_qos"] < qos_seuil]

        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("QoS moyen", f"{work['_qos'].mean() * 100:.0f}%", "", "blue")
        with c2:
            kpi_card("Alertes QoS", str(len(low_qos)), f"< {qos_seuil:.0%}", "orange")
        with c3:
            kpi_card("Stations", str(work["station_id"].nunique()) if "station_id" in work.columns else "0", "", "gray")

        with section("Stations à surveiller"):
            if "station_id" in work.columns:
                prio = (
                    work.groupby("station_id", as_index=False)
                    .agg(qos=("score_qos", "mean"), lignes=("score_qos", "count"))
                    .sort_values("qos")
                    .head(15)
                )
                if "gouvernorat" in work.columns:
                    prio["gouvernorat"] = prio["station_id"].map(work.groupby("station_id")["gouvernorat"].first())
                st.dataframe(format_dataframe_for_display(prio), width="stretch", hide_index=True)

        work["_heure"] = pd.to_numeric(
            work.get("heure", work["timestamp"].dt.hour if "timestamp" in work.columns else 0),
            errors="coerce",
        ).fillna(0)
        with section("QoS × heure"):
            fig = px.scatter(
                work,
                x="_heure",
                y="_qos",
                color="mode_operation" if "mode_operation" in work.columns else None,
                hover_data=["station_id"] if "station_id" in work.columns else None,
                labels={"_heure": "Heure", "_qos": "Score QoS"},
                color_discrete_map=MODE_COLORS,
            )
            fig.add_hline(y=qos_seuil, line_dash="dash", line_color="#c8102e")
            fig.update_layout(template=template, height=320, margin=dict(l=0, r=0, t=8, b=0))
            st.plotly_chart(fig, width="stretch")
