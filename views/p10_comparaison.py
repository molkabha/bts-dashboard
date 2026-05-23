"""Page 10 - Comparaison (admin)."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from ui.components import header, section
from ui.page_helpers import load_dashboard_df
from ui.utils import active_filter_label


def page_comparaison():
    security_middleware.enforce(role="admin")
    header("Comparaison", "Gouvernorats et technologies")
    st.caption(active_filter_label())

    df = load_dashboard_df()
    if df.empty:
        st.warning("Aucune donnee pour les filtres actifs.")
        return

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    if "gouvernorat" in df.columns and "consommation_kwh" in df.columns:
        with section("Conso moyenne par gouvernorat"):
            by_gov = (
                df.groupby("gouvernorat", as_index=False)["consommation_kwh"]
                .mean()
                .nlargest(12, "consommation_kwh")
                .sort_values("consommation_kwh")
            )
            fig = px.bar(by_gov, x="consommation_kwh", y="gouvernorat", orientation="h")
            fig.update_layout(template=template, height=320, margin=dict(l=0, r=0, t=8, b=0), showlegend=False)
            st.plotly_chart(fig, width="stretch")

    if "technologie" in df.columns:
        with section("Par technologie"):
            by_tech = df.groupby("technologie").agg(
                conso=("consommation_kwh", "mean"),
                qos=("score_qos", "mean"),
            ).reset_index().round(2)
            st.dataframe(by_tech, width="stretch", hide_index=True)
