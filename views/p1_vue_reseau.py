"""Page 1 - Carte du parc BTS."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import (
    PLOTLY_DARK,
    PLOTLY_LIGHT,
    map_action_color_discrete_map,
    mode_category_order,
    mode_color_discrete_map,
    normalize_mode_key,
)
from security.middleware import security_middleware
from services.data_service import latest_action_per_station
from ui.components import header, section
from ui.page_helpers import get_station_map_data, load_dashboard_df
from ui.utils import active_filter_label, is_admin


def _attach_station_last_action(df: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    if df.empty or scores.empty or "station_id" not in scores.columns:
        return scores
    latest = latest_action_per_station(df, prefer_rl=False)
    if latest.empty:
        return scores
    out = scores.merge(
        latest.rename(columns={"action_label": "action_actuelle"}),
        on="station_id",
        how="left",
    )
    keep = set(df["station_id"].astype(str).unique())
    return out[out["station_id"].astype(str).isin(keep)]


def _normalize_mode_column(plot_scores: pd.DataFrame, column: str) -> pd.DataFrame:
    out = plot_scores.copy()
    if column not in out.columns:
        return out

    def _clean(value) -> str:
        if pd.isna(value) or str(value).strip().lower() in {"", "none", "nan"}:
            return "NORMAL"
        return normalize_mode_key(value) or "NORMAL"

    out[column] = out[column].map(_clean)
    return out


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

    color_col = None
    if "action_actuelle" in plot_scores.columns:
        color_col = "action_actuelle"
        plot_scores["action_actuelle"] = plot_scores["action_actuelle"].fillna("Maintien").astype(str)
    elif "mode_actuel" in plot_scores.columns:
        color_col = "mode_actuel"
        plot_scores = _normalize_mode_column(plot_scores, "mode_actuel")
    elif "categorie" in plot_scores.columns:
        color_col = "categorie"
        plot_scores = _normalize_mode_column(plot_scores, "categorie")

    size_col = "conso_moy" if "conso_moy" in plot_scores.columns else None
    hover_cols = [
        c for c in [
            "station_id", "gouvernorat", "technologie", "conso_moy",
            "action_actuelle", "mode_actuel", "categorie",
        ]
        if c in plot_scores.columns
    ]
    if is_admin() and "score_criticite" in plot_scores.columns and "score_criticite" not in hover_cols:
        hover_cols.append("score_criticite")

    base_kwargs = dict(
        lat="latitude",
        lon="longitude",
        size=size_col,
        hover_name="station_id" if "station_id" in plot_scores.columns else None,
        hover_data=hover_cols,
        zoom=6,
        height=520,
        mapbox_style="open-street-map",
    )

    if color_col:
        color_map = (
            map_action_color_discrete_map(plot_scores[color_col])
            if color_col == "action_actuelle"
            else mode_color_discrete_map(plot_scores[color_col])
        )
        category_orders = (
            {color_col: sorted(plot_scores[color_col].dropna().astype(str).unique())}
            if color_col == "action_actuelle"
            else {color_col: mode_category_order(plot_scores[color_col])}
        )
        color_label = "Action" if color_col == "action_actuelle" else "Mode"
        fig = px.scatter_mapbox(
            plot_scores,
            color=color_col,
            color_discrete_map=color_map,
            category_orders=category_orders,
            labels={color_col: color_label},
            **base_kwargs,
        )
    else:
        fig = px.scatter_mapbox(plot_scores, **base_kwargs)

    center_lat = plot_scores["latitude"].mean()
    center_lon = plot_scores["longitude"].mean()
    layout_kwargs: dict = {
        "template": template,
        "mapbox": dict(center=dict(lat=center_lat, lon=center_lon), zoom=6),
        "margin": dict(l=0, r=0, t=8, b=0),
    }
    if color_col == "action_actuelle":
        layout_kwargs["showlegend"] = True
        layout_kwargs["legend"] = dict(title="Dernière action")
    else:
        layout_kwargs["showlegend"] = False
    fig.update_layout(**layout_kwargs)
    if color_col and size_col is None:
        fig.update_traces(marker=dict(opacity=0.88, size=11))
    elif color_col:
        fig.update_traces(marker=dict(opacity=0.88))
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

    subtitle = "Localisation par dernière action NB3 (Mapbox)"
    if not is_admin():
        subtitle = "Vos stations — couleur = dernière action"
    header("Carte", subtitle)
    st.caption(active_filter_label())

    df = load_dashboard_df([
        "mode_operation", "action_rl", "action_proposee", "action_principale",
        "latitude", "longitude",
    ])
    if df.empty:
        st.warning("Aucune donnée pour les filtres actifs.")
        return

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    scores = get_station_map_data(df)
    scores = _attach_station_last_action(df, scores)

    _render_mapbox(scores, template)
    _render_comparison(df, template)

    with section("Liste des stations"):
        tbl_cols = ["station_id", "gouvernorat", "technologie", "conso_moy", "score_qos_moy"]
        if is_admin():
            tbl_cols.extend(["score_criticite", "categorie"])
        if "action_actuelle" in scores.columns:
            tbl_cols.insert(3, "action_actuelle")
        elif "mode_actuel" in scores.columns:
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
