"""Shared data-loading helpers for dashboard pages."""

from __future__ import annotations

import plotly.express as px
import pandas as pd
import streamlit as st

from services.data_service import (
    compute_filtered_kpis,
    dataset_cache_key,
    load_filtered_main_data,
    load_station_map_data,
)
from ui.utils import apply_current_admin_filters, filters_cache_key

DEFAULT_COLS = [
    "timestamp", "station_id", "gouvernorat", "technologie", "type_zone",
    "consommation_kwh", "conso_predite", "pred_q10", "pred_q90",
    "anomalie_score_ensemble", "nb_votes_anomalie", "score_qos",
    "mode_operation", "action_proposee", "action_principale",
    "economie_estimee_kwh", "economie_rl_kwh", "economie_kwh", "ecart_pct",
    "heure", "jour_semaine", "mois", "charge_cpu_pct",
    "latitude", "longitude", "meilleur_agent_rl",
]


def get_station_map_data(df: pd.DataFrame) -> pd.DataFrame:
    """Session-cached station map positions for the current filter context."""
    station_token = ""
    if not df.empty and "station_id" in df.columns:
        station_token = str(hash(tuple(sorted(df["station_id"].astype(str).unique()))))
    cache_id = f"{dataset_cache_key()}|{filters_cache_key()}|{station_token}"
    if st.session_state.get("_map_data_key") == cache_id:
        cached = st.session_state.get("_map_data_val")
        if isinstance(cached, pd.DataFrame):
            return cached
    result = load_station_map_data(df)
    st.session_state["_map_data_key"] = cache_id
    st.session_state["_map_data_val"] = result
    return result


def load_dashboard_df(extra_cols: list[str] | None = None) -> pd.DataFrame:
    """Load filtered dashboard data with per-rerun session cache."""
    cols = tuple(dict.fromkeys(DEFAULT_COLS + (extra_cols or [])))
    session_key = f"{dataset_cache_key()}|{filters_cache_key()}|{cols}"
    cached = st.session_state.get("_df_session_val")
    if st.session_state.get("_df_session_key") == session_key and isinstance(cached, pd.DataFrame):
        if all(c in cached.columns for c in cols):
            return cached
    df = apply_current_admin_filters(load_filtered_main_data(list(cols)))
    st.session_state["_df_session_key"] = session_key
    st.session_state["_df_session_val"] = df
    return df


def render_conso_gouvernorat_par_periode(
    df: pd.DataFrame,
    template: str,
    *,
    show_page_filters: bool = False,
) -> None:
    """Bar charts: mean kWh by governorate and month (respects sidebar filters on df)."""
    from ui.utils import active_filter_label, merged_active_filters

    if df.empty:
        st.warning("Aucune donnee pour les filtres actifs.")
        return

    st.caption(active_filter_label())

    top_govs: list[str] | None = None
    if show_page_filters and "gouvernorat" in df.columns:
        avail = sorted(df["gouvernorat"].dropna().astype(str).unique().tolist())
        c1, c2 = st.columns([2, 1])
        with c1:
            picked = st.multiselect(
                "Gouvernorats a comparer",
                avail,
                key="cmp_chart_govs",
                placeholder="Tous (top par consommation)",
            )
        with c2:
            top_n = st.number_input("Max gouvernorats", min_value=3, max_value=24, value=10, key="cmp_chart_top_n")
        top_govs = picked if picked else None
        if not top_govs:
            top_govs = (
                df.groupby("gouvernorat")["consommation_kwh"]
                .sum()
                .sort_values(ascending=False)
                .head(int(top_n))
                .index.astype(str)
                .tolist()
            )

    if "gouvernorat" not in df.columns or "consommation_kwh" not in df.columns:
        st.info("Colonnes gouvernorat / consommation indisponibles.")
        return

    if "timestamp" not in df.columns:
        work = df
        if top_govs:
            work = work[work["gouvernorat"].astype(str).isin(top_govs)]
        by_gov = work.groupby("gouvernorat", as_index=False)["consommation_kwh"].mean()
        by_gov = by_gov.rename(columns={"consommation_kwh": "conso_moy_kwh"}).sort_values("conso_moy_kwh", ascending=True)
        fig = px.bar(by_gov, x="conso_moy_kwh", y="gouvernorat", orientation="h", template=template)
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, width="stretch")
        return

    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work = work.dropna(subset=["timestamp", "gouvernorat"])
    if top_govs:
        work = work[work["gouvernorat"].astype(str).isin(top_govs)]
    if work.empty:
        st.warning("Aucune ligne apres filtrage gouvernorat.")
        return

    work["periode"] = work["timestamp"].dt.to_period("M").astype(str)
    by_period = (
        work.groupby(["periode", "gouvernorat"], as_index=False)["consommation_kwh"]
        .mean()
        .rename(columns={"consommation_kwh": "conso_moy_kwh"})
        .sort_values("periode")
    )
    if top_govs is None:
        top_govs = (
            work.groupby("gouvernorat")["consommation_kwh"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .index.astype(str)
            .tolist()
        )
    chart_df = by_period[by_period["gouvernorat"].astype(str).isin(top_govs)]

    fig_period = px.bar(
        chart_df,
        x="periode",
        y="conso_moy_kwh",
        color="gouvernorat",
        barmode="group",
        template=template,
        labels={
            "periode": "Periode (mois)",
            "conso_moy_kwh": "Consommation moyenne (kWh)",
            "gouvernorat": "Gouvernorat",
        },
        title="Moyenne par mois et par gouvernorat",
    )
    fig_period.update_layout(height=340, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_period, width="stretch")

    gf = merged_active_filters()
    if gf.get("date_range"):
        start, end = gf["date_range"]
        period_label = f"Periode filtree : {start} → {end}"
    elif not chart_df.empty:
        period_label = f"Periodes : {chart_df['periode'].min()} → {chart_df['periode'].max()}"
    else:
        period_label = ""
    st.caption(f"{period_label} · {len(top_govs)} gouvernorat(s)".strip(" · "))

    by_gov = (
        work.groupby("gouvernorat", as_index=False)["consommation_kwh"]
        .mean()
        .rename(columns={"consommation_kwh": "conso_moy_kwh"})
        .sort_values("conso_moy_kwh", ascending=True)
    )
    fig_gov = px.bar(
        by_gov,
        x="conso_moy_kwh",
        y="gouvernorat",
        orientation="h",
        template=template,
        labels={"conso_moy_kwh": "Conso moyenne (kWh)", "gouvernorat": "Gouvernorat"},
        title="Moyenne sur la periode selectionnee",
    )
    fig_gov.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_gov, width="stretch")


def fleet_status_metrics(df: pd.DataFrame) -> dict:
    """Compute global status bar metrics from filtered dataframe."""
    if df.empty:
        return {
            "critiques": 0, "attention": 0, "ok": 0,
            "conso_instant": 0.0, "pct_eco": 0.0, "eei_moy": 0.0,
        }
    modes = df["mode_operation"].astype(str) if "mode_operation" in df.columns else pd.Series(dtype=str)
    if "station_id" in df.columns and not modes.empty:
        latest = df.sort_values("timestamp", ascending=False).groupby("station_id").first() if "timestamp" in df.columns else df.groupby("station_id").last()
        modes = latest["mode_operation"].astype(str) if "mode_operation" in latest.columns else modes
        stations = latest.index.nunique()
    else:
        stations = df["station_id"].nunique() if "station_id" in df.columns else 0

    critiques = int((modes == "CRITIQUE").sum())
    attention = int((modes == "ATTENTION").sum())
    ok = max(0, int(stations) - critiques - attention) if stations else 0

    if "timestamp" in df.columns:
        last_ts = df["timestamp"].max()
        snap = df[df["timestamp"] == last_ts] if pd.notna(last_ts) else df.tail(min(100, len(df)))
    else:
        snap = df.tail(min(100, len(df)))

    conso = pd.to_numeric(snap.get("consommation_kwh", pd.Series(dtype=float)), errors="coerce").sum()
    kpis = compute_filtered_kpis(df)
    pct_eco = float(kpis.get("pct_mode_eco") or 0)

    eei = None
    if "consommation_kwh" in snap.columns and "trafic_data_mbps" in snap.columns:
        trafic = pd.to_numeric(snap["trafic_data_mbps"], errors="coerce").replace(0, pd.NA)
        eei = (pd.to_numeric(snap["consommation_kwh"], errors="coerce") / trafic).mean()
    if eei is None or pd.isna(eei):
        conso_vals = pd.to_numeric(snap.get("consommation_kwh", pd.Series(dtype=float)), errors="coerce")
        eei = float(conso_vals.mean()) if not conso_vals.empty else 0.0

    return {
        "critiques": critiques,
        "attention": attention,
        "ok": ok,
        "conso_instant": float(conso or 0),
        "pct_eco": pct_eco,
        "eei_moy": float(eei) if eei is not None and not pd.isna(eei) else 0.0,
    }


def mode_explanation(row: pd.Series) -> str:
    """Short operational explanation for current mode."""
    mode = str(row.get("mode_operation", "NORMAL"))
    heure = int(row.get("heure", 12) or 12)
    cpu = float(row.get("charge_cpu_pct", 0) or 0)
    score = float(row.get("anomalie_score_ensemble", 0) or 0)
    if mode == "ECO":
        return f"Mode ECO declenche car heure creuse ({heure}h), CPU {cpu:.0f}%, score anomalie faible ({score:.2f})"
    if mode == "CRITIQUE":
        return f"Mode CRITIQUE : score anomalie eleve ({score:.2f}) ou consensus detecteurs fort"
    if mode == "ATTENTION":
        ecart = abs(float(row.get("ecart_pct", 0) or 0))
        return f"Mode ATTENTION : ecart consommation {ecart:.1f}% vs profil ou score {score:.2f}"
    return f"Mode NORMAL : supervision standard, score anomalie {score:.2f}"
