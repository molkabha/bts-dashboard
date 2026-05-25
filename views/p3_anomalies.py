"""Page NB2 — Anomalies."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import MODE_COLORS, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import load_nb2_network_stats
from ui.components import header, kpi_card, section
from ui.data_validation import (
    MSG_ANOM_COL,
    MSG_QOS_COL,
    nb2_seuil_or_warn,
    qos_seuil_or_warn,
    require_column_or_warn,
)
from ui.display import PAGE_ANOMALIES
from ui.formatting import format_dataframe_for_display
from ui.page_helpers import load_dashboard_df
from ui.utils import active_filter_label, is_admin


def _detector_rows(nb2_stats: dict) -> pd.DataFrame:
    detecteurs = nb2_stats.get("detecteurs", {})
    if not isinstance(detecteurs, dict):
        return pd.DataFrame()
    skip = {
        "ensemble", "seuil_ensemble", "threshold_ensemble", "kpi_reseau",
        "seuil", "threshold", "optimal_threshold",
    }
    rows = []
    for name, stats in detecteurs.items():
        if name in skip or not isinstance(stats, dict):
            continue
        pct = stats.get("pct_test", stats.get("pct_anomalies"))
        if pct is None:
            continue
        rows.append({
            "Détecteur": str(name),
            "Anomalies %": pct,
        })
    return pd.DataFrame(rows)


_MAX_SCATTER_POINTS = 2500


def _hourly_metric_chart_df(work: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Agrège par heure (et mode) — évite d'envoyer des milliers de points à Plotly."""
    if work.empty or value_col not in work.columns:
        return pd.DataFrame()
    df = work.copy()
    if "heure" in df.columns:
        df["_heure"] = pd.to_numeric(df["heure"], errors="coerce")
    elif "timestamp" in df.columns:
        df["_heure"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.hour
    else:
        df["_heure"] = 0
    df["_heure"] = df["_heure"].fillna(0).astype(int).clip(0, 23)
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

    group: list[str] = ["_heure"]
    if "mode_operation" in df.columns:
        group.append("mode_operation")

    agg_kwargs: dict = {
        value_col: (value_col, "mean"),
        "mesures": (value_col, "count"),
    }
    if "station_id" in df.columns:
        agg_kwargs["stations"] = ("station_id", "nunique")
    return df.groupby(group, as_index=False).agg(**agg_kwargs)


def _render_hourly_scatter(
    work: pd.DataFrame,
    value_col: str,
    y_label: str,
    seuil: float,
    template: str,
    *,
    seuil_annotation: str | None = None,
) -> None:
    n_rows = len(work)
    chart_df = _hourly_metric_chart_df(work, value_col)
    if chart_df.empty:
        st.info("Aucune donnée pour tracer le graphique.")
        return
    if n_rows > _MAX_SCATTER_POINTS:
        st.caption(
            f"Moyenne par heure sur {n_rows:,} mesures "
            f"({int(chart_df['mesures'].sum()) if 'mesures' in chart_df.columns else len(chart_df)} points affichés)."
        )
    fig = px.scatter(
        chart_df,
        x="_heure",
        y=value_col,
        color="mode_operation" if "mode_operation" in chart_df.columns else None,
        size="mesures" if "mesures" in chart_df.columns else None,
        hover_data=[c for c in ("mesures", "stations", "mode_operation") if c in chart_df.columns],
        labels={"_heure": "Heure", value_col: y_label, "mesures": "Mesures", "stations": "Stations"},
        color_discrete_map=MODE_COLORS,
    )
    fig.add_hline(
        y=seuil,
        line_dash="dash",
        line_color="#c8102e",
        annotation_text=seuil_annotation or "Seuil",
    )
    fig.update_layout(template=template, height=320, margin=dict(l=0, r=0, t=8, b=0))
    st.plotly_chart(fig, width="stretch")


def _priority_stations(work: pd.DataFrame, seuil: float, anom_col: str) -> pd.DataFrame:
    from services.data_service import filter_valid_station_rows

    work = filter_valid_station_rows(work)
    if work.empty or "station_id" not in work.columns:
        return pd.DataFrame()
    agg = work.groupby("station_id", as_index=False).agg(
        score=(anom_col, "max"),
        alertes=(
            anom_col,
            lambda s: int((pd.to_numeric(s, errors="coerce").dropna() > seuil).sum()),
        ),
    )
    if "gouvernorat" in work.columns:
        gov = work.groupby("station_id")["gouvernorat"].first()
        agg["gouvernorat"] = agg["station_id"].map(gov)
    if "mode_operation" in work.columns:
        mode = work.sort_values("timestamp").groupby("station_id")["mode_operation"].last() if "timestamp" in work.columns else work.groupby("station_id")["mode_operation"].first()
        agg["mode"] = agg["station_id"].map(mode)
    return agg.sort_values("score", ascending=False).head(15)


def page_anomalies():
    security_middleware.enforce()

    subtitle = "Score × heure et stations prioritaires"
    if not is_admin():
        subtitle = "Surveillance QoS de vos stations (sans scores ML)"
    header(PAGE_ANOMALIES, subtitle)
    st.caption(active_filter_label())

    df = load_dashboard_df(columns=[
        "station_id", "anomalie_score_ensemble", "nb_votes_anomalie",
        "score_qos", "gouvernorat", "heure", "mode_operation",
    ])
    if df.empty:
        st.warning("Aucune donnée pour les filtres actifs.")
        return

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    if is_admin():
        nb2_stats = load_nb2_network_stats()
        seuil = nb2_seuil_or_warn(nb2_stats)
        anom_col = "anomalie_score_ensemble"
        if seuil is None or not require_column_or_warn(df, anom_col, MSG_ANOM_COL):
            return

        work = df.copy()
        work["_score"] = pd.to_numeric(work[anom_col], errors="coerce")
        scored = work.dropna(subset=["_score"])
        anom_df = scored[scored["_score"] > seuil]

        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Score moyen", f"{scored['_score'].mean():.2f}", "", "orange")
        with c2:
            kpi_card("Mesures en alerte", str(len(anom_df)), f"Score > {seuil:.2f}", "red")
        with c3:
            n_st = int(anom_df["station_id"].nunique()) if not anom_df.empty and "station_id" in anom_df.columns else 0
            kpi_card("Stations touchées", str(n_st), "Au moins une alerte", "blue")

        det_df = _detector_rows(nb2_stats)
        if not det_df.empty:
            with section("Détecteurs NB2"):
                st.dataframe(det_df, width="stretch", hide_index=True)
        src = nb2_stats.get("seuil_ensemble_source", "")
        st.caption(
            f"Seuil consensus (ensemble) : {seuil:.3f}"
            + (f" — source : {src}" if src else "")
        )

        with section("Stations prioritaires"):
            prio = _priority_stations(scored, seuil, anom_col)
            if prio.empty:
                st.success("Aucune station prioritaire.")
            else:
                st.dataframe(format_dataframe_for_display(prio), width="stretch", hide_index=True)

        with section("Score × heure"):
            _render_hourly_scatter(
                scored, "_score", "Score anomalie (moy.)", seuil, template,
            )
    else:
        qos_seuil = qos_seuil_or_warn()
        if qos_seuil is None or not require_column_or_warn(df, "score_qos", MSG_QOS_COL):
            return

        work = df.copy()
        work["_qos"] = pd.to_numeric(work["score_qos"], errors="coerce")
        qos_valid = work.dropna(subset=["_qos"])
        low_qos = qos_valid[qos_valid["_qos"] < qos_seuil]

        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("QoS moyen", f"{qos_valid['_qos'].mean() * 100:.0f}%", "", "blue")
        with c2:
            kpi_card("Alertes QoS", str(len(low_qos)), f"< {qos_seuil:.0%}", "orange")
        with c3:
            n_st = int(qos_valid["station_id"].nunique()) if "station_id" in qos_valid.columns else 0
            kpi_card("Stations", str(n_st), "", "gray")

        with section("Stations à surveiller"):
            if "station_id" in qos_valid.columns:
                prio = (
                    qos_valid.groupby("station_id", as_index=False)
                    .agg(qos=("_qos", "mean"), lignes=("_qos", "count"))
                    .sort_values("qos")
                    .head(15)
                )
                if "gouvernorat" in qos_valid.columns:
                    prio["gouvernorat"] = prio["station_id"].map(
                        qos_valid.groupby("station_id")["gouvernorat"].first()
                    )
                st.dataframe(format_dataframe_for_display(prio), width="stretch", hide_index=True)

        with section("QoS × heure"):
            _render_hourly_scatter(
                qos_valid, "_qos", "QoS moyen", qos_seuil, template, seuil_annotation="Seuil QoS",
            )
