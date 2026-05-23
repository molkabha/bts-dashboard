"""Page 7 - Monitoring temps reel (ingenieur)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import station_summary_from_df
from ui.components import header, kpi_card, section
from ui.page_helpers import fleet_status_metrics, load_dashboard_df


def _latest_per_station(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "station_id" not in df.columns:
        return df
    if "timestamp" in df.columns:
        return df.sort_values("timestamp").groupby("station_id", as_index=False).last()
    return df.groupby("station_id", as_index=False).last()


def page_monitoring():
    security_middleware.enforce()
    df = st.session_state.get("_dashboard_df")
    if not isinstance(df, pd.DataFrame) or df.empty:
        df = load_dashboard_df(["trafic_data_mbps", "pue", "taux_charge_data"])
    metrics = st.session_state.get("_fleet_metrics") or fleet_status_metrics(df)
    header("Monitoring", "Supervision operationnelle du parc BTS")

    df = load_dashboard_df(["trafic_data_mbps", "pue", "taux_charge_data"])
    if df.empty:
        st.warning("Aucune donnee disponible pour les filtres actifs.")
        return

    kpis = metrics if metrics else fleet_status_metrics(df)
    latest = _latest_per_station(df)
    pue_vals = pd.to_numeric(latest.get("pue", pd.Series(dtype=float)), errors="coerce").dropna()
    pue_moy = float(pue_vals.mean()) if not pue_vals.empty else None

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Conso totale actuelle", f"{kpis['conso_instant']:,.1f} kWh", "Instantanee flotte", "blue")
    with c2:
        nb_alertes = kpis["critiques"] + kpis["attention"]
        kpi_card("Alertes actives", str(nb_alertes), f"{kpis['critiques']} critiques", "orange")
    with c3:
        kpi_card("% ECO actif", f"{kpis['pct_eco']:.1f}%", "Stations en mode economie", "eco")
    with c4:
        if pue_moy is not None:
            kpi_card("PUE moyen", f"{pue_moy:.2f}", "Flotte", "gray")
        else:
            kpi_card("EEI moyen", f"{kpis['eei_moy']:.2f}", "kWh / Mbps proxy", "gray")

    # Heatmap consommation : heure x jour semaine
    with section("Heatmap consommation (kWh moyen)"):
        if {"heure", "jour_semaine", "consommation_kwh"}.issubset(df.columns):
            heat = df.groupby(["jour_semaine", "heure"])["consommation_kwh"].mean().reset_index()
            jours = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
            heat["jour_label"] = heat["jour_semaine"].astype(int).map(
                lambda x: jours[x] if 0 <= x < 7 else str(x))
            pivot = heat.pivot(index="jour_label", columns="heure", values="consommation_kwh")
            pivot = pivot.reindex([j for j in jours if j in pivot.index])
            template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
            fig = px.imshow(pivot, aspect="auto", color_continuous_scale="Blues",
                            labels=dict(x="Heure", y="Jour", color="kWh moyen"))
            fig.update_layout(template=template, margin=dict(l=0, r=0, t=24, b=0), height=320)
            st.plotly_chart(fig, width="stretch")

    scores = station_summary_from_df(df)

    with section("Top 10 stations consommatrices"):
        if not scores.empty and "conso_moy" in scores.columns:
            profil = scores["conso_moy"].median() if scores["conso_moy"].notna().any() else 1
            scores = scores.copy()
            scores["ecart_vs_profil"] = ((scores["conso_moy"] - profil) / profil * 100).round(1)
            top10 = scores.nlargest(10, "conso_moy")
            fig = px.bar(
                top10.sort_values("conso_moy"),
                x="ecart_vs_profil", y="station_id", orientation="h",
                title="Ecart vs profil moyen (%)",
                color="ecart_vs_profil", color_continuous_scale="Reds",
            )
            template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
            fig.update_layout(template=template, showlegend=False, height=360, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, width="stretch")
