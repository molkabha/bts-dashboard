"""Page 0 - Accueil (admin)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from ui.components import header, kpi_card, section
from ui.page_helpers import load_dashboard_df, render_executive_report_export
from services.data_service import (
    build_nb3_monthly_series,
    compute_filtered_kpis,
    load_nb2_network_stats,
)


def page_accueil():
    security_middleware.enforce()
    if st.session_state.get("role") != "admin":
        st.session_state["_nav_override"] = 6
        st.rerun()
        return

    header("Accueil", "Pilotage strategique du parc BTS Tunisie Telecom")

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
    pct_eco_nb3 = float(kpis.get("economie_combinee_pct") or 0)
    nb2_stats = load_nb2_network_stats()
    seuil = float(nb2_stats.get("seuil_ensemble") or 0.25)
    scores = pd.to_numeric(df.get("anomalie_score_ensemble", 0), errors="coerce").fillna(0)
    nb_anomalies = int((scores > seuil).sum())

    with section("Indicateurs strategiques"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            eco_help = f"{eco_label} · ~{eco_mois:,.0f} DT/mois"
            if pct_eco_nb3 > 0:
                eco_help += f" · {pct_eco_nb3:.1f}% conso"
            kpi_card("Economies realisees", f"{eco_dt:,.0f} DT", eco_help, "green")
        with c2:
            kpi_card("CO2 evite", f"{co2:.1f} t", "Equivalent", "eco")
        with c3:
            kpi_card("% stations ECO", f"{pct_eco:.1f}%", "Mode actif", "eco")
        with c4:
            kpi_card(
                "Anomalies NB2",
                str(nb_anomalies),
                f"Mesures avec score > {seuil:.2f}",
                "orange",
            )

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
        with section("Top gouvernorats (conso moyenne)"):
            if {"gouvernorat", "consommation_kwh"}.issubset(df.columns):
                by_gov = (
                    df.groupby("gouvernorat", as_index=False)["consommation_kwh"]
                    .mean()
                    .nlargest(8, "consommation_kwh")
                    .sort_values("consommation_kwh")
                )
                fig = px.bar(
                    by_gov,
                    x="consommation_kwh",
                    y="gouvernorat",
                    orientation="h",
                    labels={"consommation_kwh": "kWh moyen", "gouvernorat": ""},
                )
                fig.update_layout(template=template, height=280, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
                st.plotly_chart(fig, width="stretch")
                st.caption("Detail par gouvernorat : page Comparaison.")
            else:
                st.info("Colonnes gouvernorat / consommation indisponibles.")

    render_executive_report_export(kpis)
