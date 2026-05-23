"""Page 10 - Comparaison gouvernorats / technologies (admin)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from ui.components import header, section
from ui.page_helpers import load_dashboard_df


def page_comparaison():
    security_middleware.enforce()
    header("Comparaison", "Benchmark gouvernorats et technologies")

    df = load_dashboard_df()
    if df.empty:
        st.warning("Aucune donnee.")
        return

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    with section("Consommation moyenne par gouvernorat"):
        if "gouvernorat" in df.columns:
            by_gov = df.groupby("gouvernorat")["consommation_kwh"].mean().reset_index()
            by_gov.columns = ["Gouvernorat", "Conso moyenne kWh"]
            fig = px.bar(by_gov.sort_values("Conso moyenne kWh", ascending=False),
                         x="Gouvernorat", y="Conso moyenne kWh")
            fig.update_layout(template=template, height=320, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, width="stretch")

    with section("Par technologie"):
        if "technologie" in df.columns:
            by_tech = df.groupby("technologie").agg(
                conso=("consommation_kwh", "mean"),
                qos=("score_qos", "mean"),
                anomalies=("anomalie_score_ensemble", "mean"),
            ).reset_index()
            st.dataframe(by_tech.round(2), width="stretch", hide_index=True)
