from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from services.data_service import artifact_path


@lru_cache(maxsize=1)
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


def clear_inference_cache() -> None:
    _load_joblib.cache_clear()


def enrich_with_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    pipeline = _load_joblib("pipeline_inference.joblib")
    if pipeline is None:
        return _enrich_with_nb1(df)
    work = df.copy()
    try:
        if hasattr(pipeline, "predict"):
            out = pipeline.predict(work)
            if isinstance(out, pd.DataFrame):
                return _merge_predictions(work, out)
            if isinstance(out, dict):
                for key, series in out.items():
                    if len(series) == len(work):
                        work[key] = series
                return work
        if callable(pipeline):
            out = pipeline(work)
            if isinstance(out, pd.DataFrame):
                return _merge_predictions(work, out)
    except Exception:
        pass
    return _enrich_with_nb1(df)


def _merge_predictions(base: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    out = base.copy()
    for col in pred.columns:
        if col not in out.columns or col in {
            "conso_predite", "pred_q10", "pred_q90",
            "anomalie_score_ensemble", "mode_operation",
            "action_proposee", "action_rl", "economie_estimee_kwh", "economie_rl_kwh",
        }:
            out[col] = pred[col].values
    return out


def _enrich_with_nb1(df: pd.DataFrame) -> pd.DataFrame:
    model = _load_joblib("best_model.joblib")
    if model is None or not hasattr(model, "predict"):
        return df
    work = df.copy()
    feature_cols = [c for c in work.columns if c not in {"timestamp", "station_id", "source_decision_nb3"}]
    try:
        matrix = work[feature_cols]
        preds = model.predict(matrix)
        work["conso_predite"] = preds
        if "pred_q10" not in work.columns:
            work["pred_q10"] = preds * 0.9
        if "pred_q90" not in work.columns:
            work["pred_q90"] = preds * 1.1
        if "consommation_kwh" in work.columns:
            conso = pd.to_numeric(work["consommation_kwh"], errors="coerce")
            pred = pd.to_numeric(work["conso_predite"], errors="coerce")
            work["ecart_pct"] = ((conso - pred) / pred.replace(0, pd.NA) * 100).fillna(0)
    except Exception:
        return df
    return work
