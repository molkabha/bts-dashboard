"""Prepare uploaded datasets using notebook artefacts before publication."""

from __future__ import annotations

import pandas as pd

from services.data_service import (
    artifact_path,
    enrich_dashboard_data,
    normalize_dataframe_columns,
    read_parquet_fast,
)
from services.nb_metrics import blank_mask, harmonize_nb3_economies
from services.pipeline_service import simulate_nb_pipeline

NB1_COLUMNS = ["conso_predite", "pred_q10", "pred_q90", "ecart_pct"]
NB2_COLUMNS = ["anomalie_score_ensemble", "nb_votes_anomalie"]
NB3_COLUMNS = ["mode_operation", "action_proposee", "economie_estimee_kwh", "economie_rl_kwh", "action_rl"]


def _needs_pipeline_step(df: pd.DataFrame, columns: list[str]) -> bool:
    for col in columns:
        if col not in df.columns:
            return True
        if blank_mask(df[col]).any():
            return True
    return False


def prepare_published_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich from NB1/NB2/NB3 parquet/json artefacts, then run the dashboard pipeline
    only for columns still missing after merge.
    """
    if df.empty:
        return df

    out = normalize_dataframe_columns(df.copy())
    requested = list(dict.fromkeys(list(out.columns) + NB1_COLUMNS + NB2_COLUMNS + NB3_COLUMNS))
    out = enrich_dashboard_data(out, requested)

    needs_nb1 = _needs_pipeline_step(out, ["conso_predite"])
    needs_nb2 = _needs_pipeline_step(out, NB2_COLUMNS)
    needs_nb3 = _needs_pipeline_step(out, ["mode_operation", "action_proposee", "economie_estimee_kwh"])

    if not (needs_nb1 or needs_nb2 or needs_nb3):
        out = harmonize_nb3_economies(out)
        out["source_decision_nb3"] = "NB3"
        return out

    decisions = read_parquet_fast(
        artifact_path("decisions_par_station.parquet"),
        ["station_id", "heure", "action_rl", "economie_rl_kwh", "mode_majoritaire", "economie_estimee_kwh"],
    )
    out = simulate_nb_pipeline(out, source="import_utilisateur", decisions=decisions)
    if not needs_nb3 and "source_decision_nb3" not in out.columns:
        out["source_decision_nb3"] = "NB3"
    return out
