"""Page 10 - Comparaison gouvernorats / technologies (admin)."""

from __future__ import annotations

import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from ui.components import header, section
from ui.page_helpers import load_dashboard_df, render_conso_gouvernorat_par_periode


def page_comparaison():
    security_middleware.enforce()
    header("Comparaison", "Benchmark gouvernorats et technologies")

    df = load_dashboard_df()
    if df.empty:
        st.warning("Aucune donnee pour les filtres actifs. Ajustez la barre laterale ou reinitialisez les filtres.")
        return

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    with section("Consommation moyenne par gouvernorat (par periode)"):
        render_conso_gouvernorat_par_periode(df, template, show_page_filters=True)

    with section("Par technologie"):
        if "technologie" in df.columns:
            by_tech = df.groupby("technologie").agg(
                conso=("consommation_kwh", "mean"),
                qos=("score_qos", "mean"),
                anomalies=("anomalie_score_ensemble", "mean"),
            ).reset_index()
            st.dataframe(by_tech.round(2), width="stretch", hide_index=True)
        else:
            st.info("Colonne technologie indisponible.")
