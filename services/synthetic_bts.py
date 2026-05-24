from __future__ import annotations

from datetime import date, datetime, time
from functools import lru_cache

import numpy as np
import pandas as pd

from config.settings import settings
from services.calendar_tn import calendar_context
from services.data_service import load_filtered_main_data, resolve_nb2_seuil_ensemble
from services.nb_metrics import harmonize_nb3_economies

PROFILE_KEYS = ["station_id", "heure", "mois", "est_weekend"]
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


def _station_catalog(ref: pd.DataFrame) -> pd.DataFrame:
    if ref.empty:
        return pd.DataFrame(columns=META_COLS)
    work = ref.sort_values("timestamp") if "timestamp" in ref.columns else ref
    keep = [c for c in META_COLS if c in work.columns]
    return work.groupby("station_id", as_index=False).last()[keep]


def _profile_lookup(ref: pd.DataFrame) -> pd.DataFrame:
    if ref.empty:
        return pd.DataFrame()
    work = ref.copy()
    for col in ("heure", "mois", "est_weekend"):
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")
    numeric_vals = [c for c in VALUE_COLS if c in work.columns]
    grouped = (
        work.groupby(PROFILE_KEYS, as_index=False)[numeric_vals]
        .mean(numeric_only=True)
    )
    return grouped


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


def _apply_decision_rules(row: dict, seuil: float, qos_seuil: float) -> dict:
    score = float(row.get("anomalie_score_ensemble") or 0)
    qos = float(row.get("score_qos") or 0)
    heure = int(row.get("heure") or 0)
    conso = float(row.get("consommation_kwh") or 0)

    action = "maintien"
    mode = "NORMAL"
    eco_est = 0.0
    eco_rl = 0.0

    if score >= seuil * 2.4 and qos < qos_seuil:
        mode = "CRITIQUE"
        action = "alerte_qos"
    elif score >= seuil and qos >= qos_seuil:
        mode = "ATTENTION"
        action = "aucune_action"
    elif score >= seuil and qos < qos_seuil:
        mode = "CRITIQUE"
        action = "intervention"
    elif heure <= 5 or heure >= 23:
        mode = "ECO"
        action = "reduction_puissance"
        eco_est = min(conso * 0.12, conso)
        eco_rl = eco_est
    elif heure >= 10 and heure <= 16 and score < seuil * 0.6:
        mode = "ECO"
        action = "mode_eco"
        eco_est = min(conso * 0.08, conso)
        eco_rl = eco_est * 0.95
    elif score >= seuil * 1.4:
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
        base = _pick_profile(profiles, ref, sid, hour, ctx["mois"], ctx["est_weekend"])
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
        pred = _jitter(float(base.get("conso_predite") or conso) * scale, seed=seed + 1)
        if pred <= 0:
            pred = conso
        ecart = (conso - pred) / pred * 100.0 if pred else 0.0

        score_qos = float(base.get("score_qos") or 0.85)
        score_anom = float(base.get("anomalie_score_ensemble") or 0.05)
        score_anom = min(1.0, max(0.0, score_anom + abs(ecart) * 0.002))

        row = {
            "timestamp": ts,
            "station_id": str(sid),
            "heure": hour,
            **ctx,
            "consommation_kwh": conso,
            "conso_predite": pred,
            "pred_q10": pred * 0.9,
            "pred_q90": pred * 1.1,
            "ecart_pct": ecart,
            "score_qos": score_qos,
            "anomalie_score_ensemble": score_anom,
            "nb_votes_anomalie": int(base.get("nb_votes_anomalie") or 0),
            "charge_cpu_pct": float(base.get("charge_cpu_pct") or 40),
            "temperature_ambiante": float(base.get("temperature_ambiante") or 22),
            "source_decision_nb3": "scenario",
        }
        for col in ("gouvernorat", "technologie", "type_zone", "latitude", "longitude"):
            if col in base and pd.notna(base.get(col)):
                row[col] = base[col]
        row = _apply_decision_rules(row, seuil, qos_seuil)
        rows.append(row)

    out = pd.DataFrame(rows)
    return harmonize_nb3_economies(out)


def scenario_timestamps(target_date: date, start_hour: int = 0) -> list[datetime]:
    return [
        datetime.combine(target_date, time(hour=h))
        for h in range(int(start_hour), 24)
    ]
