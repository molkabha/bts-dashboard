"""Page 0 - Accueil (admin)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import (
    build_nb3_monthly_series,
    compute_filtered_kpis,
    load_nb2_network_stats,
)
from ui.components import header, kpi_card, section
from ui.page_helpers import load_dashboard_df, render_executive_report_export
from ui.utils import active_filter_label


def page_accueil():
    security_middleware.enforce(role="admin")

    header("Accueil", "Synthese reseau sur la periode filtree")
    st.caption(active_filter_label())

    df = load_dashboard_df()
    if df.empty:
        st.warning("Aucune donnee pour les filtres actifs.")
        return

    kpis = compute_filtered_kpis(df)
    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    nb2_stats = load_nb2_network_stats()
    seuil = float(nb2_stats.get("seuil_ensemble") or 0.25)
    scores = pd.to_numeric(df.get("anomalie_score_ensemble", 0), errors="coerce").fillna(0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        eco_dt = kpis.get("economie_dt") or 0
        kpi_card("Economies", f"{eco_dt:,.0f} DT", "Estimation NB3", "green")
    with c2:
        kpi_card("CO2 evite", f"{float(kpis.get('co2_evite_t') or 0):.1f} t", "", "eco")
    with c3:
        kpi_card("Stations ECO", f"{float(kpis.get('pct_mode_eco') or 0):.1f}%", "", "eco")
    with c4:
        kpi_card("Alertes", str(int((scores > seuil).sum())), f"Score > {seuil:.2f}", "orange")

    c1, c2 = st.columns(2)
    with c1:
        with section("Conso et economies mensuelles"):
            monthly = build_nb3_monthly_series(df, kpis)
            if monthly.empty or "periode" not in monthly.columns:
                st.info("Serie mensuelle indisponible.")
            else:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=monthly["periode"], y=monthly["conso"], name="Conso"))
                if "eco_expert" in monthly.columns:
                    fig.add_trace(go.Scatter(x=monthly["periode"], y=monthly["eco_expert"], name="Eco. regles"))
                if "eco_rl" in monthly.columns:
                    fig.add_trace(go.Scatter(x=monthly["periode"], y=monthly["eco_rl"], name="Eco. RL"))
                fig.update_layout(template=template, height=260, margin=dict(l=0, r=0, t=8, b=0), showlegend=True)
                st.plotly_chart(fig, width="stretch")

    with c2:
        with section("Conso moyenne par gouvernorat"):
            if {"gouvernorat", "consommation_kwh"}.issubset(df.columns):
                by_gov = (
                    df.groupby("gouvernorat", as_index=False)["consommation_kwh"]
                    .mean()
                    .nlargest(6, "consommation_kwh")
                    .sort_values("consommation_kwh")
                )
                fig = px.bar(by_gov, x="consommation_kwh", y="gouvernorat", orientation="h")
                fig.update_layout(template=template, height=260, margin=dict(l=0, r=0, t=8, b=0), showlegend=False)
                st.plotly_chart(fig, width="stretch")

    render_executive_report_export(kpis)
