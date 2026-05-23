"""Page 6 - Simulation / bac a sable."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import engineer_assigned_stations, load_filtered_main_data
from services.decision_service import MoteurDecisionEnergie
from ui.components import header, kpi_card, section
from ui.utils import apply_current_admin_filters


def page_sandbox():
    security_middleware.enforce()
    header("Simulation", "Bac a sable — scenarios energetiques")

    role = st.session_state.get("role")
    cols = ["timestamp", "station_id", "consommation_kwh", "heure", "mode_operation",
            "charge_cpu_pct", "anomalie_score_ensemble", "score_qos", "ecart_pct"]
    df_raw = load_filtered_main_data(cols)
    df = apply_current_admin_filters(df_raw)

    if role != "admin":
        assigned = engineer_assigned_stations(st.session_state.get("username", ""))
        if assigned and "station_id" in df.columns:
            df = df[df["station_id"].astype(str).isin(assigned)]

    if df.empty:
        st.warning("Aucune donnee pour la simulation.")
        return

    baseline = float(pd.to_numeric(df["consommation_kwh"], errors="coerce").mean() or 3) * 24

    with section("Parametres du scenario"):
        c1, c2, c3 = st.columns(3)
        with c1:
            nb_eco = st.slider("Stations en mode ECO", 0, 87, 30)
        with c2:
            heure_debut, heure_fin = st.slider("Plage horaire", 0, 23, (0, 6))
        with c3:
            duree_h = st.slider("Duree simulation (h)", 1, 24, 24)

    reduction = nb_eco / max(df["station_id"].nunique(), 1) * 0.18
    sim_conso = baseline * (1 - reduction) * (duree_h / 24)
    eco_kwh = baseline * reduction * (duree_h / 24)
    eco_dt = eco_kwh * settings.PRIX_KWH_TN
    co2_kg = eco_kwh * settings.FACTEUR_CO2_TN

    r1, r2, r3 = st.columns(3)
    with r1:
        kpi_card("Cout simule", f"{eco_dt:,.0f} DT", "Economie vs baseline", "green")
    with r2:
        kpi_card("Energie", f"{eco_kwh:,.0f} kWh", "economises", "eco")
    with r3:
        kpi_card("CO2 evite", f"{co2_kg/1000:.2f} t", "", "blue")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    hours = list(range(24))
    base_profile = [baseline / 24] * 24
    sim_profile = [v * (1 - reduction if heure_debut <= h <= heure_fin else 1) for h, v in enumerate(base_profile)]

    with section("Consommation simulee vs baseline (24h)"):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hours, y=base_profile, name="Baseline", line=dict(color="#94a3b8")))
        fig.add_trace(go.Scatter(x=hours, y=sim_profile, name="Scenario ECO", line=dict(color="#059669", width=2.5)))
        fig.update_layout(template=template, xaxis_title="Heure", yaxis_title="kWh",
                          height=300, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, width="stretch")

    if st.button("Appliquer le scenario", type="primary"):
        moteur = MoteurDecisionEnergie()
        sample = df.head(min(200, len(df))).copy()
        sample["heure"] = sample["heure"].where(
            (sample["heure"] >= heure_debut) & (sample["heure"] <= heure_fin),
            sample["heure"],
        )
        decided = moteur.appliquer_sur_dataset(sample)
        st.success(f"Scenario applique sur {len(decided)} mesures — moteur NB3 execute.")
        show_cols = ["station_id", "mode_operation", "action_principale"]
        show_cols = [c for c in show_cols if c in decided.columns]
        st.dataframe(decided[show_cols].head(15), width="stretch", hide_index=True)
