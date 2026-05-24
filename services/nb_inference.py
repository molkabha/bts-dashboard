"""NB1 (LGBM) → NB2 (anomalies) → NB3 (décisions) — même artefacts que le dashboard."""

from __future__ import annotations

import math
import sys
from datetime import date
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from services.calendar_tn import calendar_context
from services.data_service import artifact_path, read_parquet_fast, resolve_nb2_seuil_ensemble
from services.nb3_runtime import apply_nb3_decisions

NB3_STUB_CLASSES = ("MoteurDecisionEnergie", "StrategieOptimisation")


def _register_nb3_stubs() -> None:
    import services.nb3_runtime as rt

    for name in NB3_STUB_CLASSES:
        setattr(sys.modules["__main__"], name, getattr(rt, name))


@lru_cache(maxsize=16)
def _load_joblib(name: str) -> Any | None:
    try:
        import joblib
    except ImportError:
        return None
    path = artifact_path(name)
    if not path.exists():
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


@lru_cache(maxsize=1)
def load_pipeline_bundle() -> dict[str, Any] | None:
    """pipeline_inference.joblib (dict: LGBM, anomalies, encodeurs, config, RL meta)."""
    _register_nb3_stubs()
    try:
        import joblib
    except ImportError:
        return None
    path = artifact_path("pipeline_inference.joblib")
    if not path.exists():
        return None
    try:
        obj = joblib.load(path)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


@lru_cache(maxsize=1)
def _feature_templates() -> pd.DataFrame:
    """Profil moyen NB1 (65 features) par station × heure."""
    cols = ["station_id", "heure"]
    path = artifact_path("streamlit_data.parquet")
    if not path.exists():
        path = artifact_path("df_full_processed.parquet")
    if not path.exists():
        return pd.DataFrame()

    config = _load_joblib("config.joblib")
    feat_cols = list(config.get("features", [])) if isinstance(config, dict) else []
    if not feat_cols:
        return pd.DataFrame()

    read_cols = list(dict.fromkeys(cols + feat_cols + ["technologie", "type_zone", "gouvernorat"]))
    df = read_parquet_fast(path, read_cols)
    if df.empty or "station_id" not in df.columns:
        return pd.DataFrame()

    work = df.copy()
    work["station_id"] = work["station_id"].astype(str)
    work["heure"] = pd.to_numeric(work.get("heure"), errors="coerce")
    work = work.dropna(subset=["heure"])
    numeric = [c for c in feat_cols if c in work.columns]
    return work.groupby(["station_id", "heure"], as_index=False)[numeric].mean(numeric_only=True)


def clear_nb_inference_cache() -> None:
    load_pipeline_bundle.cache_clear()
    _feature_templates.cache_clear()
    _load_joblib.cache_clear()  # type: ignore[attr-defined]


def _cyclical_features(target_date: date, hour: int) -> dict[str, float]:
    ctx = calendar_context(target_date)
    mois = int(ctx.get("mois") or target_date.month)
    jour = int(ctx.get("jour_semaine") or target_date.weekday())
    return {
        "heure_sin": math.sin(2 * math.pi * hour / 24),
        "heure_cos": math.cos(2 * math.pi * hour / 24),
        "jour_sin": math.sin(2 * math.pi * jour / 7),
        "jour_cos": math.cos(2 * math.pi * jour / 7),
        "mois_sin": math.sin(2 * math.pi * mois / 12),
        "mois_cos": math.cos(2 * math.pi * mois / 12),
        "mois_annee": float(mois),
        "est_weekend": float(ctx.get("est_weekend", 0)),
        "est_vendredi": float(ctx.get("est_vendredi", 0)),
        "est_ramadan": float(ctx.get("est_ramadan", 0)),
        "est_ferie": float(ctx.get("est_ferie", 0)),
    }


def _encode_row(
    row: pd.Series,
    encodeurs: dict,
    feature_names: list[str],
) -> np.ndarray:
    values: list[float] = []
    for feat in feature_names:
        if feat == "technologie_enc":
            le = encodeurs.get("technologie")
            raw = row.get("technologie")
            values.append(float(le.transform([str(raw)])[0]) if le is not None and raw is not None else 0.0)
        elif feat == "type_zone_enc":
            le = encodeurs.get("type_zone")
            raw = row.get("type_zone")
            values.append(float(le.transform([str(raw)])[0]) if le is not None and raw is not None else 0.0)
        elif feat == "gouvernorat_enc":
            le = encodeurs.get("gouvernorat")
            raw = row.get("gouvernorat")
            values.append(float(le.transform([str(raw)])[0]) if le is not None and raw is not None else 0.0)
        elif feat == "station_enc":
            smap = encodeurs.get("station_enc_map")
            sid = str(row.get("station_id", ""))
            if smap is not None and sid in smap.index:
                values.append(float(smap[sid]))
            elif smap is not None and sid in smap:
                values.append(float(smap[sid]))
            else:
                values.append(float(smap.mean()) if smap is not None and len(smap) else 0.0)
        else:
            val = row.get(feat)
            values.append(float(val) if val is not None and pd.notna(val) else 0.0)
    return np.array(values, dtype=float).reshape(1, -1)


def build_nb1_feature_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Construit la matrice NB1 (65 features) à partir des templates historiques + calendrier."""
    if df.empty:
        return pd.DataFrame()

    templates = _feature_templates()
    if templates.empty:
        return pd.DataFrame()

    config = _load_joblib("config.joblib")
    if not isinstance(config, dict):
        bundle = load_pipeline_bundle()
        config = bundle.get("config") if bundle else {}
    feature_names = list(config.get("features") or [])
    if not feature_names:
        return pd.DataFrame()

    rows: list[dict] = []
    for _, src in df.iterrows():
        sid = str(src.get("station_id", ""))
        hour = int(src.get("heure") or 0)
        ts = pd.to_datetime(src.get("timestamp"), errors="coerce")
        target_date = ts.date() if pd.notna(ts) else date.today()

        tpl = templates[
            (templates["station_id"].astype(str) == sid)
            & (pd.to_numeric(templates["heure"], errors="coerce") == hour)
        ]
        if tpl.empty:
            tpl = templates[templates["station_id"].astype(str) == sid]
        if tpl.empty:
            tpl = templates[pd.to_numeric(templates["heure"], errors="coerce") == hour]
        base = tpl.iloc[0].to_dict() if not tpl.empty else {}

        feat = {**base, **_cyclical_features(target_date, hour)}
        for col in ("technologie", "type_zone", "gouvernorat", "station_id"):
            if col in src and pd.notna(src.get(col)):
                feat[col] = src[col]
        for col in (
            "charge_cpu_pct", "temperature_ambiante", "trafic_data_mbps",
            "taux_charge_voix", "taux_charge_data", "score_qos",
        ):
            if col in src and pd.notna(src.get(col)):
                feat[col] = src[col]

        trafic = float(feat.get("trafic_data_mbps") or 0)
        temp = float(feat.get("temperature_ambiante") or 20)
        cpu = float(feat.get("charge_cpu_pct") or 40)
        secteurs = float(feat.get("nb_secteurs_actifs") or 1)
        feat["trafic_x_temp"] = trafic * temp
        feat["charge_cpu_x_secteurs"] = cpu * secteurs
        if "charge_par_secteur" not in feat or not feat.get("charge_par_secteur"):
            conso_lag = float(feat.get("conso_lag_1h") or feat.get("conso_moy_station") or 8.0)
            feat["charge_par_secteur"] = conso_lag / max(secteurs, 1)

        rows.append(feat)

    return pd.DataFrame(rows)


def _predict_nb1(
    feature_df: pd.DataFrame,
    bundle: dict[str, Any] | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if feature_df.empty:
        return np.array([]), np.array([]), np.array([])

    config = (bundle or {}).get("config") or _load_joblib("config.joblib") or {}
    encodeurs = (bundle or {}).get("encodeurs") or _load_joblib("encodeurs.joblib") or {}
    feature_names = list(config.get("features") or [])
    model = (bundle or {}).get("modele_lgbm") or _load_joblib("best_model.joblib")
    quantiles = (bundle or {}).get("quantiles") or _load_joblib("quantile_models.joblib") or {}

    matrix = np.vstack([
        _encode_row(feature_df.iloc[i], encodeurs, feature_names)[0]
        for i in range(len(feature_df))
    ])
    preds = model.predict(matrix)
    q10 = quantiles["q10"].predict(matrix) if isinstance(quantiles, dict) and "q10" in quantiles else preds * 0.9
    q90 = quantiles["q90"].predict(matrix) if isinstance(quantiles, dict) and "q90" in quantiles else preds * 1.1
    return preds, q10, q90


def _nb2_features(df: pd.DataFrame, template: pd.DataFrame | None = None) -> pd.DataFrame:
    anom = _load_joblib("modeles_anomalie.joblib")
    if not isinstance(anom, dict):
        bundle = load_pipeline_bundle()
        anom = bundle.get("modele_anom") if bundle else None
    feat_cols = list(anom.get("features", [])) if isinstance(anom, dict) else []
    if not feat_cols:
        return pd.DataFrame()

    out = df.copy()
    if template is not None and not template.empty:
        for col in feat_cols:
            if col not in out.columns and col in template.columns:
                out[col] = template[col].values
    conso = pd.to_numeric(out["consommation_kwh"], errors="coerce")
    pred = pd.to_numeric(out["conso_predite"], errors="coerce")
    out["ecart_pct"] = ((conso - pred) / pred.replace(0, pd.NA) * 100).fillna(0)
    if "eei" not in out.columns:
        out["eei"] = 100.0 + out["ecart_pct"] * 0.65
    if "ecart_vs_profil_horaire" not in out.columns:
        out["ecart_vs_profil_horaire"] = (conso - pred).fillna(0)
    for col in feat_cols:
        if col not in out.columns:
            out[col] = 0.0
    return out[feat_cols]


def _predict_nb2(
    df: pd.DataFrame,
    bundle: dict[str, Any] | None,
    template: pd.DataFrame | None = None,
) -> tuple[pd.Series, pd.Series]:
    anom = (bundle or {}).get("modele_anom") if bundle else None
    if anom is None:
        anom = _load_joblib("modeles_anomalie.joblib")
    if not isinstance(anom, dict):
        n = len(df)
        return pd.Series(0.05, index=df.index), pd.Series(0, index=df.index)

    feat_df = _nb2_features(df, template)
    if feat_df.empty:
        n = len(df)
        return pd.Series(0.05, index=df.index), pd.Series(0, index=df.index)

    poids = anom.get("poids") or {}
    X = feat_df.astype(float).values
    X_std = anom["scaler_std"].transform(X)
    X_rob = anom["scaler_rob"].transform(X)

    scores: dict[str, np.ndarray] = {}
    votes = np.zeros(len(df), dtype=int)

    iso = anom.get("iso_f")
    if iso is not None:
        pred = iso.predict(X_std)
        votes += (pred == -1).astype(int)
        raw = -iso.score_samples(X_std)
        scores["Isolation Forest"] = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)

    lof = anom.get("lof")
    if lof is not None:
        pred = lof.predict(X_std)
        votes += (pred == -1).astype(int)
        raw = -lof.score_samples(X_std)
        scores["LOF"] = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)

    oc = anom.get("oc_svm")
    if oc is not None:
        pred = oc.predict(X_rob)
        votes += (pred == -1).astype(int)
        raw = -oc.decision_function(X_rob)
        scores["One-Class SVM"] = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)

    ee = anom.get("ee")
    if ee is not None:
        pred = ee.predict(X_rob)
        votes += (pred == -1).astype(int)
        raw = -ee.score_samples(X_rob)
        scores["Elliptic Envelope"] = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)

    gmm = anom.get("gmm")
    if gmm is not None:
        logp = gmm.score_samples(X_rob)
        thresh = float(anom.get("seuil_gmm", np.percentile(logp, 5)))
        votes += (logp < thresh).astype(int)
        scores["GMM"] = (-logp - (-logp).min()) / ((-logp).max() - (-logp).min() + 1e-9)

    ensemble = np.zeros(len(df))
    total_w = 0.0
    for name, sc in scores.items():
        w = float(poids.get(name, 1.0 / max(len(scores), 1)))
        ensemble += sc * w
        total_w += w
    if total_w > 0:
        ensemble /= total_w
    ensemble = np.clip(ensemble, 0, 1)

    return pd.Series(ensemble, index=df.index), pd.Series(votes, index=df.index)


def _merge_nb3_decisions(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "heure" not in df.columns or "station_id" not in df.columns:
        return df
    path = artifact_path("decisions_par_station.parquet")
    if not path.exists():
        return df
    dec_cols = [
        "station_id", "heure", "mode_operation", "action_proposee",
        "action_rl", "economie_estimee_kwh", "economie_rl_kwh",
    ]
    decisions = read_parquet_fast(path, dec_cols)
    if decisions.empty:
        return df
    merged = df.merge(
        decisions,
        on=["station_id", "heure"],
        how="left",
        suffixes=("", "_nb3"),
    )
    for col in ("mode_operation", "action_proposee", "action_rl", "economie_estimee_kwh", "economie_rl_kwh"):
        nb3_col = f"{col}_nb3"
        if nb3_col in merged.columns:
            mask = merged[nb3_col].notna()
            merged.loc[mask, col] = merged.loc[mask, nb3_col]
            merged.drop(columns=[nb3_col], inplace=True)
    has = merged["mode_operation"].notna()
    merged.loc[has, "source_decision_nb3"] = "decisions_par_station"
    return merged


def run_nb_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """Applique NB1 LGBM + NB2 + NB3 sur les lignes de simulation."""
    if df.empty:
        return df

    bundle = load_pipeline_bundle()
    out = df.copy()
    feat_rows = build_nb1_feature_rows(out)
    if feat_rows.empty:
        return out

    preds, q10, q90 = _predict_nb1(feat_rows, bundle)
    out["conso_predite"] = preds
    out["pred_q10"] = q10
    out["pred_q90"] = q90
    conso = pd.to_numeric(out["consommation_kwh"], errors="coerce")
    pred = pd.to_numeric(out["conso_predite"], errors="coerce")
    out["ecart_pct"] = ((conso - pred) / pred.replace(0, pd.NA) * 100).fillna(0)

    scores, votes = _predict_nb2(out, bundle, feat_rows)
    out["anomalie_score_ensemble"] = scores.values
    out["nb_votes_anomalie"] = votes.values.astype(int)

    seuil, _ = resolve_nb2_seuil_ensemble()
    qos_seuil = float(
        (bundle or {}).get("qos_seuil")
        or ((bundle or {}).get("config") or {}).get("qos_seuil_optimisation")
        or 0.6
    )
    env_meta = (bundle or {}).get("env_rl_meta") if bundle else None
    out = apply_nb3_decisions(
        out,
        qos_seuil=qos_seuil,
        env_rl_meta=env_meta,
        anomaly_seuil=float(seuil or 0.15),
    )
    if bundle and bundle.get("best_agent_name"):
        out["meilleur_agent_rl"] = bundle["best_agent_name"]
    out = _merge_nb3_decisions(out)
    return out
