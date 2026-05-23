"""Page NB3 — Decisions, optimisation et agents RL."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import (
    build_nb3_profil_horaire,
    compute_filtered_kpis,
    load_nb3_rapport,
)
from ui.components import context_badge, header, kpi_card, section
from ui.page_helpers import (
    latest_per_station,
    load_dashboard_df,
    render_nb3_decision_cards,
    render_nb3_rl_agents,
)
from ui.utils import active_filter_label, selected_station_filter, session_outputs


def page_optimisation_rl():
    security_middleware.enforce(role="admin")
    header(
        "NB3 — Decisions",
        "Actions RL, modes operationnels, economies et comparaison des agents",
    )

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    nb3 = session_outputs().get("nb3", {})

    df = load_dashboard_df([
        "timestamp", "station_id", "consommation_kwh", "economie_estimee_kwh",
        "economie_rl_kwh", "action_rl", "action_proposee", "action_principale",
        "score_qos", "mode_operation", "heure", "technologie", "type_zone",
    ])
    selected_station = selected_station_filter()

    if df.empty:
        st.warning("Aucune donnee disponible pour les filtres actifs.")
        return

    st.caption(active_filter_label())

    kpis = compute_filtered_kpis(df)
    rapport = load_nb3_rapport() or nb3
    economies = rapport.get("economies", {}) if isinstance(rapport, dict) else {}
    combinee = economies.get("5 — Combinée (1+2+3+4)", {}) if isinstance(economies, dict) else {}

    with section("Impact reseau (strategies NB3)"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi_card(
                "Economie combinee",
                f"{float(combinee.get('economie_dt', kpis.get('economie_dt') or 0)):,.0f} DT",
                "Regles expertes 1+2+3+4",
                "green",
            )
        with c2:
            kpi_card(
                "Energie economisee",
                f"{float(combinee.get('economie_kwh', kpis.get('economie_kwh') or 0)):,.0f} kWh",
                f"{float(combinee.get('economie_pct', kpis.get('economie_combinee_pct') or 0)):.1f}% conso",
                "eco",
            )
        with c3:
            kpi_card(
                "CO2 evite",
                f"{float(combinee.get('co2_evite_t', kpis.get('co2_evite_t') or 0)):.1f} t",
                "Reseau filtre",
                "blue",
            )
        with c4:
            kpi_card(
                "Meilleur agent RL",
                str(rapport.get("meilleur_agent", kpis.get("meilleur_agent_rl", "—"))),
                f"{float(kpis.get('economie_rl_pct') or 0):.1f}% vs baseline",
                "gray",
            )

    if "station_id" in df.columns:
        with section("Actions proposees par station (priorite)"):
            render_nb3_decision_cards(latest_per_station(df))

    with section("Comparaison des agents RL"):
        render_nb3_rl_agents(nb3, template)

    with section("Profil horaire — baseline vs optimisation"):
        hourly = build_nb3_profil_horaire(df)
        if selected_station:
            context_badge("Filtre", f"Station {selected_station}", "success")
        if not hourly.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=hourly["heure"], y=hourly["conso_moy"],
                name="Sans optimisation", line=dict(color="#94a3b8", width=2),
            ))
            if "conso_optimisee_moy" in hourly.columns:
                fig.add_trace(go.Scatter(
                    x=hourly["heure"], y=hourly["conso_optimisee_moy"],
                    name="Regles expertes", line=dict(color="#3b82f6", width=2),
                ))
            if "conso_optimisee_rl_moy" in hourly.columns:
                fig.add_trace(go.Scatter(
                    x=hourly["heure"], y=hourly["conso_optimisee_rl_moy"],
                    name="Agent RL retenu", line=dict(color="#059669", width=2.5),
                ))
            fig.update_layout(
                template=template, xaxis_title="Heure", yaxis_title="kWh moyen",
                margin=dict(l=0, r=0, t=20, b=0), height=320, hovermode="x unified",
            )
            st.plotly_chart(fig, width="stretch")

    with section("Repartition des modes (ECO / NORMAL / ATTENTION / CRITIQUE)"):
        if "mode_operation" in df.columns:
            mode_counts = df["mode_operation"].value_counts().reset_index()
            mode_counts.columns = ["Mode", "Nb"]
            colors = {"ECO": "#059669", "NORMAL": "#2563eb", "ATTENTION": "#d97706", "CRITIQUE": "#c8102e"}
            fig_d = px.pie(
                mode_counts, names="Mode", values="Nb", hole=0.45,
                color="Mode", color_discrete_map=colors,
            )
            fig_d.update_layout(template=template, margin=dict(l=0, r=0, t=20, b=0), height=300)
            st.plotly_chart(fig_d, width="stretch")
