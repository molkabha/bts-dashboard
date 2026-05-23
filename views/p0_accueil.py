"""Page 0 - Accueil."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import MODE_COLORS, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import compute_filtered_kpis, load_nb2_network_stats
from ui.components import header, kpi_card, section
from ui.page_helpers import get_station_map_data, load_dashboard_df, render_executive_report_export
from ui.utils import active_filter_label, is_admin


def page_accueil():
    security_middleware.enforce()

    subtitle = "Synthese reseau sur la periode filtree"
    if not is_admin():
        subtitle = "Vos stations assignees — vue operationnelle"
    header("Accueil", subtitle)
    st.caption(active_filter_label())

    df = load_dashboard_df()
    if df.empty:
        st.warning("Aucune donnee pour les filtres actifs.")
        return

    kpis = compute_filtered_kpis(df)
    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    nb_stations = int(df["station_id"].nunique()) if "station_id" in df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    if is_admin():
        nb2_stats = load_nb2_network_stats()
        seuil = float(nb2_stats.get("seuil_ensemble") or 0.25)
        scores = pd.to_numeric(df.get("anomalie_score_ensemble", 0), errors="coerce").fillna(0)
        with c1:
            eco_dt = kpis.get("economie_dt") or 0
            kpi_card("Economies", f"{eco_dt:,.0f} DT", kpis.get("economie_periode_label", "Periode filtree"), "green")
        with c2:
            kpi_card("CO2 evite", f"{float(kpis.get('co2_evite_t') or 0):.1f} t", "", "eco")
        with c3:
            kpi_card("Stations ECO", f"{float(kpis.get('pct_mode_eco') or 0):.1f}%", "", "eco")
        with c4:
            kpi_card("Alertes ML", str(int((scores > seuil).sum())), f"Score > {seuil:.2f}", "orange")
    else:
        conso_moy = float(kpis.get("conso_moyenne_kwh") or 0)
        qos_raw = kpis.get("score_qos_moyen")
        qos_moy = float(qos_raw) * 100 if qos_raw is not None else 0
        with c1:
            kpi_card("Stations", str(nb_stations), "Parc assigne", "blue")
        with c2:
            kpi_card("Conso moyenne", f"{conso_moy:.1f} kWh", "Periode filtree", "gray")
        with c3:
            kpi_card("Mode ECO", f"{float(kpis.get('pct_mode_eco') or 0):.1f}%", "", "eco")
        with c4:
            kpi_card("QoS moyen", f"{qos_moy:.0f}%", "Indicateur reseau", "blue")

    c1, c2 = st.columns(2)
    with c1:
        with section("Repartition des modes"):
            if "mode_operation" in df.columns:
                mode_counts = df["mode_operation"].value_counts().reset_index()
                mode_counts.columns = ["Mode", "Nb"]
                fig = px.pie(
                    mode_counts,
                    names="Mode",
                    values="Nb",
                    hole=0.45,
                    color="Mode",
                    color_discrete_map=MODE_COLORS,
                )
                fig.update_layout(template=template, height=280, margin=dict(l=0, r=0, t=8, b=0))
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Colonne mode_operation indisponible.")

    with c2:
        with section("Top 5 stations critiques"):
            scores_df = get_station_map_data(df)
            if scores_df.empty:
                st.info("Aucune station a classer.")
            else:
                if is_admin() and "score_criticite" in scores_df.columns:
                    sort_col = "score_criticite"
                elif "conso_moy" in scores_df.columns:
                    sort_col = "conso_moy"
                elif "score_qos_moy" in scores_df.columns:
                    scores_df = scores_df.copy()
                    scores_df["_prio_qos"] = 1 - pd.to_numeric(scores_df["score_qos_moy"], errors="coerce").fillna(0.75)
                    sort_col = "_prio_qos"
                else:
                    sort_col = "station_id"
                cols = [c for c in [
                    "station_id", "gouvernorat", "technologie", "mode_actuel",
                    "conso_moy", "score_criticite", "categorie", "score_qos_moy",
                ] if c in scores_df.columns or c == "mode_actuel"]
                top = scores_df.sort_values(sort_col, ascending=False).head(5)
                if "mode_actuel" not in top.columns and "mode_operation" in df.columns:
                    modes = df.sort_values("timestamp").groupby("station_id")["mode_operation"].last() if "timestamp" in df.columns else df.groupby("station_id")["mode_operation"].first()
                    top = top.merge(modes.rename("mode_actuel"), left_on="station_id", right_index=True, how="left")
                show_cols = [c for c in cols if c in top.columns]
                st.dataframe(top[show_cols], width="stretch", hide_index=True)

    if is_admin():
        render_executive_report_export(kpis)
