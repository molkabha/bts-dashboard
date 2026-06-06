from __future__ import annotations

from functools import lru_cache

import pandas as pd

from services.data_service import artifact_is_ready, artifact_path

from services.nb_inference import (
    clear_nb_inference_cache,
    load_pipeline_bundle,
    pipeline_load_error,
    run_nb_pipeline,
)

_PIPELINE_PRIMARY = "pipeline_inference.joblib"

_PIPELINE_FALLBACK = ("best_model.joblib", "config.joblib")


class PipelineUnavailableError(RuntimeError):
    """Raised when NB1/NB2/NB3 Hub artefacts cannot run live inference."""


@lru_cache(maxsize=1)
def _pipeline_available() -> bool:

    primary = artifact_path(_PIPELINE_PRIMARY)

    if artifact_is_ready(primary):

        return True

    return any(artifact_is_ready(artifact_path(name)) for name in _PIPELINE_FALLBACK)


def pipeline_unavailable_message() -> str:

    return (
        "Artefacts NB1/NB2/NB3 indisponibles. Verifiez USE_HF_HUB=True, HF_REPO_ID, "
        "HF_TOKEN (si repo prive) et la presence de pipeline_inference.joblib sur le Hub. "
        "La Simulation n'utilise pas le mode offline."
    )


def ensure_pipeline_ready() -> str | None:

    try:

        clear_inference_cache()

        if not _pipeline_available():

            return pipeline_unavailable_message()

        bundle = load_pipeline_bundle()

        if not bundle:

            detail = pipeline_load_error() or "cause inconnue"

            return (
                "Impossible de charger les artefacts NB1/NB2/NB3. "
                f"Detail : {detail}"
            )

        return None

    except Exception as exc:

        return f"Erreur chargement pipeline NB1/NB2/NB3 : {exc}"


def clear_inference_cache() -> None:

    _pipeline_available.cache_clear()

    clear_nb_inference_cache()


def enrich_with_pipeline(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty:

        return df

    if not _pipeline_available():

        raise PipelineUnavailableError(pipeline_unavailable_message())

    enriched = run_nb_pipeline(df)

    if enriched.empty or "mode_operation" not in enriched.columns:

        raise PipelineUnavailableError(
            "Le pipeline NB1+NB2+NB3 n'a produit aucune decision (mode_operation absent)."
        )

    pipeline = enriched.get("inference_pipeline")

    if pipeline is not None:

        modes = pipeline.astype(str).str.lower()

        if modes.str.contains("offline", na=False).any():

            raise PipelineUnavailableError(
                "Inference offline detectee alors que le pipeline Hub est requis."
            )

    return enriched
