"""Page 4 - Systeme de decision NB3 (ingenieur)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import MODE_COLORS, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from ui.components import header, kpi_card, section
from services.data_service import compute_filtered_kpis
from ui.page_helpers import load_dashboard_df, mode_explanation


def page_decision():
    security_middleware.enforce()
    header("Systeme de decision", "Moteur NB3 — modes operationnels et economies")

    df = load_dashboard_df()
    if df.empty:
        st.warning("Aucune donnee disponible.")
        return

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    if "mode_operation" in df.columns:
        mode_counts = df["mode_operation"].astype(str).value_counts().reset_index()
        mode_counts.columns = ["Mode", "Nb"]
        with section("Repartition modes operationnels"):
            fig = px.bar(mode_counts, x="Mode", y="Nb", color="Mode",
                         color_discrete_map=MODE_COLORS, title="Flotte en ce moment")
            fig.update_layout(template=template, margin=dict(l=0, r=0, t=30, b=0), height=280, showlegend=False)
            st.plotly_chart(fig, width="stretch")

    kpis = compute_filtered_kpis(df)
    eco_total = float(kpis.get("economie_kwh") or 0)
    eco_dt = float(kpis.get("economie_dt") or 0)
    co2_kg = float(kpis.get("co2_evite_t") or 0) * 1000

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Economies cumulees", f"{eco_dt:,.0f} DT", kpis.get("economie_periode_label", "NB3"), "green")
    with c2:
        kpi_card("Energie economisee", f"{eco_total:,.0f} kWh", "", "eco")
    with c3:
        kpi_card("CO2 evite", f"{co2_kg/1000:.2f} t", "", "blue")

    # Decision cards + priority table
    if "station_id" in df.columns:
        latest = df.sort_values("timestamp").groupby("station_id", as_index=False).last() if "timestamp" in df.columns else df.groupby("station_id", as_index=False).last()
        prio = {"CRITIQUE": 0, "ATTENTION": 1, "NORMAL": 2, "ECO": 3}
        latest = latest.copy()
        latest["_prio"] = latest["mode_operation"].astype(str).map(lambda m: prio.get(m, 9))
        latest = latest.sort_values("_prio")

        with section("Decisions par station (priorite decroissante)"):
            display = latest.head(20)
            for _, row in display.iterrows():
                mode = str(row.get("mode_operation", "NORMAL"))
                color = MODE_COLORS.get(mode, "#64748b")
                action = str(row.get("action_proposee", row.get("action_principale", "Monitoring")))
                eco = float(row.get("economie_estimee_kwh", 0) or 0) * settings.PRIX_KWH_TN
                expl = mode_explanation(row)
                sid = str(row.get("station_id", ""))
                st.markdown(f"""
<div class="decision-card" style="border-left-color:{color};">
  <div class="dc-mode" style="color:{color};">{sid} — {mode}</div>
  <div class="dc-action">{action}</div>
  <div class="dc-reason">{expl}</div>
  <div class="dc-saving">Economie potentielle : {eco:.2f} DT | {float(row.get('economie_estimee_kwh', 0) or 0):.2f} kWh</div>
</div>""", unsafe_allow_html=True)
