"""État et préchargement des artefacts ML pour la simulation (Hub / local)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from config.settings import settings
from services import data_service
from services.data_service import artifact_is_ready, artifact_path, hf_hub_token

# Fichiers légers + pipeline (évite streamlit_data.parquet ~100 Mo au démarrage).
SIM_WARM_FILES = (
    "pipeline_inference.joblib",
    "config.joblib",
    "encodeurs.joblib",
    "best_model.joblib",
    "modeles_anomalie.joblib",
    "streamlit_score_stations.parquet",
)


def _check_file(name: str) -> bool:
    path = artifact_path(name)
    return artifact_is_ready(path)


@lru_cache(maxsize=1)
def sim_ml_status() -> dict:
    """Diagnostic : pourquoi le LGBM est ou n'est pas actif."""
    has_pipeline = _check_file("pipeline_inference.joblib")
    has_lgbm = has_pipeline or _check_file("best_model.joblib")
    has_config = has_pipeline or _check_file("config.joblib")
    has_anom = has_pipeline or _check_file("modeles_anomalie.joblib")
    has_data = _check_file("streamlit_data.parquet") or _check_file("df_full_processed.parquet")
    has_light = _check_file("streamlit_score_stations.parquet")

    ready = has_lgbm and has_config
    if ready:
        detail = "Pipeline LightGBM pret (Hub ou local)."
    elif not settings.USE_HF_HUB:
        detail = "USE_HF_HUB=False : activez le Hub ou copiez les .joblib dans VF/*/output."
    elif data_service.hf_hub_download is None:
        detail = "huggingface_hub non installe."
    elif not has_lgbm:
        detail = "Modeles absents (pipeline_inference.joblib / best_model.joblib)."
    elif not has_config:
        detail = "config.joblib introuvable."
    else:
        detail = (
            "Templates features indisponibles ; repli synthetique utilise si le modele charge."
        )

    return {
        "ready": ready,
        "has_pipeline": has_pipeline,
        "has_lgbm": has_lgbm,
        "has_config": has_config,
        "has_anom": has_anom,
        "has_data": has_data,
        "has_light": has_light,
        "use_hf_hub": settings.USE_HF_HUB,
        "hf_repo": settings.HF_REPO_ID,
        "hf_token_set": bool(hf_hub_token()),
        "detail": detail,
    }


def warm_sim_ml_artifacts() -> None:
    """Télécharge les artefacts essentiels (cache HF)."""
    sim_ml_status.cache_clear()
    for name in SIM_WARM_FILES:
        artifact_path(name)


def clear_sim_ml_status_cache() -> None:
    sim_ml_status.cache_clear()
