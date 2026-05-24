from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from services.data_service import artifact_path
from services.nb_inference import clear_nb_inference_cache, run_nb_pipeline


@lru_cache(maxsize=1)
def _pipeline_available() -> bool:
    for name in ("pipeline_inference.joblib", "best_model.joblib", "config.joblib"):
        if artifact_path(name).exists():
            return True
    return False


def clear_inference_cache() -> None:
    _pipeline_available.cache_clear()
    clear_nb_inference_cache()


def enrich_with_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """Enrichit les lignes simulation via NB1 (LGBM) → NB2 → NB3."""
    if df.empty or not _pipeline_available():
        return df
    try:
        return run_nb_pipeline(df)
    except Exception:
        return df
