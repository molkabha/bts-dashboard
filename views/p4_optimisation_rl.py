"""Page NB3 — Decisions, optimisation et agents RL."""

from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import MODE_COLORS, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import (
    build_nb3_profil_horaire,
    compute_filtered_kpis,
    load_nb3_rapport,
)
from ui.components import context_badge, header, kpi_card, section
from ui.page_helpers import load_dashboard_df, mode_explanation
from ui.utils import active_filter_label, selected_station_filter, session_outputs

AGENT_DESCRIPTIONS = {
    "Q-Learning": "Apprend de ses erreurs passees sans les repeter",
    "SARSA": "Plus prudent, tient compte de ce qu'il va faire ensuite",
    "Double Q-Learning": "Evite de surestimer les bonnes actions",
    "Expected SARSA": "Moyenne les actions futures pour plus de stabilite",
    "Q-Learning Adaptatif": "Ajuste automatiquement son taux d'exploration",
    "Q-Learning UCB": "Equilibre exploration et exploitation",
    "SARSA Lambda": "Memorise les sequences d'actions reussies",
    "SARSA(\u03bb)": "Traces d'eligibilite",
    "Dyna-Q": "Simule des experiences pour apprendre plus vite",
    "Monte Carlo": "Evalue les trajectoires completes",
}


def _render_rl_agents(nb3: dict, template: str) -> None:
    rl_data = nb3.get("rl_resultats_tous_agents", {})
    if not rl_data:
        st.info("Comparaison agents : cle `rl_resultats_tous_agents` dans rapport_optimisation.json.")
        return
    df_rl = pd.DataFrame.from_dict(rl_data, orient="index").reset_index(names="Agent")
    if "economie_pct" in df_rl.columns:
        df_rl["economie_pct"] = pd.to_numeric(df_rl["economie_pct"], errors="coerce")
        df_rl = df_rl.sort_values("economie_pct", ascending=False).reset_index(drop=True)
        fig = px.bar(
            df_rl.head(10),
            x="economie_pct",
            y="Agent",
            orientation="h",
            labels={"economie_pct": "Economie %"},
            title="Classement agents RL (NB3)",
        )
        fig.update_layout(template=template, height=max(240, 36 * min(10, len(df_rl))),
                          margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
        st.plotly_chart(fig, width="stretch")
    if len(df_rl) >= 3 and "economie_pct" in df_rl.columns:
        podium_agents = [html.escape(str(df_rl.iloc[i]["Agent"])) for i in range(3)]
        st.markdown(f"""
<div class="podium">
  <div class="podium-item silver"><div class="podium-rank">2e</div><div class="podium-name">{podium_agents[1]}</div></div>
  <div class="podium-item gold"><div class="podium-rank">1er</div><div class="podium-name">{podium_agents[0]}</div></div>
  <div class="podium-item bronze"><div class="podium-rank">3e</div><div class="podium-name">{podium_agents[2]}</div></div>
</div>""", unsafe_allow_html=True)
    st.dataframe(df_rl, width="stretch", hide_index=True)


def _render_decision_cards(latest: pd.DataFrame, limit: int = 20) -> None:
    prio = {"CRITIQUE": 0, "ATTENTION": 1, "NORMAL": 2, "ECO": 3}
    work = latest.copy()
    work["_prio"] = work["mode_operation"].astype(str).map(lambda m: prio.get(m, 9))
    work = work.sort_values("_prio").head(limit)
    for _, row in work.iterrows():
        mode = str(row.get("mode_operation", "NORMAL"))
        color = MODE_COLORS.get(mode, "#64748b")
        action = str(row.get("action_rl", row.get("action_proposee", row.get("action_principale", "Monitoring"))))
        eco_kwh = float(row.get("economie_rl_kwh", row.get("economie_estimee_kwh", 0)) or 0)
        eco_dt = eco_kwh * settings.PRIX_KWH_TN
        expl = mode_explanation(row)
        sid = str(row.get("station_id", ""))
        st.markdown(f"""
<div class="decision-card" style="border-left-color:{color};">
  <div class="dc-mode" style="color:{color};">{sid} — {mode}</div>
  <div class="dc-action">Action proposee : {html.escape(action)}</div>
  <div class="dc-reason">{html.escape(expl)}</div>
  <div class="dc-saving">Gain estime : {eco_dt:.2f} DT | {eco_kwh:.2f} kWh</div>
</div>""", unsafe_allow_html=True)


def page_optimisation_rl():
    security_middleware.enforce()
    header(
        "NB3 — Decisions",
        "Actions RL, modes operationnels, economies et comparaison des agents",
    )

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    outputs = session_outputs()
    nb3 = outputs.get("nb3", {})

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
        if "timestamp" in df.columns:
            latest = df.sort_values("timestamp").groupby("station_id", as_index=False).last()
        else:
            latest = df.groupby("station_id", as_index=False).last()
        with section("Actions proposees par station (priorite)"):
            _render_decision_cards(latest)

    with section("Comparaison des agents RL"):
        _render_rl_agents(nb3, template)

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
