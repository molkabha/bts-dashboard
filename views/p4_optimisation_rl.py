"""Page 4 - Optimisation et RL (NB3)."""

from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import PLOTLY_LIGHT, PLOTLY_DARK
from security.middleware import security_middleware
from services.data_service import (
    build_nb3_profil_horaire,
    compute_filtered_kpis,
    load_nb3_rapport,
)
from ui.components import context_badge, header, kpi_card, section
from ui.page_helpers import load_dashboard_df
from ui.utils import active_filter_label, selected_station_filter, session_outputs

AGENT_DESCRIPTIONS = {
    "Q-Learning": "Apprend de ses erreurs passees sans les repeter",
    "SARSA": "Plus prudent, tient compte de ce qu'il va faire ensuite",
    "Double Q-Learning": "Evite de surestimer les bonnes actions",
    "Expected SARSA": "Moyenne les actions futures pour plus de stabilite",
    "Q-Learning Adaptatif": "Ajuste automatiquement son taux d'exploration",
    "Q-Learning UCB": "Equilibre exploration et exploitation avec une borne de confiance",
    "SARSA Lambda": "Memorise les sequences d'actions reussies",
    "SARSA(\u03bb)": "Memorise les sequences d'actions reussies avec traces d'eligibilite",
    "Dyna-Q": "Simule des experiences pour apprendre plus vite",
    "Monte Carlo": "Evalue les decisions a partir de trajectoires completes",
}


def page_optimisation_rl():
    security_middleware.enforce()
    header("Optimisation RL", "Economies, modes operationnels et recommandations")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    outputs = session_outputs()
    nb3 = outputs.get("nb3", {})

    df = load_dashboard_df([
        "timestamp", "station_id", "consommation_kwh", "economie_estimee_kwh",
        "economie_rl_kwh", "action_rl", "action_proposee", "score_qos",
        "mode_operation", "heure", "technologie", "type_zone",
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

    with section("Economies reseau (NB3 — rapport_optimisation.json)"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi_card(
                "Economie combinee",
                f"{float(combinee.get('economie_dt', kpis.get('economie_dt') or 0)):,.0f} DT",
                "Strategies 1+2+3+4",
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
                "Reseau",
                "blue",
            )
        with c4:
            kpi_card(
                "Meilleur agent RL",
                str(rapport.get("meilleur_agent", kpis.get("meilleur_agent_rl", "—"))),
                f"{float(kpis.get('economie_rl_pct') or 0):.1f}%",
                "gray",
            )
    with section("Profil horaire 24h"):
        hourly = build_nb3_profil_horaire(df)
        if selected_station:
            context_badge("Profil NB3", f"Filtre station {selected_station}", "success")

        if not hourly.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hourly["heure"], y=hourly["conso_moy"],
                                     name="Baseline (sans optimisation)", line=dict(color="#94a3b8", width=2)))
            if "conso_optimisee_moy" in hourly.columns:
                fig.add_trace(go.Scatter(x=hourly["heure"], y=hourly["conso_optimisee_moy"],
                                         name="Regles expertes", line=dict(color="#3b82f6", width=2),
                                         fill="tonexty", fillcolor="rgba(59,130,246,0.1)"))
            if "conso_optimisee_rl_moy" in hourly.columns:
                fig.add_trace(go.Scatter(x=hourly["heure"], y=hourly["conso_optimisee_rl_moy"],
                                         name="Meilleur agent RL", line=dict(color="#059669", width=2.5),
                                         fill="tonexty", fillcolor="rgba(5,150,105,0.1)"))
            fig.update_layout(template=template, xaxis_title="Heure", yaxis_title="kWh moyen",
                              margin=dict(l=0, r=0, t=20, b=0), height=320, hovermode="x unified")
            st.plotly_chart(fig, width="stretch")

    # RL agents comparison (admin only)
    if st.session_state.get("role") == "admin":
        with st.expander("Comparaison technique des agents RL", expanded=False):
            rl_data = nb3.get("rl_resultats_tous_agents", {})
            if rl_data:
                df_rl = pd.DataFrame.from_dict(rl_data, orient="index").reset_index(names="Agent")
                if "economie_pct" in df_rl.columns:
                    df_rl = df_rl.sort_values("economie_pct", ascending=False).reset_index(drop=True)

                # Podium
                if len(df_rl) >= 3:
                    podium_agents = [html.escape(str(df_rl.iloc[i]["Agent"])) for i in range(3)]
                    st.markdown(f"""
<div class="podium">
  <div class="podium-item silver"><div class="podium-rank">2e</div><div class="podium-name">{podium_agents[1]}</div></div>
  <div class="podium-item gold"><div class="podium-rank">1er</div><div class="podium-name">{podium_agents[0]}</div></div>
  <div class="podium-item bronze"><div class="podium-rank">3e</div><div class="podium-name">{podium_agents[2]}</div></div>
</div>""", unsafe_allow_html=True)

                for _, row in df_rl.iterrows():
                    agent = str(row.get("Agent", ""))
                    eco = row.get("economie_pct", 0)
                    viol = row.get("pct_violations", 0)
                    desc = AGENT_DESCRIPTIONS.get(agent, "Agent d'apprentissage par renforcement")
                    eco_str = f"{float(eco):.1f}%" if pd.notna(eco) and eco != "" else "0.0%"
                    viol_str = f"{float(viol):.1f}%" if pd.notna(viol) and viol != "" else "0.0%"
                    st.markdown(f"**{agent}** - Economie : {eco_str} | Violations QoS : {viol_str}")
                    st.caption(desc)

                st.dataframe(df_rl, width="stretch", hide_index=True)
            else:
                st.info("Donnees agents RL non disponibles dans les artefacts NB3.")

    with section("Repartition des modes operationnels"):
        if "mode_operation" in df.columns:
            mode_counts = df["mode_operation"].value_counts().reset_index()
            mode_counts.columns = ["Mode", "Nb"]
            colors = {"ECO": "#059669", "NORMAL": "#2563eb", "ATTENTION": "#d97706", "CRITIQUE": "#c8102e"}
            fig_d = px.pie(
                mode_counts,
                names="Mode",
                values="Nb",
                hole=0.45,
                color="Mode",
                color_discrete_map=colors,
                title="Decisions NB3 sur la periode filtree",
            )
            fig_d.update_layout(template=template, margin=dict(l=0, r=0, t=30, b=0), height=320)
            st.plotly_chart(fig_d, width="stretch")
            st.caption("Profil horaire : page Monitoring (ingenieur).")
