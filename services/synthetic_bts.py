from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from config.settings import settings
from services.calendar_tn import calendar_context, scenario_timestamps
from services.data_service import load_filtered_main_data, resolve_nb2_seuil_ensemble
from services.nb_metrics import harmonize_nb3_economies
from services.sim_inference import clear_inference_cache, enrich_with_pipeline

PROFILE_KEYS_BASE = ["station_id", "heure", "mois", "est_weekend"]
META_COLS = [
    "station_id", "gouvernorat", "technologie", "type_zone",
    "latitude", "longitude",
]
VALUE_COLS = [
    "consommation_kwh", "conso_predite", "pred_q10", "pred_q90",
    "charge_cpu_pct", "temperature_ambiante", "score_qos",
    "anomalie_score_ensemble", "nb_votes_anomalie",
    "mode_operation", "action_proposee", "action_rl",
    "economie_estimee_kwh", "economie_rl_kwh", "meilleur_agent_rl",
    "ecart_pct", "trafic_data_mbps", "pue", "taux_charge_data", "taux_charge_voix",
]


def clear_synthetic_cache() -> None:
    _reference_frame.cache_clear()
    clear_inference_cache()


@lru_cache(maxsize=2)
def _reference_frame() -> pd.DataFrame:
    cols = list(dict.fromkeys(
        ["timestamp", "station_id", "heure", "mois", "est_weekend", "est_ramadan",
         "est_ferie", "est_vendredi", "jour_semaine"] + META_COLS + VALUE_COLS
    ))
    df = load_filtered_main_data(cols)
    if df.empty:
        return df
    if "timestamp" in df.columns:
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


def _profile_keys(ref: pd.DataFrame) -> list[str]:
    keys = list(PROFILE_KEYS_BASE)
    if not ref.empty and "est_ramadan" in ref.columns:
        keys.append("est_ramadan")
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


def _fallback_profile(ref: pd.DataFrame, station_id: str, heure: int, mois: int, est_weekend: int) -> dict:
    if ref.empty or "station_id" not in ref.columns:
        return {
            "consommation_kwh": 8.0,
            "conso_predite": 8.0,
            "score_qos": 0.85,
            "anomalie_score_ensemble": 0.05,
            "nb_votes_anomalie": 0,
        }
    work = ref[ref["station_id"].astype(str) == str(station_id)]
    if work.empty:
        work = ref
    if "heure" in work.columns:
        work = work[pd.to_numeric(work["heure"], errors="coerce") == heure]
    if work.empty:
        work = ref
    row = work.mean(numeric_only=True)
    out = {c: row.get(c, np.nan) for c in VALUE_COLS if c in work.columns}
    out.setdefault("consommation_kwh", 8.0)
    out.setdefault("conso_predite", out["consommation_kwh"])
    out.setdefault("score_qos", 0.85)
    out.setdefault("anomalie_score_ensemble", 0.05)
    out.setdefault("nb_votes_anomalie", 0)
    return out


def _pick_profile(
    profiles: pd.DataFrame,
    ref: pd.DataFrame,
    station_id: str,
    heure: int,
    mois: int,
    est_weekend: int,
    est_ramadan: int,
) -> dict:
    if ref.empty:
        return _fallback_profile(ref, station_id, heure, mois, est_weekend)
    if not profiles.empty and "station_id" in profiles.columns:
        mask = (
            (profiles["station_id"].astype(str) == str(station_id))
            & (pd.to_numeric(profiles["heure"], errors="coerce") == heure)
            & (pd.to_numeric(profiles["mois"], errors="coerce") == mois)
            & (pd.to_numeric(profiles["est_weekend"], errors="coerce") == est_weekend)
        )
        if "est_ramadan" in profiles.columns:
            mask &= pd.to_numeric(profiles["est_ramadan"], errors="coerce") == est_ramadan
        hit = profiles[mask]
        if not hit.empty:
            return hit.iloc[0].to_dict()
        mask = (
            (profiles["station_id"].astype(str) == str(station_id))
            & (pd.to_numeric(profiles["heure"], errors="coerce") == heure)
        )
        hit = profiles[mask]
        if not hit.empty:
            return hit.iloc[0].to_dict()
    return _fallback_profile(ref, station_id, heure, mois, est_weekend)


def _calendar_scale(ctx: dict, heure: int) -> float:
    scale = 1.0
    if ctx.get("est_ramadan"):
        scale *= 0.94 if 0 <= heure <= 6 or heure >= 22 else 0.97
    if ctx.get("est_ferie"):
        scale *= 0.88
    if ctx.get("est_vendredi") and 11 <= heure <= 14:
        scale *= 1.03
    if ctx.get("est_weekend"):
        scale *= 0.92 if 9 <= heure <= 18 else 0.96
    return scale


def _apply_decision_rules(
    row: dict,
    seuil: float,
    qos_seuil: float,
    anomaly_sensitivity: float = 1.0,
) -> dict:
    sens = anomaly_sensitivity if anomaly_sensitivity > 0 else 1.0
    effective_seuil = seuil / sens
    score = float(row.get("anomalie_score_ensemble") or 0)
    qos = float(row.get("score_qos") or 0)
    heure = int(row.get("heure") or 0)
    conso = float(row.get("consommation_kwh") or 0)

    action = "maintien"
    mode = "NORMAL"
    eco_est = 0.0
    eco_rl = 0.0

    if score >= effective_seuil * 2.4 and qos < qos_seuil:
        mode = "CRITIQUE"
        action = "alerte_qos"
    elif score >= effective_seuil and qos >= qos_seuil:
        mode = "ATTENTION"
        action = "aucune_action"
    elif score >= effective_seuil and qos < qos_seuil:
        mode = "CRITIQUE"
        action = "intervention"
    elif heure <= 5 or heure >= 23:
        mode = "ECO"
        action = "reduction_puissance"
        eco_est = min(conso * 0.12, conso)
        eco_rl = eco_est
    elif heure >= 10 and heure <= 16 and score < effective_seuil * 0.6:
        mode = "ECO"
        action = "mode_eco"
        eco_est = min(conso * 0.08, conso)
        eco_rl = eco_est * 0.95
    elif score >= effective_seuil * 1.4:
        mode = "ATTENTION"
        action = "reduction_puissance"
        eco_est = min(conso * 0.06, conso)
        eco_rl = eco_est

    row["mode_operation"] = mode
    row["action_proposee"] = action
    row["action_rl"] = action
    row["action_principale"] = action
    row["economie_estimee_kwh"] = eco_est
    row["economie_rl_kwh"] = eco_rl
    row["meilleur_agent_rl"] = row.get("meilleur_agent_rl") or "PPO"
    return row


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
    anomaly_sensitivity: float = 1.0,
    use_ml: bool = True,
) -> pd.DataFrame:
    ref = _reference_frame()
    if not station_ids:
        return pd.DataFrame()
    catalog = _station_catalog(ref)
    profiles = _profile_lookup(ref)
    ctx = calendar_context(target_date)
    ts = datetime.combine(target_date, time(hour=hour))
    seuil, _ = resolve_nb2_seuil_ensemble()
    qos_seuil = float(settings.QOS_SEUIL_DEFAULT)
    rows: list[dict] = []

    for idx, sid in enumerate(station_ids):
        base = _pick_profile(
            profiles, ref, sid, hour, ctx["mois"], ctx["est_weekend"], ctx.get("est_ramadan", 0),
        )
        meta = pd.DataFrame()
        if not catalog.empty and "station_id" in catalog.columns:
            meta = catalog[catalog["station_id"].astype(str) == str(sid)]
        if not meta.empty:
            for col in META_COLS:
                if col in meta.columns:
                    base[col] = meta.iloc[0][col]

        seed = hash((str(sid), target_date.isoformat(), hour)) % (2**31)
        scale = _calendar_scale(ctx, hour)
        conso = _jitter(float(base.get("consommation_kwh") or 8.0) * scale, seed=seed)

        score_qos = float(base.get("score_qos") or 0.85)

        row = {
            "timestamp": ts,
            "station_id": str(sid),
            "heure": hour,
            **ctx,
            "consommation_kwh": conso,
            "score_qos": score_qos,
            "taux_charge_voix": float(base.get("taux_charge_voix") or 0.5),
            "taux_charge_data": float(base.get("taux_charge_data") or 0.5),
            "trafic_data_mbps": float(base.get("trafic_data_mbps") or 100),
            "charge_cpu_pct": float(base.get("charge_cpu_pct") or 40),
            "temperature_ambiante": float(base.get("temperature_ambiante") or 22),
            "source_decision_nb3": "scenario",
            "inference_pipeline": "nb1_nb2_nb3",
        }
        for col in ("gouvernorat", "technologie", "type_zone", "latitude", "longitude"):
            if col in base and pd.notna(base.get(col)):
                row[col] = base[col]
        rows.append(row)

    out = pd.DataFrame(rows)
    if use_ml and not out.empty:
        enriched = enrich_with_pipeline(out)
        if not enriched.empty and "conso_predite" in enriched.columns:
            out = enriched
            if "source_decision_nb3" not in out.columns:
                out["source_decision_nb3"] = "nb1_nb2_nb3"
        else:
            out = _apply_decision_rules_batch(out, seuil, qos_seuil, anomaly_sensitivity)
            out["source_decision_nb3"] = "scenario_rules"
    else:
        out = _fill_fallback_predictions(out)
        out = _apply_decision_rules_batch(out, seuil, qos_seuil, anomaly_sensitivity)
    return harmonize_nb3_economies(out)


def _fill_fallback_predictions(df: pd.DataFrame) -> pd.DataFrame:
    """Si les artefacts ML sont absents, aligner prédit sur le réel simulé."""
    if df.empty:
        return df
    out = df.copy()
    conso = pd.to_numeric(out["consommation_kwh"], errors="coerce")
    if "conso_predite" not in out.columns:
        out["conso_predite"] = conso
    out["pred_q10"] = out.get("pred_q10", conso * 0.9)
    out["pred_q90"] = out.get("pred_q90", conso * 1.1)
    pred = pd.to_numeric(out["conso_predite"], errors="coerce")
    out["ecart_pct"] = ((conso - pred) / pred.replace(0, pd.NA) * 100).fillna(0)
    if "anomalie_score_ensemble" not in out.columns:
        out["anomalie_score_ensemble"] = 0.05
    if "nb_votes_anomalie" not in out.columns:
        out["nb_votes_anomalie"] = 0
    return out


def _apply_decision_rules_batch(
    df: pd.DataFrame,
    seuil: float,
    qos_seuil: float,
    anomaly_sensitivity: float,
) -> pd.DataFrame:
    rows = [
        _apply_decision_rules(r.to_dict(), seuil, qos_seuil, anomaly_sensitivity)
        for _, r in df.iterrows()
    ]
    return pd.DataFrame(rows)


def generate_period(
    start_date: date,
    start_hour: int,
    num_days: int,
    station_ids: list[str],
    *,
    anomaly_sensitivity: float = 1.0,
    use_ml: bool = True,
) -> pd.DataFrame:
    frames = []
    for ts in scenario_timestamps(start_date, start_hour, num_days):
        batch = hourly_snapshot(
            ts.date(), ts.hour, station_ids,
            anomaly_sensitivity=anomaly_sensitivity,
            use_ml=use_ml,
        )
        if not batch.empty:
            frames.append(batch)
    if not frames:
        return pd.DataFrame()
    return harmonize_nb3_economies(pd.concat(frames, ignore_index=True))


def replay_historical_hour(
    source: pd.DataFrame,
    target_date: date,
    hour: int,
    station_ids: list[str],
) -> pd.DataFrame:
    if source.empty or "timestamp" not in source.columns:
        return pd.DataFrame()
    ts = datetime.combine(target_date, time(hour=hour))
    mask = (
        (pd.to_datetime(source["timestamp"], errors="coerce") == pd.Timestamp(ts))
        & (source["station_id"].astype(str).isin([str(s) for s in station_ids]))
    )
    return source[mask].copy()
