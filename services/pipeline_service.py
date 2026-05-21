"""Service for orchestrating the NB1/NB2/NB3 data pipeline."""

from __future__ import annotations

import pandas as pd
from services.decision_service import MoteurDecisionEnergie
from services.optimization_service import StrategieOptimisation


def _blank_mask(series: pd.Series) -> pd.Series:
    """Return rows where a business column has no usable value."""
    if pd.api.types.is_string_dtype(series) or series.dtype == object:
        return series.isna() | series.astype(str).str.strip().isin(["", "None", "nan", "NaN"])
    return series.isna()


def _fill_business_columns(df: pd.DataFrame, source: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Fill missing or empty business columns without overwriting valid notebook/import values."""
    for col in columns:
        if col not in source.columns:
            continue
        if col not in df.columns:
            df[col] = source[col]
            continue
        missing = _blank_mask(df[col])
        if missing.any():
            df.loc[missing, col] = source.loc[missing, col]
    return df


def simulate_nb_pipeline(
    df_in: pd.DataFrame,
    thresholds: dict | None = None,
    decisions: pd.DataFrame | None = None,
    source: str = "notebook_outputs",
) -> pd.DataFrame:
    """
    Simulate the full NB1/NB2/NB3 pipeline on a given dataset.

    Args:
        df_in: Input DataFrame.
        thresholds: Thresholds for decision engine.
        decisions: Historical or reference decisions to merge.
        source: Source of the data (influences logic).

    Returns:
        pd.DataFrame: Processed DataFrame with decision and optimization columns.
    """
    df = df_in.copy()

    # 1. Basic Decision Logic (NB1/NB2 results mapping to modes)
    has_nb3_decision = {"mode_operation", "action_proposee", "economie_estimee_kwh"}.issubset(df.columns)

    if source == "notebook_outputs" and has_nb3_decision and not any(
        _blank_mask(df[col]).any() for col in ["mode_operation", "action_proposee", "economie_estimee_kwh"]
    ):
        df["source_decision_nb3"] = "NB3"
    else:
        decisions_locales = MoteurDecisionEnergie(thresholds or {}).appliquer_sur_dataset(df)
        df = _fill_business_columns(
            df,
            decisions_locales,
            ["mode_operation", "priorite", "action_principale", "eco_potentiel_pct", "risque_qos"],
        )

        strategies_locales = StrategieOptimisation().appliquer(df)
        df = _fill_business_columns(df, strategies_locales, ["action_proposee", "economie_estimee_kwh"])

        # Audit source
        df["source_decision_nb3"] = (
            "calcule_dashboard_depuis_saisie_manuelle"
            if source == "saisie_manuelle"
            else "calcule_dashboard_depuis_flux_genere"
            if source == "flux_temps_reel_genere"
            else "calcule_dashboard_depuis_import"
            if source != "notebook_outputs"
            else "calcule_dashboard_colonnes_nb3_manquantes"
        )

    # 2. Merge with specific NB3 decisions if available
    if source in {"notebook_outputs", "import_utilisateur"} and isinstance(
            decisions, pd.DataFrame) and {"station_id", "heure"}.issubset(df.columns):
        keep = ["station_id", "heure", "action_rl", "economie_rl_kwh", "mode_majoritaire"]
        missing_keep = [c for c in ["action_rl", "economie_rl_kwh", "mode_majoritaire"] if c not in df.columns]
        if missing_keep and {"station_id", "heure"}.issubset(decisions.columns):
            df = df.merge(
                decisions[[c for c in keep if c in decisions.columns]],
                on=["station_id", "heure"],
                how="left",
                suffixes=("", "_nb3_station"),
            )

    # 3. Fallbacks for RL columns
    if "action_rl" not in df.columns:
        df["action_rl"] = df["action_proposee"]
    if "economie_rl_kwh" not in df.columns:
        df["economie_rl_kwh"] = df["economie_estimee_kwh"]

    return df
