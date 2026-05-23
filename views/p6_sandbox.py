"""Page 6 - Simulation scenarios from NB3 notebook artefacts."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import (
    artifact_table,
    build_nb3_profil_horaire,
    compute_filtered_kpis,
    engineer_assigned_stations,
    load_filtered_main_data,
    load_nb3_network_kpi,
)
from ui.components import header, kpi_card, section
from ui.utils import apply_current_admin_filters


def _apply_scenario(df: pd.DataFrame, nb_eco: int, heure_debut: int, heure_fin: int) -> pd.DataFrame:
    """Filter / highlight NB3 rows matching a what-if ECO scenario on real data."""
    if df.empty:
        return df
    out = df.copy()
    out["heure"] = pd.to_numeric(out.get("heure", 0), errors="coerce").fillna(0).astype(int)
    in_window = out["heure"].between(heure_debut, heure_fin)

    if "station_id" in out.columns:
        stations = sorted(out["station_id"].astype(str).unique())
        eco_stations = set(stations[:nb_eco])
        out = out[in_window & out["station_id"].astype(str).isin(eco_stations)]
    else:
        out = out[in_window]

    if "mode_operation" in out.columns:
        out = out[out["mode_operation"].astype(str).eq("ECO")]
    return out


def page_sandbox():
    security_middleware.enforce()
    header("Simulation", "Scenarios sur donnees NB3 (decisions et profils horaires)")

    role = st.session_state.get("role")
    cols = [
        "timestamp", "station_id", "consommation_kwh", "heure", "mode_operation",
        "action_proposee", "action_rl", "economie_estimee_kwh", "economie_rl_kwh",
        "economie_kwh", "score_qos", "anomalie_score_ensemble",
    ]
    df_raw = load_filtered_main_data(cols)
    df = apply_current_admin_filters(df_raw)

    if role != "admin":
        assigned = engineer_assigned_stations(st.session_state.get("username", ""))
        if assigned and "station_id" in df.columns:
            df = df[df["station_id"].astype(str).isin(assigned)]

    if df.empty:
        st.warning("Aucune donnee NB3 disponible pour la simulation.")
        return

    kpi = load_nb3_network_kpi()
    kpis = compute_filtered_kpis(df)
    nb_stations_max = int(kpi.get("nb_stations") or df["station_id"].nunique() or 1)
    profil_ref = build_nb3_profil_horaire(df)

    st.caption("Source : streamlit_data.parquet + decisions_par_station.parquet (notebooks NB3).")

    with section("Parametres du scenario"):
        c1, c2, c3 = st.columns(3)
        with c1:
            nb_eco = st.slider("Stations mode ECO (filtre)", 1, nb_stations_max, min(10, nb_stations_max))
        with c2:
            heure_debut, heure_fin = st.slider("Plage horaire", 0, 23, (0, 6))
        with c3:
            duree_h = st.slider("Fenetre analyse (h)", 1, 24, heure_fin - heure_debut + 1)

    scenario_df = _apply_scenario(df, nb_eco, heure_debut, heure_fin)
    if scenario_df.empty:
        st.warning("Aucune mesure NB3 en mode ECO pour ce scenario — affichage de la plage horaire.")
        if "heure" in df.columns:
            h = pd.to_numeric(df["heure"], errors="coerce")
            scenario_df = df[h.between(heure_debut, heure_fin)]
        else:
            scenario_df = df.head(100)

    scen_kpis = compute_filtered_kpis(scenario_df)
    eco_kwh = float(scen_kpis.get("economie_kwh") or 0) * (duree_h / 24)
    eco_dt = eco_kwh * settings.PRIX_KWH_TN
    co2_kg = eco_kwh * settings.FACTEUR_CO2_TN

    r1, r2, r3 = st.columns(3)
    with r1:
        kpi_card("Economie scenario", f"{eco_dt:,.0f} DT", "NB3 (filtre ECO)", "green")
    with r2:
        kpi_card("Energie", f"{eco_kwh:,.0f} kWh", f"{len(scenario_df):,} mesures", "eco")
    with r3:
        kpi_card("CO2 evite", f"{co2_kg/1000:.2f} t", "", "blue")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    if not profil_ref.empty and "heure" in profil_ref.columns:
        hours = profil_ref["heure"].tolist()
        base_profile = profil_ref["conso_moy"].tolist()
        opt_col = "conso_optimisee_rl_moy" if "conso_optimisee_rl_moy" in profil_ref.columns else "conso_optimisee_moy"
        opt_profile = profil_ref[opt_col].tolist() if opt_col in profil_ref.columns else base_profile
    else:
        hours, base_profile, opt_profile = list(range(24)), [0.0] * 24, [0.0] * 24

    with section("Profil horaire NB3 (baseline vs optimise)"):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hours, y=base_profile, name="Baseline NB3", line=dict(color="#94a3b8")))
        fig.add_trace(go.Scatter(x=hours, y=opt_profile, name="Optimise NB3", line=dict(color="#059669", width=2.5)))
        fig.update_layout(template=template, xaxis_title="Heure", yaxis_title="kWh moy",
                          height=300, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, width="stretch")

    decisions = artifact_table("decisions_par_station.parquet")
    with section("Decisions NB3 (station x heure)"):
        if not decisions.empty:
            dec = decisions.copy()
            if "heure" in dec.columns:
                dec = dec[pd.to_numeric(dec["heure"], errors="coerce").between(heure_debut, heure_fin)]
            if "station_id" in dec.columns and nb_eco:
                top_stations = df["station_id"].astype(str).value_counts().head(nb_eco).index
                dec = dec[dec["station_id"].astype(str).isin(top_stations)]
            show = [c for c in [
                "station_id", "heure", "mode_operation", "action_rl",
                "economie_rl_kwh", "economie_estimee_kwh",
            ] if c in dec.columns]
            st.dataframe(dec[show].head(30), width="stretch", hide_index=True)
        else:
            st.info("decisions_par_station.parquet non disponible.")

    with section("Echantillon mesures scenario"):
        show_cols = [c for c in [
            "station_id", "timestamp", "heure", "mode_operation",
            "action_proposee", "economie_estimee_kwh", "economie_rl_kwh", "consommation_kwh",
        ] if c in scenario_df.columns]
        st.dataframe(scenario_df[show_cols].head(20), width="stretch", hide_index=True)

    st.caption(
        f"Reference reseau : {float(kpis.get('economie_dt') or 0):,.0f} DT cumul | "
        f"meilleur agent {kpi.get('meilleur_agent_rl', '—')}"
    )
