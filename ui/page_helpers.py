"""Shared data-loading helpers for dashboard pages."""

from __future__ import annotations

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
