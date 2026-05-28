from __future__ import annotations

from functools import lru_cache

import pandas as pd

from services.data_service import resolve_cached_artifact

from services.nb_inference import (
    apply_offline_nb23,
    clear_nb_inference_cache,
    run_nb_pipeline,
)

_ML_ARTIFACTS = ("pipeline_inference.joblib", "best_model.joblib", "config.joblib")


@lru_cache(maxsize=1)
def _pipeline_available() -> bool:

    return any((resolve_cached_artifact(name) is not None for name in _ML_ARTIFACTS))


def clear_inference_cache() -> None:

    _pipeline_available.cache_clear()

    clear_nb_inference_cache()


def enrich_with_pipeline(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty:

        return df

    if not _pipeline_available():

        return apply_offline_nb23(df)

    try:

        enriched = run_nb_pipeline(df)

        if enriched.empty or "mode_operation" not in enriched.columns:

            return apply_offline_nb23(df)

        return enriched

    except Exception:

        return apply_offline_nb23(df)
