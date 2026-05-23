"""Page 1 - Carte du parc BTS (admin)."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from security.middleware import security_middleware
from ui.components import header, section
from ui.page_helpers import get_station_map_data, load_dashboard_df
from ui.utils import active_filter_label


def _render_folium_map(scores: pd.DataFrame):
    if scores.empty or not {"latitude", "longitude"}.issubset(scores.columns):
        st.warning(
            "Coordonnees GPS indisponibles pour la carte. "
            "Verifiez streamlit_carte_stations.parquet ou latitude/longitude dans le dataset."
        )
        return

    plot_scores = scores.copy()
    plot_scores["latitude"] = pd.to_numeric(plot_scores["latitude"], errors="coerce")
    plot_scores["longitude"] = pd.to_numeric(plot_scores["longitude"], errors="coerce")
    plot_scores = plot_scores.dropna(subset=["latitude", "longitude"])
    if plot_scores.empty:
        st.warning("Aucune coordonnee GPS valide.")
        return

    import folium
    from streamlit_folium import st_folium

    center_lat = plot_scores["latitude"].mean()
    center_lon = plot_scores["longitude"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="OpenStreetMap")

    mode_col = "mode_actuel" if "mode_actuel" in plot_scores.columns else (
        "mode_operation" if "mode_operation" in plot_scores.columns else "categorie"
    )
    color_map = {
        "ECO": "#059669", "NORMAL": "#2563eb", "ATTENTION": "#d97706", "CRITIQUE": "#c8102e",
        "Faible": "#059669", "Moyenne": "#d97706", "Critique": "#c8102e",
    }
    conso_col = "conso_moy" if "conso_moy" in plot_scores.columns else "consommation_kwh"

    for _, row in plot_scores.iterrows():
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
        nearest = plot_scores.iloc[
            ((plot_scores["latitude"] - clicked["lat"]) ** 2 + (plot_scores["longitude"] - clicked["lng"]) ** 2).argsort()[:1]
        ]
        if not nearest.empty:
            st.session_state["selected_station_detail"] = str(nearest.iloc[0]["station_id"])
            if st.button("Ouvrir fiche station", type="primary"):
                st.session_state["_nav_override"] = 8
                st.rerun()


def _attach_station_modes(df: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    if df.empty or scores.empty or "station_id" not in scores.columns or "mode_operation" not in df.columns:
        return scores
    if "timestamp" in df.columns:
        modes = df.sort_values("timestamp").groupby("station_id")["mode_operation"].last()
    else:
        modes = df.groupby("station_id")["mode_operation"].first()
    out = scores.merge(modes.rename("mode_actuel"), left_on="station_id", right_index=True, how="left")
    keep = set(df["station_id"].astype(str).unique())
    return out[out["station_id"].astype(str).isin(keep)]


def page_vue_reseau():
    security_middleware.enforce(role="admin")
    header("Carte", "Localisation et etat des stations")
    st.caption(active_filter_label())

    df = load_dashboard_df(["mode_operation", "latitude", "longitude"])
    if df.empty:
        st.warning("Aucune donnee pour les filtres actifs.")
        return

    nb_stations = df["station_id"].nunique() if "station_id" in df.columns else 0
    st.caption(f"{nb_stations} stations")

    scores = get_station_map_data(df)
    scores = _attach_station_modes(df, scores)

    _render_folium_map(scores)

    with section("Liste"):
        tbl_cols = ["station_id", "gouvernorat", "technologie", "conso_moy", "score_qos_moy", "categorie"]
        tbl_cols = [c for c in tbl_cols if c in scores.columns]
        if "mode_actuel" in scores.columns:
            tbl_cols.insert(3, "mode_actuel")
        if scores.empty:
            st.info("Aucune station a afficher.")
            return
        page_size = 15
        total_pages = max(1, (len(scores) + page_size - 1) // page_size)
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
        start = (page - 1) * page_size
        sort_col = "score_criticite" if "score_criticite" in scores.columns else "station_id"
        page_df = scores.sort_values(sort_col, ascending=False).iloc[start:start + page_size]

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
