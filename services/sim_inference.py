from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from services.data_service import artifact_is_ready, artifact_path
from services.ml_artifacts import sim_ml_status, warm_sim_ml_artifacts
from services.nb_inference import clear_nb_inference_cache, run_nb_pipeline


@lru_cache(maxsize=1)
def _pipeline_available() -> bool:
    warm_sim_ml_artifacts()
    status = sim_ml_status()
    if status["ready"]:
        return True
    for name in ("pipeline_inference.joblib", "best_model.joblib", "config.joblib"):
        if artifact_is_ready(artifact_path(name)):
            return True
    return False


def clear_inference_cache() -> None:
    _pipeline_available.cache_clear()
    clear_nb_inference_cache()
    from services.ml_artifacts import clear_sim_ml_status_cache

    clear_sim_ml_status_cache()


def enrich_with_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """Enrichit les lignes simulation via NB1 (LGBM) → NB2 → NB3."""
    if df.empty or not _pipeline_available():
        return df
    try:
        enriched = run_nb_pipeline(df)
        if (
            not enriched.empty
            and "conso_predite" in enriched.columns
            and enriched["conso_predite"].notna().any()
        ):
            return enriched
    except Exception:
        pass
    return df


def ml_status_for_ui() -> dict[str, Any]:
    """Expose le diagnostic ML pour la page simulation."""
    warm_sim_ml_artifacts()
    return sim_ml_status()
