from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from config.settings import settings
from services.nb_inference import apply_offline_nb23, clear_nb_inference_cache, run_nb_pipeline

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    hf_hub_download = None

_ML_ARTIFACTS = ("pipeline_inference.joblib", "best_model.joblib", "config.joblib")


def _artifact_cached_locally(name: str) -> Path | None:
    """Detecte un artefact deja en cache / disque sans declencher de telechargement HF."""
    candidates = [settings.OUTPUTS_DIR / name]
    from services.data_service import NOTEBOOK_OUTPUTS, artifact_is_ready

    for base in NOTEBOOK_OUTPUTS.values():
        candidates.append(base / name)
    for path in candidates:
        if artifact_is_ready(path):
            return path

    if hf_hub_download is None:
        return None
    for hf_name in (name, f"streamlit_{name}" if not name.startswith("streamlit_") else name):
        try:
            downloaded = hf_hub_download(
                repo_id=settings.HF_REPO_ID,
                filename=hf_name,
                cache_dir=str(settings.HF_CACHE_DIR),
                local_files_only=True,
            )
            path = Path(downloaded)
            if artifact_is_ready(path):
                return path
        except Exception:
            continue
    return None


@lru_cache(maxsize=1)
def _pipeline_available() -> bool:
    return any(_artifact_cached_locally(name) is not None for name in _ML_ARTIFACTS)


def clear_inference_cache() -> None:
    _pipeline_available.cache_clear()
    clear_nb_inference_cache()


def enrich_with_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """Enrichit les lignes simulation via NB1 (LGBM) → NB2 → NB3 (cache local uniquement)."""
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
