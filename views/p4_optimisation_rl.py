"""Page NB3 — Decisions."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.theme import MODE_COLORS, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import build_nb3_profil_horaire, compute_filtered_kpis
from ui.components import header, kpi_card, section
from ui.display import PAGE_DECISIONS
from ui.formatting import display_text
from ui.page_helpers import (
    latest_per_station,
    load_dashboard_df,
    render_nb3_decision_cards,
    render_nb3_rl_agents,
)
from ui.utils import active_filter_label, session_outputs


def page_optimisation_rl():
    security_middleware.enforce(role="admin")
    header(PAGE_DECISIONS, "Actions recommandees et impact energetique")
    st.caption(active_filter_label())

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    nb3 = session_outputs().get("nb3", {})
    df = load_dashboard_df([
        "timestamp", "station_id", "consommation_kwh", "economie_estimee_kwh",
        "economie_rl_kwh", "action_rl", "action_proposee", "action_principale",
        "mode_operation", "heure",
    ])
    if df.empty:
        st.warning("Aucune donnee pour les filtres actifs.")
        return

    kpis = compute_filtered_kpis(df)

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card(
            "Economies",
            f"{float(kpis.get('economie_dt') or 0):,.0f} DT",
            kpis.get("economie_periode_label", "Periode filtree"),
            "green",
        )
    with c2:
        kpi_card(
            "kWh economises",
            f"{float(kpis.get('economie_kwh') or 0):,.0f}",
            f"{float(kpis.get('economie_combinee_pct') or 0):.1f}%",
            "eco",
        )
    with c3:
        kpi_card("Agent RL", display_text(kpis.get("meilleur_agent_rl")), "", "gray")

    if "station_id" in df.columns:
        with section("Actions par station"):
            render_nb3_decision_cards(latest_per_station(df), limit=12)

    with st.expander("Comparaison agents RL", expanded=False):
        render_nb3_rl_agents(nb3, template)

    c1, c2 = st.columns(2)
    with c1:
        with section("Profil horaire"):
            hourly = build_nb3_profil_horaire(df)
            if hourly.empty:
                st.info("Profil indisponible.")
            else:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=hourly["heure"], y=hourly["conso_moy"], name="Baseline"))
                if "conso_optimisee_rl_moy" in hourly.columns:
                    fig.add_trace(go.Scatter(x=hourly["heure"], y=hourly["conso_optimisee_rl_moy"], name="Apres RL"))
                fig.update_layout(template=template, height=260, margin=dict(l=0, r=0, t=8, b=0))
                st.plotly_chart(fig, width="stretch")

    with c2:
        with section("Modes"):
            if "mode_operation" in df.columns:
                mode_counts = df["mode_operation"].value_counts().reset_index()
                mode_counts.columns = ["Mode", "Nb"]
                fig_d = px.pie(
                    mode_counts, names="Mode", values="Nb", hole=0.5,
                    color="Mode", color_discrete_map=MODE_COLORS,
                )
                fig_d.update_layout(template=template, height=260, margin=dict(l=0, r=0, t=8, b=0))
                st.plotly_chart(fig_d, width="stretch")
