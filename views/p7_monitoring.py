"""Page 7 - Monitoring temps reel (ingenieur)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
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
    header("Monitoring temps reel", "Supervision operationnelle du parc BTS")

    df = load_dashboard_df(["trafic_data_mbps", "pue", "taux_charge_data"])
    if df.empty:
        st.warning("Aucune donnee disponible pour les filtres actifs.")
        return

    kpis = metrics if metrics else fleet_status_metrics(df)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Conso totale actuelle", f"{kpis['conso_instant']:,.1f} kWh", "Instantanee flotte", "blue")
    with c2:
        nb_alertes = kpis["critiques"] + kpis["attention"]
        kpi_card("Alertes actives", str(nb_alertes), f"{kpis['critiques']} critiques", "orange")
    with c3:
        kpi_card("% ECO actif", f"{kpis['pct_eco']:.1f}%", "Stations en mode economie", "eco")
    with c4:
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

    # Top 10 stations + gauges
    latest = _latest_per_station(df)
    scores = station_summary_from_df(df)

    col_a, col_b = st.columns([1.4, 1])
    with col_a:
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

    with col_b:
        with section("Indicateurs flotte"):
            pue_vals = pd.to_numeric(latest.get("pue", pd.Series(dtype=float)), errors="coerce").dropna()
            pue_moy = float(pue_vals.mean()) if not pue_vals.empty else None
            pct_eco = kpis["pct_eco"]
            g1, g2 = st.columns(2)
            template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
            with g1:
                if pue_moy is not None:
                    fig_pue = go.Figure(go.Indicator(
                        mode="gauge+number", value=pue_moy, number={"suffix": ""},
                        title={"text": "PUE moyen flotte"},
                        gauge={"axis": {"range": [1, 2.5]}, "bar": {"color": "#1e3a8a"}},
                    ))
                    fig_pue.update_layout(template=template, height=180, margin=dict(l=10, r=10, t=40, b=0))
                    st.plotly_chart(fig_pue, width="stretch")
                else:
                    st.info("PUE non present dans le dataset actif (colonne `pue`).")
            with g2:
                fig_eco = go.Figure(go.Indicator(
                    mode="gauge+number", value=pct_eco, number={"suffix": "%"},
                    title={"text": "Stations ECO actif"},
                    gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#059669"}},
                ))
                fig_eco.update_layout(template=template, height=180, margin=dict(l=10, r=10, t=40, b=0))
                st.plotly_chart(fig_eco, width="stretch")

    # Tableau monitoring avec sparklines 24h
    with section("Tableau de monitoring"):
        if "station_id" in df.columns and "heure" in df.columns:
            spark_data = []
            for sid in sorted(df["station_id"].astype(str).unique())[:50]:
                sdf = df[df["station_id"].astype(str) == sid].sort_values("timestamp" if "timestamp" in df.columns else "heure")
                hourly = sdf.groupby("heure")["consommation_kwh"].mean().reindex(range(24), fill_value=np.nan)
                row_latest = latest[latest["station_id"].astype(str) == sid]
                if row_latest.empty:
                    continue
                r = row_latest.iloc[0]
                spark_data.append({
                    "station_id": sid,
                    "mode": str(r.get("mode_operation", "NORMAL")),
                    "conso_kwh": round(float(r.get("consommation_kwh", 0) or 0), 2),
                    "qos": round(float(r.get("score_qos", 0) or 0), 2),
                    "profil_24h": hourly.fillna(0).tolist(),
                })
            if spark_data:
                tbl = pd.DataFrame(spark_data)
                st.dataframe(
                    tbl,
                    column_config={
                        "station_id": "Station",
                        "mode": "Mode",
                        "conso_kwh": st.column_config.NumberColumn("Conso (kWh)", format="%.2f"),
                        "qos": st.column_config.NumberColumn("QoS", format="%.2f"),
                        "profil_24h": st.column_config.LineChartColumn("Profil 24h", width="medium"),
                    },
                    width="stretch",
                    hide_index=True,
                    height=420,
                )
