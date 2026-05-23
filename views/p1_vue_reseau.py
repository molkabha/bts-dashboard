"""Page 1 - Gestion du parc BTS (admin)."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from security.middleware import security_middleware
from services.data_service import station_summary_from_df
from ui.components import header, section
from ui.page_helpers import load_dashboard_df


def _render_folium_map(scores: pd.DataFrame):
    if scores.empty or not {"latitude", "longitude"}.issubset(scores.columns):
        st.warning("Coordonnees GPS indisponibles pour la carte.")
        return

    import folium
    from streamlit_folium import st_folium

    center_lat = scores["latitude"].mean()
    center_lon = scores["longitude"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="OpenStreetMap")

    mode_col = "mode_operation" if "mode_operation" in scores.columns else "categorie"
    color_map = {
        "ECO": "#059669", "NORMAL": "#2563eb", "ATTENTION": "#d97706", "CRITIQUE": "#c8102e",
        "Faible": "#059669", "Moyenne": "#d97706", "Critique": "#c8102e",
    }
    conso_col = "conso_moy" if "conso_moy" in scores.columns else "consommation_kwh"

    for _, row in scores.iterrows():
        lat, lon = row.get("latitude"), row.get("longitude")
        if pd.isna(lat) or pd.isna(lon):
            continue
        station = str(row.get("station_id", ""))
        mode = str(row.get(mode_col, "NORMAL"))
        color = color_map.get(mode, "#2563eb")
        conso = float(row.get(conso_col, 3) or 3)
        popup_html = f"""
        <div style="font-family:Inter,sans-serif;min-width:200px;">
            <b>{html.escape(station)}</b><br>
            {html.escape(str(row.get('gouvernorat','')))} | {html.escape(str(row.get('technologie','')))}<br>
            Mode: <span style="color:{color};font-weight:700;">{html.escape(mode)}</span><br>
            Conso: {conso:.1f} kWh
        </div>"""
        folium.CircleMarker(
            location=[float(lat), float(lon)], radius=9, color=color, fill=True,
            fill_color=color, fill_opacity=0.75,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{station} ({mode})",
        ).add_to(m)

    map_data = st_folium(m, width=None, height=520, returned_objects=["last_object_clicked"])
    clicked = map_data.get("last_object_clicked") if map_data else None
    if clicked and clicked.get("lat"):
        nearest = scores.iloc[
            ((scores["latitude"] - clicked["lat"]) ** 2 + (scores["longitude"] - clicked["lng"]) ** 2).argsort()[:1]
        ]
        if not nearest.empty:
            st.session_state["selected_station_detail"] = str(nearest.iloc[0]["station_id"])
            if st.button("Ouvrir fiche station", type="primary"):
                st.session_state["_nav_override"] = 8
                st.rerun()


def page_vue_reseau():
    security_middleware.enforce()
    header("Gestion du parc", "Carte interactive, filtres et inventaire stations")

    df = load_dashboard_df(["mode_operation", "latitude", "longitude", "derniere_alerte"])
    if df.empty:
        st.warning("Aucune donnee disponible.")
        return

    with section("Filtres"):
        fc1, fc2, fc3, fc4 = st.columns(4)
        filtered = df.copy()
        with fc1:
            if "gouvernorat" in df.columns:
                govs = st.multiselect("Gouvernorat", sorted(df["gouvernorat"].dropna().unique().astype(str)))
                if govs:
                    filtered = filtered[filtered["gouvernorat"].astype(str).isin(govs)]
        with fc2:
            if "technologie" in df.columns:
                techs = st.multiselect("Technologie", sorted(df["technologie"].dropna().unique().astype(str)))
                if techs:
                    filtered = filtered[filtered["technologie"].astype(str).isin(techs)]
        with fc3:
            if "type_zone" in df.columns:
                zones = st.multiselect("Type zone", sorted(df["type_zone"].dropna().unique().astype(str)))
                if zones:
                    filtered = filtered[filtered["type_zone"].astype(str).isin(zones)]
        with fc4:
            if "mode_operation" in df.columns:
                statuts = st.multiselect("Statut", ["ECO", "NORMAL", "ATTENTION", "CRITIQUE"])
                if statuts:
                    filtered = filtered[filtered["mode_operation"].astype(str).isin(statuts)]

    scores = station_summary_from_df(filtered)
    if "mode_operation" in filtered.columns and "station_id" in scores.columns:
        modes = filtered.sort_values("timestamp").groupby("station_id")["mode_operation"].last() if "timestamp" in filtered.columns else filtered.groupby("station_id")["mode_operation"].first()
        scores = scores.merge(modes.rename("mode_actuel"), left_on="station_id", right_index=True, how="left")

    with section("Carte du parc"):
        _render_folium_map(scores)

    with section("Inventaire stations"):
        tbl_cols = ["station_id", "gouvernorat", "technologie", "conso_moy", "score_qos_moy", "categorie"]
        tbl_cols = [c for c in tbl_cols if c in scores.columns]
        if "mode_actuel" in scores.columns:
            tbl_cols.insert(3, "mode_actuel")
        page_size = 15
        total_pages = max(1, (len(scores) + page_size - 1) // page_size)
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
        start = (page - 1) * page_size
        page_df = scores.sort_values("score_criticite", ascending=False).iloc[start:start + page_size]

        selection = st.dataframe(
            page_df[tbl_cols],
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
        )
        if selection and selection.selection.rows:
            idx = selection.selection.rows[0]
            sid = str(page_df.iloc[idx]["station_id"])
            st.session_state["selected_station_detail"] = sid
            if st.button("Voir fiche detail", key="open_station"):
                st.session_state["_nav_override"] = 8
                st.rerun()
