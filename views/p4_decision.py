"""Page 4 - Decision operationnelle NB3 (ingenieur)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config.settings import settings
from config.theme import MODE_COLORS
from security.middleware import security_middleware
from services.data_service import compute_filtered_kpis, load_nb2_network_stats
from ui.components import header, kpi_card, section
from ui.page_helpers import load_dashboard_df, mode_explanation
from ui.utils import active_filter_label


def page_decision():
    security_middleware.enforce()
    header("Decision", "Moteur NB3 — modes operationnels et economies")

    df = load_dashboard_df()
    if df.empty:
        st.warning("Aucune donnee disponible.")
        return

    st.caption(active_filter_label())
    kpis = compute_filtered_kpis(df)
    nb2_stats = load_nb2_network_stats()
    seuil = float(nb2_stats.get("seuil_ensemble") or 0.25)
    scores = pd.to_numeric(df.get("anomalie_score_ensemble", 0), errors="coerce").fillna(0)
    nb_anomalies = int((scores > seuil).sum())

    if "station_id" not in df.columns:
        st.warning("Colonne station_id indisponible.")
        return

    if "timestamp" in df.columns:
        latest = df.sort_values("timestamp").groupby("station_id", as_index=False).last()
    else:
        latest = df.groupby("station_id", as_index=False).last()

    alert_modes = {"CRITIQUE", "ATTENTION"}
    nb_alert_stations = int(latest["mode_operation"].astype(str).isin(alert_modes).sum()) if "mode_operation" in latest.columns else 0
    mode_dom = "—"
    if "mode_operation" in latest.columns and not latest.empty:
        mode_dom = str(latest["mode_operation"].astype(str).mode().iloc[0])

    eco_dt = float(kpis.get("economie_dt") or 0)
    pct_eco = float(kpis.get("pct_mode_eco") or 0)

    with section("Synthese du filtre actif"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi_card("Economies estimees", f"{eco_dt:,.0f} DT", "Reseau filtre", "green")
        with c2:
            kpi_card("% stations ECO", f"{pct_eco:.1f}%", "Dernier etat par station", "eco")
        with c3:
            kpi_card("Stations alerte", str(nb_alert_stations), "CRITIQUE ou ATTENTION", "orange")
        with c4:
            kpi_card(
                "Anomalies NB2",
                str(nb_anomalies),
                f"Mesures score > {seuil:.2f} · mode dominant {mode_dom}",
                "blue",
            )

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
