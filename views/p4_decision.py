"""Page 4 - Systeme de decision NB3 (ingenieur)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config.settings import settings
from config.theme import MODE_COLORS
from security.middleware import security_middleware
from ui.components import header, section
from ui.page_helpers import load_dashboard_df, mode_explanation


def page_decision():
    security_middleware.enforce()
    header("Systeme de decision", "Moteur NB3 — modes operationnels et economies")

    df = load_dashboard_df()
    if df.empty:
        st.warning("Aucune donnee disponible.")
        return

    # Decision cards (economies / modes : voir Vue executive et Optimisation)
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
