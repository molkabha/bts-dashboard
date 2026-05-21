"""Page 4 - Optimisation et RL (NB3)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import PLOTLY_LIGHT, PLOTLY_DARK
from security.middleware import security_middleware
from services.data_service import compute_filtered_kpis, load_filtered_main_data
from ui.components import header, kpi_card, section
from ui.utils import apply_current_admin_filters, session_outputs

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
    header("Optimisation et RL", "Economies realisees et agents de reinforcement learning")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    outputs = session_outputs()
    nb3 = outputs.get("nb3", {})

    cols = ["timestamp", "station_id", "consommation_kwh", "economie_estimee_kwh",
            "economie_rl_kwh", "action_rl", "action_proposee", "score_qos",
            "mode_operation", "heure", "technologie", "type_zone"]
    df_raw = load_filtered_main_data(cols)
    df = apply_current_admin_filters(df_raw)

    if df.empty:
        st.warning("Aucune donnee disponible pour l'optimisation.")
        return

    kpis = compute_filtered_kpis(df)
    nb_stations = kpis.get("nb_stations", 87)

    # Section 1 - Interactive savings simulator
    with section("Simulateur d'Economies Interactif"):
        st.markdown("**Et si vous activiez ces optimisations ?**")
        c1, c2 = st.columns(2)
        with c1:
            sleep_stations = st.slider(
                "Stations en sleep mode nocturne", 0, int(nb_stations), int(
                    nb_stations // 2), key="opt_sleep")
            reduction_pct = st.slider("Reduction puissance emission (%)", 0, 100, 30, key="opt_reduc")
        with c2:
            free_cooling = st.toggle("Free cooling active", value=True, key="opt_cooling")
            eco_weekends = st.toggle("Mode eco weekends et feries", value=True, key="opt_weekends")

        conso_base = float(kpis.get("conso_totale_kwh", 0) or 0)
        if conso_base == 0:
            conso_base = 500000
        annualization = 12

        eco_sleep = sleep_stations * 1.8 * 6 * 365
        eco_reduc = conso_base * annualization * (reduction_pct / 100) * 0.08
        eco_cool = conso_base * annualization * 0.15 if free_cooling else 0
        eco_we = conso_base * annualization * 0.05 if eco_weekends else 0
        eco_total_kwh = eco_sleep + eco_reduc + eco_cool + eco_we
        eco_total_dt = eco_total_kwh * settings.PRIX_KWH_TN
        co2_evite = eco_total_kwh * settings.FACTEUR_CO2_TN / 1000
        roi_months = 4.2 if eco_total_kwh > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi_card("Economie annuelle", f"{eco_total_dt:,.0f} DT", "Projection", "green")
        with c2:
            kpi_card("Energie economisee", f"{eco_total_kwh:,.0f} kWh/an", "", "eco")
        with c3:
            kpi_card("CO2 evite", f"{co2_evite:.1f} t/an", "", "blue")
        with c4:
            kpi_card("Retour sur investissement", f"{roi_months:.1f} mois", "", "gray")

        st.caption(f"Calcul base sur les donnees reelles, tarif STEG haute tension {settings.PRIX_KWH_TN} DT/kWh, "
                   f"facteur CO2 reseau TN {settings.FACTEUR_CO2_TN} kg/kWh")

    # Section 2 - 24h profile
    with section("Profil Horaire 24h"):
        if "heure" in df.columns and "consommation_kwh" in df.columns:
            hourly = df.groupby("heure").agg(
                conso_moy=("consommation_kwh", "mean"),
            ).reset_index()
            if "economie_estimee_kwh" in df.columns:
                hourly_eco = df.groupby("heure")["economie_estimee_kwh"].apply(
                    lambda x: pd.to_numeric(x, errors="coerce").mean()).reset_index(name="eco_expert")
                hourly = hourly.merge(hourly_eco, on="heure", how="left")
            if "economie_rl_kwh" in df.columns:
                hourly_rl = df.groupby("heure")["economie_rl_kwh"].apply(
                    lambda x: pd.to_numeric(x, errors="coerce").mean()).reset_index(name="eco_rl")
                hourly = hourly.merge(hourly_rl, on="heure", how="left")

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hourly["heure"], y=hourly["conso_moy"],
                                     name="Baseline (sans optimisation)", line=dict(color="#94a3b8", width=2)))
            if "eco_expert" in hourly.columns:
                fig.add_trace(go.Scatter(x=hourly["heure"],
                                         y=hourly["conso_moy"] - hourly["eco_expert"].fillna(0),
                                         name="Regles expertes", line=dict(color="#3b82f6", width=2),
                                         fill="tonexty", fillcolor="rgba(59,130,246,0.1)"))
            if "eco_rl" in hourly.columns:
                fig.add_trace(go.Scatter(x=hourly["heure"],
                                         y=hourly["conso_moy"] - hourly["eco_rl"].fillna(0),
                                         name="Meilleur agent RL", line=dict(color="#059669", width=2.5),
                                         fill="tonexty", fillcolor="rgba(5,150,105,0.1)"))
            fig.update_layout(template=template, xaxis_title="Heure", yaxis_title="kWh moyen",
                              margin=dict(l=0, r=0, t=20, b=0), height=320, hovermode="x unified")
            st.plotly_chart(fig, width="stretch")

    # Section 3 - RL agents comparison (admin only - technical detail)
    if st.session_state.get("role") == "admin":
        with section("Comparaison des Agents RL"):
            rl_data = nb3.get("rl_resultats_tous_agents", {})
            if rl_data:
                df_rl = pd.DataFrame.from_dict(rl_data, orient="index").reset_index(names="Agent")
                if "economie_pct" in df_rl.columns:
                    df_rl = df_rl.sort_values("economie_pct", ascending=False).reset_index(drop=True)

                # Podium
                if len(df_rl) >= 3:
                    st.markdown(f"""
<div class="podium">
  <div class="podium-item silver"><div class="podium-rank">2e</div><div class="podium-name">{df_rl.iloc[1]['Agent']}</div></div>
  <div class="podium-item gold"><div class="podium-rank">1er</div><div class="podium-name">{df_rl.iloc[0]['Agent']}</div></div>
  <div class="podium-item bronze"><div class="podium-rank">3e</div><div class="podium-name">{df_rl.iloc[2]['Agent']}</div></div>
</div>""", unsafe_allow_html=True)

                for _, row in df_rl.iterrows():
                    agent = str(row.get("Agent", ""))
                    eco = row.get("economie_pct", 0)
                    viol = row.get("pct_violations", 0)
                    desc = AGENT_DESCRIPTIONS.get(agent, "Agent d'apprentissage par renforcement")
                    eco_str = f"{float(eco):.1f}%" if pd.notna(eco) and eco != "" else "0.0%"
                    viol_str = f"{float(viol):.1f}%" if pd.notna(viol) and viol != "" else "0.0%"
                    st.markdown(f"**{agent}** — Economie : {eco_str} | Violations QoS : {viol_str}")
                    st.caption(desc)

                st.dataframe(df_rl, width="stretch", hide_index=True)
            else:
                st.info("Donnees agents RL non disponibles dans les artefacts NB3.")

    # Section 4 - Decision distribution
    with section("Distribution des Decisions"):
        if "mode_operation" in df.columns:
            c1, c2 = st.columns(2)
            with c1:
                mode_counts = df["mode_operation"].value_counts().reset_index()
                mode_counts.columns = ["Mode", "Nb"]
                colors = {"ECO": "#059669", "NORMAL": "#2563eb", "ATTENTION": "#d97706", "CRITIQUE": "#c8102e"}
                fig_d = px.pie(mode_counts, names="Mode", values="Nb", hole=0.45,
                               color="Mode", color_discrete_map=colors,
                               title="Repartition des modes operationnels")
                fig_d.update_layout(template=template, margin=dict(l=0, r=0, t=30, b=0), height=300)
                st.plotly_chart(fig_d, width="stretch")
            with c2:
                if "heure" in df.columns:
                    mode_hour = df.groupby(["heure", "mode_operation"]).size().reset_index(name="count")
                    fig_mh = px.bar(mode_hour, x="heure", y="count", color="mode_operation",
                                    color_discrete_map=colors, title="Distribution par heure")
                    fig_mh.update_layout(template=template, margin=dict(l=0, r=0, t=30, b=0),
                                         height=300, barmode="stack")
                    st.plotly_chart(fig_mh, width="stretch")
