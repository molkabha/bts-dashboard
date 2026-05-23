"""Page 1 - Carte du parc BTS."""

from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import (
    MODE_COLORS,
    MODE_ORDER,
    PLOTLY_DARK,
    PLOTLY_LIGHT,
    mode_category_order,
    mode_color_discrete_map,
    normalize_mode_key,
)
from security.middleware import security_middleware
from ui.components import header, section
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


def _render_mode_legend() -> None:
    items = "".join(
        f'<span style="margin-right:14px;">'
        f'<span style="color:{html.escape(MODE_COLORS[m])};font-size:16px;font-weight:900;">●</span> '
        f'<span style="font-size:12px;font-weight:700;color:#64748b;">{html.escape(m)}</span></span>'
        for m in MODE_ORDER
    )
    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin:4px 0 10px 0;">{items}</div>',
        unsafe_allow_html=True,
    )


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
    if "mode_actuel" in plot_scores.columns:
        color_col = "mode_actuel"
        plot_scores = _normalize_mode_column(plot_scores, "mode_actuel")
    elif "categorie" in plot_scores.columns:
        color_col = "categorie"
        plot_scores = _normalize_mode_column(plot_scores, "categorie")

    size_col = "conso_moy" if "conso_moy" in plot_scores.columns else None
    hover_cols = [
        c for c in ["station_id", "gouvernorat", "technologie", "conso_moy", "mode_actuel", "categorie"]
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
        _render_mode_legend()
        fig = px.scatter_mapbox(
            plot_scores,
            color=color_col,
            color_discrete_map=mode_color_discrete_map(plot_scores[color_col]),
            category_orders={color_col: mode_category_order(plot_scores[color_col])},
            labels={color_col: "Mode"},
            **base_kwargs,
        )
    else:
        fig = px.scatter_mapbox(plot_scores, **base_kwargs)

    center_lat = plot_scores["latitude"].mean()
    center_lon = plot_scores["longitude"].mean()
    fig.update_layout(
        template=template,
        mapbox=dict(center=dict(lat=center_lat, lon=center_lon), zoom=6),
        margin=dict(l=0, r=0, t=8, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, title_text="Mode"),
    )
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

    subtitle = "Localisation par mode opérationnel (Mapbox)"
    if not is_admin():
        subtitle = "Vos stations — couleur = dernier mode NB3"
    header("Carte", subtitle)
    st.caption(active_filter_label())

    df = load_dashboard_df(["mode_operation", "latitude", "longitude"])
    if df.empty:
        st.warning("Aucune donnée pour les filtres actifs.")
        return

    nb_stations = df["station_id"].nunique() if "station_id" in df.columns else 0
    st.caption(f"{nb_stations} stations · CRITIQUE rouge · ATTENTION jaune · NORMAL vert · ECO bleu-vert")

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
