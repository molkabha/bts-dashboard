"""Page 1 - Carte du parc BTS."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import MODE_COLORS, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from ui.components import header, section
from ui.formatting import display_text
from ui.page_helpers import get_station_map_data, load_dashboard_df
from ui.utils import active_filter_label, is_admin


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


def _render_mapbox(scores: pd.DataFrame, template: str):
    if scores.empty or not {"latitude", "longitude"}.issubset(scores.columns):
        st.warning(
            "Coordonnées GPS indisponibles. Vérifiez latitude/longitude dans le jeu de données."
        )
        return

    plot_scores = scores.copy()
    plot_scores["latitude"] = pd.to_numeric(plot_scores["latitude"], errors="coerce")
    plot_scores["longitude"] = pd.to_numeric(plot_scores["longitude"], errors="coerce")
    plot_scores = plot_scores.dropna(subset=["latitude", "longitude"])
    if plot_scores.empty:
        st.warning("Aucune coordonnée GPS valide.")
        return

    color_col = "score_criticite" if is_admin() and "score_criticite" in plot_scores.columns else "mode_actuel"
    if color_col not in plot_scores.columns:
        color_col = "categorie" if "categorie" in plot_scores.columns else None

    size_col = "conso_moy" if "conso_moy" in plot_scores.columns else None
    hover_cols = [c for c in ["station_id", "gouvernorat", "technologie", "conso_moy", "categorie"] if c in plot_scores.columns]

    fig = px.scatter_mapbox(
        plot_scores,
        lat="latitude",
        lon="longitude",
        color=color_col,
        size=size_col,
        hover_name="station_id" if "station_id" in plot_scores.columns else None,
        hover_data=hover_cols,
        color_continuous_scale="Reds" if color_col == "score_criticite" else None,
        color_discrete_map=MODE_COLORS if color_col == "mode_actuel" else None,
        zoom=6,
        height=520,
        mapbox_style="open-street-map",
    )
    center_lat = plot_scores["latitude"].mean()
    center_lon = plot_scores["longitude"].mean()
    fig.update_layout(
        template=template,
        mapbox=dict(center=dict(lat=center_lat, lon=center_lon), zoom=6),
        margin=dict(l=0, r=0, t=8, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, width="stretch")


def _render_comparison(df: pd.DataFrame, template: str):
    with st.expander("Comparaison gouvernorats / technologies", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            if "gouvernorat" in df.columns and "consommation_kwh" in df.columns:
                by_gov = (
                    df.groupby("gouvernorat", as_index=False)["consommation_kwh"]
                    .mean()
                    .nlargest(10, "consommation_kwh")
                    .sort_values("consommation_kwh")
                )
                fig = px.bar(by_gov, x="consommation_kwh", y="gouvernorat", orientation="h")
                fig.update_layout(template=template, height=280, margin=dict(l=0, r=0, t=8, b=0), showlegend=False)
                st.plotly_chart(fig, width="stretch")
        with c2:
            if "technologie" in df.columns:
                by_tech = df.groupby("technologie").agg(
                    conso=("consommation_kwh", "mean"),
                    qos=("score_qos", "mean"),
                ).reset_index().round(2)
                st.dataframe(by_tech, width="stretch", hide_index=True)


def page_vue_reseau():
    security_middleware.enforce()

    subtitle = "Localisation et criticité (Mapbox)"
    if not is_admin():
        subtitle = "Vos stations — état opérationnel"
    header("Carte", subtitle)
    st.caption(active_filter_label())

    df = load_dashboard_df(["mode_operation", "latitude", "longitude"])
    if df.empty:
        st.warning("Aucune donnée pour les filtres actifs.")
        return

    nb_stations = df["station_id"].nunique() if "station_id" in df.columns else 0
    st.caption(f"{nb_stations} stations")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    scores = get_station_map_data(df)
    scores = _attach_station_modes(df, scores)

    _render_mapbox(scores, template)
    _render_comparison(df, template)

    with section("Liste des stations"):
        tbl_cols = ["station_id", "gouvernorat", "technologie", "conso_moy", "score_qos_moy"]
        if is_admin():
            tbl_cols.extend(["score_criticite", "categorie"])
        if "mode_actuel" in scores.columns:
            tbl_cols.insert(3, "mode_actuel")
        tbl_cols = [c for c in tbl_cols if c in scores.columns]
        if scores.empty:
            st.info("Aucune station à afficher.")
            return
        sort_col = "score_criticite" if is_admin() and "score_criticite" in scores.columns else "conso_moy"
        if sort_col not in scores.columns:
            sort_col = "station_id"
        st.dataframe(
            scores.sort_values(sort_col, ascending=False)[tbl_cols].head(50),
            width="stretch",
            hide_index=True,
        )
