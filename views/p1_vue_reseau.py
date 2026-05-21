"""Page 1 - Vue Globale Reseau : carte Folium, KPIs, tableau."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from security.middleware import security_middleware
from services.data_service import (
    artifact_table,
    compute_filtered_kpis,
    load_filtered_main_data,
    station_summary_from_df,
)
from ui.components import header, kpi_card, section
from ui.utils import metric_value, download_df_button, apply_current_admin_filters, filter_artifact_dataframe


def _render_folium_map(scores: pd.DataFrame):
    """Render interactive Folium map with colored station markers."""
    if scores.empty or not {"latitude", "longitude"}.issubset(scores.columns):
        st.warning("Coordonnees GPS indisponibles pour la carte.")
        return

    import folium
    from streamlit_folium import st_folium

    center_lat = scores["latitude"].mean()
    center_lon = scores["longitude"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="OpenStreetMap")

    mode_col = None
    for candidate in ["mode_operation", "categorie"]:
        if candidate in scores.columns:
            mode_col = candidate
            break

    color_map = {"ECO": "#059669", "NORMAL": "#2563eb", "ATTENTION": "#d97706", "CRITIQUE": "#c8102e",
                 "Faible": "#059669", "Moyenne": "#d97706", "Critique": "#c8102e"}

    conso_col = "conso_moy" if "conso_moy" in scores.columns else "consommation_kwh" if "consommation_kwh" in scores.columns else None
    float(scores[conso_col].max()) if conso_col and not scores[conso_col].dropna().empty else 10

    for _, row in scores.iterrows():
        lat = row.get("latitude")
        lon = row.get("longitude")
        if pd.isna(lat) or pd.isna(lon):
            continue

        station = str(row.get("station_id", ""))
        mode = str(row.get(mode_col, "NORMAL")) if mode_col else "NORMAL"
        color = color_map.get(mode, "#2563eb")
        conso = float(row.get(conso_col, 3)) if conso_col else 3
        radius = 8

        gov = str(row.get("gouvernorat", ""))
        tech = str(row.get("technologie", ""))
        zone = str(row.get("type_zone", ""))
        qos = row.get("score_qos_moy", row.get("score_qos", None))
        qos_str = f"{float(qos):.2f}" if qos is not None and not pd.isna(qos) else "0.00"
        anom = row.get("score_anom_moy", row.get("anomalie_score_ensemble", None))
        anom_str = f"{float(anom):.2f}" if anom is not None and not pd.isna(anom) else "0.00"

        popup_html = f"""
        <div style="font-family:Inter,sans-serif;min-width:220px;">
            <div style="font-weight:800;font-size:14px;margin-bottom:6px;">{station}</div>
            <div style="font-size:12px;color:#64748b;margin-bottom:8px;">{gov} | {tech} | {zone}</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="font-size:12px;">Consommation</span>
                <span style="font-weight:700;font-size:12px;">{conso:.1f} kWh</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="font-size:12px;">Mode</span>
                <span style="font-weight:700;font-size:12px;color:{color};">{mode}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="font-size:12px;">Score QoS</span>
                <span style="font-weight:700;font-size:12px;">{qos_str}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="font-size:12px;">Score anomalie</span>
                <span style="font-weight:700;font-size:12px;">{anom_str}</span>
            </div>
        </div>
        """
        folium.CircleMarker(
            location=[float(lat), float(lon)],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{station} ({mode})",
        ).add_to(m)

    st_folium(m, width=None, height=520, returned_objects=[])


def page_vue_reseau():
    security_middleware.enforce()
    header("Vue Globale Reseau", "Lecture spatiale et operationnelle du reseau")

    cols = [
        "timestamp", "station_id", "gouvernorat", "type_zone", "technologie",
        "consommation_kwh", "conso_predite", "score_qos", "anomalie_score_ensemble",
        "mode_operation", "action_proposee", "economie_estimee_kwh",
        "economie_rl_kwh", "latitude", "longitude",
        "mois", "heure", "jour_semaine", "est_weekend",
    ]
    df_raw = load_filtered_main_data(cols)
    df = apply_current_admin_filters(df_raw)

    if df.empty:
        st.warning("Aucune donnee disponible. Verifiez les filtres ou l'importation des donnees.")
        return

    kpis = compute_filtered_kpis(df)

    # KPI row
    with section("Indicateurs Cles"):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            kpi_card("Consommation totale", metric_value(kpis, "conso_totale_kwh", " kWh", 0), "Periode filtree")
        with c2:
            eco_kwh = kpis.get("economie_rl_pct")
            kpis.get("economie_dt")
            kpi_card("Economies estimees",
                     f"{eco_kwh:.1f}%" if eco_kwh is not None and not pd.isna(eco_kwh) else "0.0%",
                     "Potentiel RL", "blue")
        with c3:
            co2 = kpis.get("co2_evite_t")
            kpi_card("CO2 evite", f"{co2:.1f} t" if co2 is not None and not pd.isna(
                co2) else "0.0 t", "Equivalent carbone", "eco")
        with c4:
            anom_pct = kpis.get("pct_anomalies")
            kpi_card("Anomalies", f"{anom_pct:.1f}%" if anom_pct is not None and not pd.isna(
                anom_pct) else "0.0%", "NB2 detectees", "orange")
        with c5:
            nb_crit = int(df[df["mode_operation"].astype(str) == "CRITIQUE"]
                          ["station_id"].nunique()) if "mode_operation" in df.columns else 0
            kpi_card("Stations critiques", str(nb_crit), "Intervention requise", "red")

    # Map
    with section("Carte Interactive"):
        scores = station_summary_from_df(df)
        _render_folium_map(scores)

    # Table
    with section("Tableau Recapitulatif"):
        if not scores.empty:
            display_cols = [
                "station_id",
                "gouvernorat",
                "technologie",
                "conso_moy",
                "score_qos_moy",
                "score_anom_moy",
                "categorie"]
            display_cols = [c for c in display_cols if c in scores.columns]
            sort_col = "score_anom_moy" if "score_anom_moy" in scores.columns else "station_id"
            st.dataframe(scores.sort_values(sort_col, ascending=False)[display_cols],
                         width="stretch", hide_index=True)
            download_df_button(scores, "stations_reseau.csv", "Exporter CSV")

    with section("Scores Stations Notebook"):
        nb3_scores = filter_artifact_dataframe(artifact_table("streamlit_score_stations.parquet"))
        nb3_map = filter_artifact_dataframe(artifact_table("streamlit_carte_stations.parquet"))
        if not nb3_scores.empty:
            st.caption("Scores stations NB3 synchronises avec les filtres du dashboard quand les colonnes existent.")
            st.dataframe(nb3_scores, width="stretch", hide_index=True)
        if not nb3_map.empty:
            st.caption("Synthese cartographique NB3 synchronisee avec les filtres du dashboard quand les colonnes existent.")
            st.dataframe(nb3_map, width="stretch", hide_index=True)
