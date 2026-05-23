"""Page NB2 — Detection d'anomalies (detecteurs + consensus)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import load_nb2_network_stats
from ui.components import header, kpi_card, section
from ui.page_helpers import load_dashboard_df
from ui.utils import active_filter_label


def _anomaly_type(score: float, qos: float) -> str:
    if qos < 0.7:
        return "QoS"
    if score > 0.5:
        return "Energetique"
    return "Mixte"


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
        if not any(k in stats for k in ("pct_test", "pct_anomalies", "seuil", "accord_metier_%", "accord_metier")):
            continue
        rows.append({
            "Detecteur": str(name),
            "Anomalies test %": stats.get("pct_test", stats.get("pct_anomalies")),
            "Seuil": stats.get("seuil", stats.get("seuil_test")),
            "Accord metier %": stats.get("accord_metier_%", stats.get("accord_metier")),
        })
    return pd.DataFrame(rows)


def page_anomalies():
    security_middleware.enforce()
    header(
        "NB2 — Anomalies",
        "Comparaison des detecteurs non supervises et anomalies detectees sur le filtre actif",
    )

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    st.caption(active_filter_label())

    df = load_dashboard_df(["ecart_pct", "label_ensemble_score", "score_qos", "gouvernorat"])
    if df.empty:
        st.warning("Aucune donnee disponible.")
        return

    nb2_stats = load_nb2_network_stats()
    seuil = float(nb2_stats.get("seuil_ensemble") or 0.25)
    seuil_src = str(nb2_stats.get("seuil_ensemble_source", ""))
    pct_reseau = nb2_stats.get("pct_anomalies_reseau")

    anom_col = "anomalie_score_ensemble"
    work = df.copy()
    work["_score"] = pd.to_numeric(work.get(anom_col, 0), errors="coerce").fillna(0)
    anom_df = work[work["_score"] > seuil].copy()

    score_consensus = float(work["_score"].mean())
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Score consensus moy.", f"{score_consensus:.2f}", "Vote pondere NB2", "orange")
    with k2:
        kpi_card("Mesures en alerte", str(len(anom_df)), f"Score > {seuil:.2f}", "red")
    with k3:
        kpi_card("Stations touchees", str(anom_df["station_id"].nunique()) if not anom_df.empty else "0", "Dernier filtre", "blue")
    with k4:
        pct_txt = f"{float(pct_reseau):.1f}%" if pct_reseau is not None else "—"
        kpi_card("Taux reseau NB2", pct_txt, seuil_src[:40] if seuil_src else "KPI export", "gray")

    with section("Performance des detecteurs (NB2)"):
        det_df = _detector_rows(nb2_stats)
        if det_df.empty:
            st.info("Tableau detecteurs : export resultats_anomalie.json (un bloc par algorithme).")
        else:
            st.dataframe(det_df, width="stretch", hide_index=True)
            st.caption("7 detecteurs entraines dans NB2 ; le consensus combine leurs scores.")

    with section("Anomalies detectees (priorite score)"):
        if anom_df.empty:
            st.success("Aucune mesure au-dessus du seuil pour les filtres actifs.")
        else:
            qos = pd.to_numeric(anom_df.get("score_qos", 1), errors="coerce").fillna(1)
            anom_df["Type"] = [
                _anomaly_type(float(s), float(q))
                for s, q in zip(anom_df["_score"], qos)
            ]
            cols = [c for c in [
                "timestamp", "station_id", "gouvernorat", "_score", "nb_votes_anomalie",
                "ecart_pct", "score_qos", "mode_operation", "Type",
            ] if c in anom_df.columns]
            show = anom_df[cols].sort_values("_score", ascending=False).head(50)
            rename = {
                "timestamp": "Horodatage",
                "station_id": "Station",
                "gouvernorat": "Gouvernorat",
                "_score": "Score ensemble",
                "nb_votes_anomalie": "Votes detecteurs",
                "ecart_pct": "Ecart % conso",
                "score_qos": "QoS",
                "mode_operation": "Mode NB3",
            }
            st.dataframe(show.rename(columns=rename), width="stretch", hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        with section("Carte score vs ecart conso"):
            if {"ecart_pct", anom_col, "mode_operation"}.issubset(work.columns):
                scatter_df = work.copy()
                scatter_df["ecart_pct"] = pd.to_numeric(scatter_df["ecart_pct"], errors="coerce").fillna(0)
                scatter_df["score"] = pd.to_numeric(scatter_df[anom_col], errors="coerce").fillna(0)
                fig = px.scatter(
                    scatter_df, x="ecart_pct", y="score", color="mode_operation",
                    hover_data=["station_id"],
                    labels={"ecart_pct": "Ecart %", "score": "Score ensemble"},
                    color_discrete_map={
                        "ECO": "#059669", "NORMAL": "#2563eb",
                        "ATTENTION": "#d97706", "CRITIQUE": "#c8102e",
                    },
                )
                fig.add_hline(y=seuil, line_dash="dash", line_color="#c8102e",
                              annotation_text=f"Seuil {seuil:.2f}")
                fig.update_layout(template=template, height=320, margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig, width="stretch")

    with c2:
        with section("Timeline alertes (24h)"):
            if "timestamp" in anom_df.columns and not anom_df.empty:
                ts = anom_df.copy()
                ts["timestamp"] = pd.to_datetime(ts["timestamp"], errors="coerce")
                cutoff = ts["timestamp"].max() - pd.Timedelta(hours=24)
                ts = ts[ts["timestamp"] >= cutoff]
                timeline = ts.groupby(["timestamp", "station_id"])["_score"].max().reset_index()
                fig = px.line(timeline, x="timestamp", y="_score", color="station_id")
                fig.update_layout(template=template, height=320, margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Pas d'anomalie recente a tracer.")
