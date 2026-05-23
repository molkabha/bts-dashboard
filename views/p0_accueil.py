"""Page 0 - Vue executive (admin)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import MODE_COLORS, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from ui.components import header, kpi_card, section
from ui.page_helpers import load_dashboard_df
from ui.utils import merged_active_filters
from services.data_service import (
    build_nb3_monthly_series,
    compute_filtered_kpis,
    load_nb2_network_stats,
)


def page_accueil():
    security_middleware.enforce()
    if st.session_state.get("role") != "admin":
        st.session_state["_nav_override"] = 7
        st.rerun()
        return

    header("Vue executive", "Pilotage strategique du parc BTS Tunisie Telecom")

    df = load_dashboard_df()
    if df.empty:
        st.warning("Aucune donnee disponible.")
        return

    kpis = compute_filtered_kpis(df)
    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    eco_dt = kpis.get("economie_dt") or 0
    eco_mois = kpis.get("economie_dt_mois") or 0
    eco_label = kpis.get("economie_periode_label") or "Reseau NB3"
    co2 = kpis.get("co2_evite_t") or 0
    pct_eco = kpis.get("pct_mode_eco") or 0
    nb_stations = kpis.get("nb_stations", 0)
    conso = kpis.get("conso_totale_kwh") or 0
    nb_mois = int(kpis.get("nb_mois_periode") or 12)
    cout_mois = conso * settings.PRIX_KWH_TN / nb_mois if conso else 0
    nb2_stats = load_nb2_network_stats()
    seuil = float(nb2_stats.get("seuil_ensemble") or 0.25)
    scores = pd.to_numeric(df.get("anomalie_score_ensemble", 0), errors="coerce").fillna(0)
    nb_incidents = int((scores > seuil).sum())
    pct_anom_nb2 = float(nb2_stats.get("pct_anomalies_reseau") or kpis.get("pct_anomalies") or 0)
    dispo = max(0, 100 - pct_anom_nb2)

    with section("Indicateurs strategiques"):
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            kpi_card("Cout flotte", f"{cout_mois:,.0f} DT/mois", "Estimation", "blue")
        with c2:
            kpi_card(
                "Economies realisees",
                f"{eco_dt:,.0f} DT",
                f"{eco_label} · ~{eco_mois:,.0f} DT/mois",
                "green",
            )
        with c3:
            kpi_card("CO2 evite", f"{co2:.1f} t", "Equivalent", "eco")
        with c4:
            kpi_card("% stations ECO", f"{pct_eco:.1f}%", "Mode actif", "eco")
        with c5:
            kpi_card("Incidents", str(nb_incidents), "Anomalies majeures", "orange")
        with c6:
            kpi_card("Disponibilite", f"{dispo:.1f}%", "Systeme", "gray")

    c1, c2 = st.columns(2)
    with c1:
        with section("Tendance mensuelle"):
            monthly = build_nb3_monthly_series(df, kpis)
            if not monthly.empty and "periode" in monthly.columns:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=monthly["periode"], y=monthly["conso"], name="Consommation", line=dict(color="#1e3a8a")))
                if "eco_expert" in monthly.columns:
                    fig.add_trace(go.Scatter(x=monthly["periode"], y=monthly["eco_expert"], name="Economie experte (NB3)", line=dict(color="#3b82f6")))
                if "eco_rl" in monthly.columns:
                    fig.add_trace(go.Scatter(x=monthly["periode"], y=monthly["eco_rl"], name="Economie RL (NB3)", line=dict(color="#059669")))
                fig.update_layout(template=template, height=280, margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig, width="stretch")
                st.caption("Source : streamlit_timeseries.parquet (NB3) ou agregats filtres du dataset actif.")

    with c2:
        with section("Modes operationnels"):
            if "mode_operation" in df.columns:
                modes = df["mode_operation"].astype(str).value_counts().reset_index()
                modes.columns = ["Mode", "Nb"]
                fig = px.pie(modes, names="Mode", values="Nb", hole=0.5, color="Mode", color_discrete_map=MODE_COLORS)
                fig.update_layout(template=template, height=280, margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig, width="stretch")

    with section("Consommation moyenne par gouvernorat (par periode)"):
        if "gouvernorat" not in df.columns or "consommation_kwh" not in df.columns:
            st.info("Donnees gouvernorat / consommation indisponibles.")
        elif "timestamp" in df.columns:
            work = df.copy()
            work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
            work = work.dropna(subset=["timestamp", "gouvernorat"])
            work["periode"] = work["timestamp"].dt.to_period("M").astype(str)

            by_period = (
                work.groupby(["periode", "gouvernorat"], as_index=False)["consommation_kwh"]
                .mean()
                .rename(columns={"consommation_kwh": "conso_moy_kwh"})
            )
            top_govs = (
                work.groupby("gouvernorat")["consommation_kwh"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
                .index.astype(str)
                .tolist()
            )
            chart_df = by_period[by_period["gouvernorat"].astype(str).isin(top_govs)].sort_values("periode")

            fig_period = px.bar(
                chart_df,
                x="periode",
                y="conso_moy_kwh",
                color="gouvernorat",
                barmode="group",
                labels={
                    "periode": "Periode (mois)",
                    "conso_moy_kwh": "Consommation moyenne (kWh)",
                    "gouvernorat": "Gouvernorat",
                },
                title="Moyenne horaire par mois et par gouvernorat",
            )
            fig_period.update_layout(template=template, height=340, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_period, width="stretch")

            period_label = ""
            gf = merged_active_filters()
            if gf.get("date_range"):
                start, end = gf["date_range"]
                period_label = f"Periode filtree : {start} → {end}"
            else:
                period_label = f"Periodes : {chart_df['periode'].min()} → {chart_df['periode'].max()}"
            st.caption(f"{period_label} · Top {len(top_govs)} gouvernorats (conso totale)")

            by_gov = (
                work.groupby("gouvernorat", as_index=False)["consommation_kwh"]
                .mean()
                .rename(columns={"consommation_kwh": "conso_moy_kwh"})
                .sort_values("conso_moy_kwh", ascending=True)
            )
            fig_gov = px.bar(
                by_gov,
                x="conso_moy_kwh",
                y="gouvernorat",
                orientation="h",
                labels={"conso_moy_kwh": "Conso moyenne (kWh)", "gouvernorat": "Gouvernorat"},
                title="Moyenne sur toute la periode selectionnee",
            )
            fig_gov.update_layout(template=template, height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_gov, width="stretch")
        else:
            by_gov = df.groupby("gouvernorat")["consommation_kwh"].mean().reset_index()
            by_gov.columns = ["Gouvernorat", "Conso moyenne (kWh)"]
            fig = px.bar(
                by_gov.sort_values("Conso moyenne (kWh)", ascending=True),
                x="Conso moyenne (kWh)",
                y="Gouvernorat",
                orientation="h",
            )
            fig.update_layout(template=template, height=300, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, width="stretch")
