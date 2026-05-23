"""Prepare uploaded datasets using notebook artefacts before publication."""

from __future__ import annotations

import pandas as pd

from config.settings import settings
from services.data_service import (
    artifact_path,
    enrich_dashboard_data,
    normalize_dataframe_columns,
    read_parquet_fast,
)
from services.nb_metrics import blank_mask, harmonize_nb3_economies

NB1_COLUMNS = ["conso_predite", "pred_q10", "pred_q90", "ecart_pct"]
NB2_COLUMNS = ["anomalie_score_ensemble", "nb_votes_anomalie"]
NB3_COLUMNS = ["mode_operation", "action_proposee", "economie_estimee_kwh", "economie_rl_kwh", "action_rl"]


class PublishDatasetError(ValueError):
    """Raised when notebook artefacts are missing and dashboard simulation is disabled."""


def _needs_pipeline_step(df: pd.DataFrame, columns: list[str]) -> bool:
    for col in columns:
        if col not in df.columns:
            return True
        if blank_mask(df[col]).any():
            return True
    return False


def _artifact_exists(filename: str) -> bool:
    return artifact_path(filename).exists()


def _missing_nb_artifacts(needs_nb1: bool, needs_nb2: bool, needs_nb3: bool) -> list[str]:
    missing: list[str] = []
    if needs_nb1:
        if not _artifact_exists("streamlit_data.parquet") and not _artifact_exists("df_full_processed.parquet"):
            missing.append("NB1 : streamlit_data.parquet ou df_full_processed.parquet (conso_predite)")
    if needs_nb2:
        if not _artifact_exists(settings.ANOMALY_DATASET):
            missing.append(f"NB2 : {settings.ANOMALY_DATASET}")
        if not _artifact_exists("resultats_anomalie.json"):
            missing.append("NB2 : resultats_anomalie.json")
    if needs_nb3:
        if not _artifact_exists("streamlit_data.parquet"):
            missing.append("NB3 : streamlit_data.parquet")
        if not _artifact_exists("kpi_reseau.json"):
            missing.append("NB3 : kpi_reseau.json")
    return missing


def prepare_published_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich from NB1/NB2/NB3 parquet/json artefacts only.
    Dashboard pipeline simulation is disabled: missing notebook columns block publication.
    """
    if df.empty:
        return df

    out = normalize_dataframe_columns(df.copy())
    requested = list(dict.fromkeys(list(out.columns) + NB1_COLUMNS + NB2_COLUMNS + NB3_COLUMNS))
    out = enrich_dashboard_data(out, requested)

    needs_nb1 = _needs_pipeline_step(out, ["conso_predite"])
    needs_nb2 = _needs_pipeline_step(out, NB2_COLUMNS)
    needs_nb3 = _needs_pipeline_step(out, ["mode_operation", "action_proposee", "economie_estimee_kwh"])

    if needs_nb1 or needs_nb2 or needs_nb3:
        missing = _missing_nb_artifacts(needs_nb1, needs_nb2, needs_nb3)
        details = "\n".join(f"  - {item}" for item in missing) if missing else (
            "  - Colonnes notebook encore vides apres fusion des parquets"
        )
        raise PublishDatasetError(
            "Publication bloquee : les sorties notebook sont incompletes. "
            "Executez NB1, NB2 et NB3, puis publiez les artefacts (VF/*/output ou Hugging Face molkab/dashboard).\n"
            f"{details}"
        )

    out = harmonize_nb3_economies(out)
    if "source_decision_nb3" not in out.columns:
        out["source_decision_nb3"] = "NB3"
    else:
        nb3_mask = ~blank_mask(out["mode_operation"]) if "mode_operation" in out.columns else pd.Series(False, index=out.index)
        if nb3_mask.any():
            out.loc[nb3_mask, "source_decision_nb3"] = "NB3"
    return out
