from __future__ import annotations

from datetime import date, datetime, time

from typing import Any

import numpy as np

import pandas as pd

from config.settings import settings

from services.data_service import (
    dataset_cache_key,
    engineer_assigned_stations,
    load_enriched_base_dataset,
)

from services.calendar_tn import calendar_context, scenario_timestamps

from services.nb_inference import apply_offline_nb23

from services.nb_metrics import compute_ecart_pct, harmonize_nb3_economies

from services.sim_inference import clear_inference_cache, enrich_with_pipeline

PROFILE_KEYS_BASE = ["station_id", "heure", "mois", "est_weekend"]

META_COLS = [
    "station_id",
    "gouvernorat",
    "technologie",
    "type_zone",
    "latitude",
    "longitude",
]

VALUE_COLS = [
    "consommation_kwh",
    "charge_cpu_pct",
    "temperature_ambiante",
    "score_qos",
    "trafic_data_mbps",
    "pue",
    "taux_charge_data",
    "taux_charge_voix",
    "puissance_emission_dbm",
    "vitesse_vent_ms",
    "humidite_relative_pct",
    "nb_secteurs_actifs",
]


def clear_synthetic_cache() -> None:

    clear_sim_engine_cache()

    clear_inference_cache()


def clear_sim_engine_cache() -> None:

    try:

        import streamlit as st

        for key in (
            "_sim_engine_key",
            "_sim_engine_ref",
            "_sim_engine_profiles",
            "_sim_engine_catalog",
        ):

            st.session_state.pop(key, None)

    except Exception:

        pass


def _ref_columns() -> list[str]:

    return list(
        dict.fromkeys(
            [
                "timestamp",
                "station_id",
                "heure",
                "mois",
                "est_weekend",
                "est_ramadan",
                "est_ferie",
                "est_vendredi",
                "jour_semaine",
            ]
            + META_COLS
            + VALUE_COLS
        )
    )


def _subset_ref_columns(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty:

        return df

    cols = [c for c in _ref_columns() if c in df.columns]

    out = df[cols].copy() if cols else df.copy()

    if "timestamp" in out.columns:

        out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")

    if "heure" not in out.columns and "timestamp" in out.columns:

        out["heure"] = out["timestamp"].dt.hour

    return out


def _load_sim_reference() -> pd.DataFrame:

    cache_key = dataset_cache_key()

    if not cache_key:

        return pd.DataFrame()

    df = load_enriched_base_dataset(cache_key)

    if df.empty:

        return df

    try:

        import streamlit as st

        role = st.session_state.get("role", "")

        if role != "admin" and "station_id" in df.columns:

            assigned = {str(s) for s in engineer_assigned_stations()}

            if assigned:

                df = df[df["station_id"].astype(str).isin(assigned)]

    except Exception:

        pass

    return _subset_ref_columns(df)


def sim_engine() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    try:

        import streamlit as st

        ck = dataset_cache_key()

        if st.session_state.get("_sim_engine_key") == ck and isinstance(
            st.session_state.get("_sim_engine_ref"), pd.DataFrame
        ):

            ref = st.session_state["_sim_engine_ref"]

            profiles = st.session_state.get("_sim_engine_profiles", pd.DataFrame())

            catalog = st.session_state.get("_sim_engine_catalog", pd.DataFrame())

            if not ref.empty:

                return (ref, profiles, catalog)

    except Exception:

        pass

    ref = _load_sim_reference()

    profiles = _profile_lookup(ref)

    catalog = _station_catalog(ref)

    try:

        import streamlit as st

        st.session_state["_sim_engine_key"] = dataset_cache_key()

        st.session_state["_sim_engine_ref"] = ref

        st.session_state["_sim_engine_profiles"] = profiles

        st.session_state["_sim_engine_catalog"] = catalog

    except Exception:

        pass

    return (ref, profiles, catalog)


def _profile_keys(ref: pd.DataFrame) -> list[str]:

    keys = list(PROFILE_KEYS_BASE)

    if ref.empty:

        return keys

    if "est_ramadan" in ref.columns:

        keys.append("est_ramadan")

    if "est_ferie" in ref.columns:

        keys.append("est_ferie")

    return keys


def _station_catalog(ref: pd.DataFrame) -> pd.DataFrame:

    if ref.empty:

        return pd.DataFrame(columns=META_COLS)

    work = ref.sort_values("timestamp") if "timestamp" in ref.columns else ref

    keep = [c for c in META_COLS if c in work.columns]

    return work.groupby("station_id", as_index=False).last()[keep]


def _profile_lookup(ref: pd.DataFrame) -> pd.DataFrame:

    if ref.empty:

        return pd.DataFrame()

    keys = _profile_keys(ref)

    work = ref.copy()

    for col in keys:

        if col != "station_id" and col in work.columns:

            work[col] = pd.to_numeric(work[col], errors="coerce")

    numeric_vals = [c for c in VALUE_COLS if c in work.columns]

    return work.groupby(keys, as_index=False)[numeric_vals].mean(numeric_only=True)


def _fallback_profile(ref: pd.DataFrame, station_id: str, heure: int) -> dict:

    if ref.empty or "station_id" not in ref.columns:

        return {
            "consommation_kwh": 8.0,
            "score_qos": 0.85,
            "charge_cpu_pct": 40.0,
            "temperature_ambiante": 22.0,
        }

    work = ref[ref["station_id"].astype(str) == str(station_id)]

    if work.empty:

        work = ref

    if "heure" in work.columns:

        by_h = work[pd.to_numeric(work["heure"], errors="coerce") == heure]

        if not by_h.empty:

            work = by_h

    row = work.mean(numeric_only=True)

    out = {
        c: float(row[c]) if c in row.index and pd.notna(row[c]) else np.nan
        for c in VALUE_COLS
        if c in work.columns
    }

    out.setdefault("consommation_kwh", 8.0)

    out.setdefault("score_qos", 0.85)

    out.setdefault("charge_cpu_pct", 40.0)

    out.setdefault("temperature_ambiante", 22.0)

    return out


def _pick_profile(
    profiles: pd.DataFrame,
    ref: pd.DataFrame,
    station_id: str,
    heure: int,
    mois: int,
    est_weekend: int,
    est_ramadan: int,
    est_ferie: int,
) -> dict:

    sid = str(station_id)

    if not profiles.empty and "station_id" in profiles.columns:

        mask = (
            (profiles["station_id"].astype(str) == sid)
            & (pd.to_numeric(profiles["heure"], errors="coerce") == heure)
            & (pd.to_numeric(profiles["mois"], errors="coerce") == mois)
            & (pd.to_numeric(profiles["est_weekend"], errors="coerce") == est_weekend)
        )

        if "est_ramadan" in profiles.columns:

            mask &= (
                pd.to_numeric(profiles["est_ramadan"], errors="coerce") == est_ramadan
            )

        if "est_ferie" in profiles.columns:

            mask &= pd.to_numeric(profiles["est_ferie"], errors="coerce") == est_ferie

        hit = profiles[mask]

        if not hit.empty:

            return hit.iloc[0].to_dict()

        mask_h = (profiles["station_id"].astype(str) == sid) & (
            pd.to_numeric(profiles["heure"], errors="coerce") == heure
        )

        hit = profiles[mask_h]

        if not hit.empty:

            return hit.iloc[0].to_dict()

    return _fallback_profile(ref, sid, heure)


def _calendar_scale(ctx: dict, hour: int) -> float:

    scale = 1.0

    if ctx.get("est_ramadan"):

        scale *= 0.92

    if ctx.get("est_ferie"):

        scale *= 0.88

    if ctx.get("est_weekend"):

        scale *= 0.95

    if hour <= 5 or hour >= 23:

        scale *= 0.85

    elif 12 <= hour <= 14:

        scale *= 1.05

    return scale


def _jitter(value: float, pct: float = 0.04, seed: int = 0) -> float:

    rng = np.random.default_rng(seed)

    if not np.isfinite(value):

        return value

    return float(value * (1.0 + rng.uniform(-pct, pct)))


def hourly_snapshot(
    target_date: date,
    hour: int,
    station_ids: list[str],
    *,
    engine: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None = None,
) -> pd.DataFrame:

    if not station_ids:

        return pd.DataFrame()

    ref, profiles, catalog = engine if engine is not None else sim_engine()

    ctx = calendar_context(target_date)

    ts = datetime.combine(target_date, time(hour=hour))

    rows: list[dict] = []

    for sid in station_ids:

        base = _pick_profile(
            profiles,
            ref,
            sid,
            hour,
            ctx["mois"],
            ctx["est_weekend"],
            ctx.get("est_ramadan", 0),
            int(ctx.get("est_ferie", 0)),
        )

        if not catalog.empty and "station_id" in catalog.columns:

            meta = catalog[catalog["station_id"].astype(str) == str(sid)]

            if not meta.empty:

                for col in META_COLS:

                    if col in meta.columns:

                        base[col] = meta.iloc[0][col]

        seed = hash((str(sid), target_date.isoformat(), hour)) % 2**31

        scale = _calendar_scale(ctx, hour)

        conso = _jitter(float(base.get("consommation_kwh") or 8.0) * scale, seed=seed)

        pred_seed = float(
            base.get("conso_predite") or base.get("consommation_kwh") or 8.0
        )

        conso_pred = _jitter(pred_seed * scale, pct=0.09, seed=seed + 1)

        row: dict[str, Any] = {
            "timestamp": ts,
            "station_id": str(sid),
            "heure": hour,
            **ctx,
            "consommation_kwh": conso,
            "conso_predite": conso_pred,
            "pred_q10": conso_pred * 0.9,
            "pred_q90": conso_pred * 1.1,
            "ecart_pct": float(
                compute_ecart_pct(pd.Series([conso]), pd.Series([conso_pred])).iloc[0]
            ),
            "score_qos": float(base.get("score_qos") or 0.85),
            "taux_charge_voix": float(base.get("taux_charge_voix") or 0.5),
            "taux_charge_data": float(base.get("taux_charge_data") or 0.5),
            "trafic_data_mbps": float(base.get("trafic_data_mbps") or 100),
            "charge_cpu_pct": float(base.get("charge_cpu_pct") or 40),
            "temperature_ambiante": float(base.get("temperature_ambiante") or 22),
            "optimisation_qos_autorisee": int(
                float(base.get("score_qos") or 0.85) >= settings.QOS_SEUIL_DEFAULT
            ),
        }

        for col in VALUE_COLS:

            if col in base and pd.notna(base.get(col)) and (col not in row):

                row[col] = base[col]

        for col in ("gouvernorat", "technologie", "type_zone", "latitude", "longitude"):

            if col in base and pd.notna(base.get(col)):

                row[col] = base[col]

        rows.append(row)

    out = pd.DataFrame(rows)

    if out.empty:

        return out

    out = enrich_with_pipeline(out)

    if "mode_operation" not in out.columns or out["mode_operation"].isna().all():

        out = apply_offline_nb23(out)

    return harmonize_nb3_economies(out)


def generate_period(
    start_date: date, start_hour: int, num_days: int, station_ids: list[str]
) -> pd.DataFrame:

    engine = sim_engine()

    frames = []

    for ts in scenario_timestamps(start_date, start_hour, num_days):

        batch = hourly_snapshot(ts.date(), ts.hour, station_ids, engine=engine)

        if not batch.empty:

            frames.append(batch)

    if not frames:

        return pd.DataFrame()

    return harmonize_nb3_economies(pd.concat(frames, ignore_index=True))
