"""Page NB3 — Optimisation."""

from __future__ import annotations

from pathlib import Path

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
    dashboard_data_coverage,
)
from ui.components import header, kpi_card, section
from ui.display import PAGE_OPTIMISATION
from ui.formatting import display_text
from ui.page_helpers import (
    latest_per_station,
    load_dashboard_df,
    render_nb3_decision_cards,
    render_nb3_rl_agents,
)
from ui.utils import active_filter_label, is_admin, session_outputs


def page_optimisation_rl():
    security_middleware.enforce()

    subtitle = "Règles vs RL, courbe d'apprentissage et economies CO₂"
    if not is_admin():
        subtitle = "Modes et actions sur vos stations (sans métriques RL)"
    header(PAGE_OPTIMISATION, subtitle)
    st.caption(active_filter_label())

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    nb3 = session_outputs().get("nb3", {})
    df = load_dashboard_df([
        "timestamp", "station_id", "consommation_kwh", "economie_estimee_kwh",
        "economie_rl_kwh", "action_rl", "action_proposee", "action_principale",
        "mode_operation", "heure",
    ])
    if df.empty:
        st.warning("Aucune donnée pour les filtres actifs.")
        return

    kpis = compute_filtered_kpis(df)

    with st.expander("Provenance des données (période filtrée)", expanded=False):
        st.caption(
            "KPI = sommes des colonnes NB3 sur les lignes filtrées (pas de % réseau extrapolé). "
            "Fusion : `enrich_dashboard_data` (parquets NB1/NB2/NB3)."
        )
        cov = dashboard_data_coverage(df)
        if not cov.empty:
            st.dataframe(cov, width="stretch", hide_index=True)
        if "action_proposee" in df.columns:
            actions = df["action_proposee"].astype(str).str.strip().str.lower()
            pct_aa = float((actions == "aucune_action").mean() * 100)
            st.caption(
                f"Part des lignes avec action experte « Aucune action » : {pct_aa:.1f} % — "
                "code NB3 normal quand le moteur ne recommande pas de mesure (souvent mode NORMAL/ECO)."
            )
        if "source_decision_nb3" in df.columns:
            nb3_rows = df["source_decision_nb3"].astype(str).eq("NB3").sum()
            st.caption(f"Lignes avec décision NB3 fusionnée : {nb3_rows:,} / {len(df):,}")
        ref_pct = kpis.get("nb3_ref_economie_combinee_pct")
        if ref_pct is not None and float(kpis.get("economie_kwh") or 0) <= 0:
            st.warning(
                f"Économies à 0 sur la période filtrée. Référence réseau NB3 (kpi_reseau.json) : "
                f"{float(ref_pct):.1f} % — affichée à titre indicatif uniquement."
            )

    if is_admin():
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi_card(
                "Économies",
                f"{float(kpis.get('economie_dt') or 0):,.0f} DT",
                kpis.get("economie_periode_label", "Période filtrée"),
                "green",
            )
        with c2:
            kpi_card(
                "kWh économisés",
                f"{float(kpis.get('economie_kwh') or 0):,.0f}",
                f"{float(kpis.get('economie_combinee_pct') or 0):.1f}%",
                "eco",
            )
        with c3:
            kpi_card("CO₂ evite", f"{float(kpis.get('co2_evite_t') or 0):.2f} t", "", "eco")
        with c4:
            kpi_card("Agent RL", display_text(kpis.get("meilleur_agent_rl")), "", "gray")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Stations", str(df["station_id"].nunique()) if "station_id" in df.columns else "0", "", "blue")
        with c2:
            kpi_card("Mode ECO", f"{float(kpis.get('pct_mode_eco') or 0):.1f}%", "", "eco")
        with c3:
            kpi_card("Conso moyenne", f"{float(kpis.get('conso_moyenne_kwh') or 0):.1f} kWh", "", "gray")

    if "station_id" in df.columns:
        with section("Actions par station"):
            render_nb3_decision_cards(latest_per_station(df), limit=12, show_savings=is_admin())

    if is_admin():
        c1, c2 = st.columns(2)
        with c1:
            with section("Règles vs RL (kWh)"):
                st.caption(
                    f"Combiné (max/ligne) : {float(kpis.get('economie_kwh') or 0):,.0f} kWh "
                    f"({float(kpis.get('economie_combinee_pct') or 0):.2f} % de la conso filtrée)"
                )
                eco_reg = float(kpis.get("economie_estimee_kwh") or 0)
                eco_rl = float(kpis.get("economie_rl_kwh") or 0)
                fig = go.Figure(
                    data=[
                        go.Bar(
                            x=["Règles expertes", "RL"],
                            y=[eco_reg, eco_rl],
                            marker_color=["#1e3a8a", "#059669"],
                        )
                    ]
                )
                fig.update_layout(template=template, height=260, margin=dict(l=0, r=0, t=8, b=0))
                st.plotly_chart(fig, width="stretch")

        with c2:
            with section("Courbe d'apprentissage RL"):
                img_path = settings.NB3_OUTPUT / "rl_7agents_apprentissage.png"
                if img_path.exists():
                    st.image(str(img_path), use_container_width=True)
                else:
                    rl_data = nb3.get("rl_resultats_tous_agents", {})
                    if rl_data:
                        df_rl = pd.DataFrame.from_dict(rl_data, orient="index").reset_index(names="Agent")
                        if "economie_pct" in df_rl.columns:
                            fig = px.bar(
                                df_rl.sort_values("economie_pct", ascending=False),
                                x="Agent",
                                y="economie_pct",
                                labels={"economie_pct": "Économie %", "Agent": "Agent"},
                            )
                            fig.update_layout(template=template, height=260, margin=dict(l=0, r=0, t=8, b=0))
                            st.plotly_chart(fig, width="stretch")
                    else:
                        st.info("Image rl_7agents_apprentissage.png ou resultats agents indisponibles.")

        with st.expander("Comparaison agents RL", expanded=False):
            render_nb3_rl_agents(nb3, template)

    c1, c2 = st.columns(2)
    with c1:
        with section("Profil horaire conso"):
            hourly = build_nb3_profil_horaire(df)
            if hourly.empty:
                st.info("Profil indisponible.")
            else:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=hourly["heure"], y=hourly["conso_moy"], name="Référence"))
                if is_admin() and "conso_optimisee_rl_moy" in hourly.columns:
                    fig.add_trace(go.Scatter(x=hourly["heure"], y=hourly["conso_optimisee_rl_moy"], name="Après RL"))
                fig.update_layout(template=template, height=260, margin=dict(l=0, r=0, t=8, b=0))
                st.plotly_chart(fig, width="stretch")

    with c2:
        with section("Répartition des modes"):
            if "mode_operation" in df.columns and "station_id" in df.columns:
                mode_counts = latest_per_station(df)["mode_operation"].value_counts().reset_index()
                mode_counts.columns = ["Mode", "Nb"]
                fig_d = px.pie(
                    mode_counts, names="Mode", values="Nb", hole=0.5,
                    color="Mode", color_discrete_map=MODE_COLORS,
                )
                fig_d.update_layout(template=template, height=260, margin=dict(l=0, r=0, t=8, b=0))
                st.plotly_chart(fig_d, width="stretch")
