"""Service for orchestrating the NB1/NB2/NB3 data pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd
from services.decision_service import MoteurDecisionEnergie
from services.nb_metrics import harmonize_nb3_economies
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


def _ensure_temporal_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Create standard temporal columns used by NB1/NB2/NB3 pages."""
    if "timestamp" not in df.columns:
        return df
    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    df["timestamp"] = ts
    if "heure" not in df.columns:
        df["heure"] = ts.dt.hour
    if "mois" not in df.columns:
        df["mois"] = ts.dt.month
    if "jour_semaine" not in df.columns:
        df["jour_semaine"] = ts.dt.weekday
    if "est_weekend" not in df.columns:
        df["est_weekend"] = pd.to_numeric(df["jour_semaine"], errors="coerce").ge(5).astype(int)
    return df


def _simulate_nb1_prediction(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add NB1-like prediction columns when the uploaded dataset does not already
    contain model outputs. This keeps the admin upload usable across all pages.
    """
    if "consommation_kwh" not in df.columns:
        return df

    conso = pd.to_numeric(df["consommation_kwh"], errors="coerce")
    if "conso_predite" not in df.columns or _blank_mask(df["conso_predite"]).any():
        pred = conso.copy()
        if {"station_id", "heure"}.issubset(df.columns):
            profile = (
                pd.DataFrame({"station_id": df["station_id"].astype(str), "heure": df["heure"], "conso": conso})
                .groupby(["station_id", "heure"])["conso"]
                .transform("median")
            )
            pred = profile.fillna(conso.median()).astype(float)
        elif "heure" in df.columns:
            pred = conso.groupby(df["heure"]).transform("median").fillna(conso.median())
        else:
            pred = conso.rolling(24, min_periods=1).median().fillna(conso.median())
        df["conso_predite"] = pred.round(3)

    pred = pd.to_numeric(df["conso_predite"], errors="coerce").fillna(conso)
    if "pred_q10" not in df.columns:
        df["pred_q10"] = (pred * 0.90).round(3)
    if "pred_q90" not in df.columns:
        df["pred_q90"] = (pred * 1.10).round(3)
    if "ecart_pct" not in df.columns:
        df["ecart_pct"] = ((conso - pred) / pred.replace(0, np.nan) * 100).replace([np.inf, -np.inf], np.nan).fillna(0)
    return df


def _simulate_nb2_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Add NB2-like anomaly scores and detector votes when missing."""
    has_scores = (
        "anomalie_score_ensemble" in df.columns
        and "nb_votes_anomalie" in df.columns
        and not _blank_mask(df["anomalie_score_ensemble"]).any()
        and not _blank_mask(df["nb_votes_anomalie"]).any()
    )
    if has_scores:
        return df

    index = df.index
    conso = pd.to_numeric(df.get("consommation_kwh", pd.Series(0, index=index)), errors="coerce").fillna(0)
    pred = pd.to_numeric(df.get("conso_predite", conso), errors="coerce").fillna(conso)
    cpu = pd.to_numeric(df.get("charge_cpu_pct", pd.Series(50, index=index)), errors="coerce").fillna(50)
    qos = pd.to_numeric(df.get("score_qos", pd.Series(0.82, index=index)), errors="coerce").fillna(0.82)
    voix = pd.to_numeric(df.get("taux_charge_voix", pd.Series(0.2, index=index)), errors="coerce").fillna(0.2)
    data = pd.to_numeric(df.get("taux_charge_data", pd.Series(0.3, index=index)), errors="coerce").fillna(0.3)

    residual = ((conso - pred).abs() / pred.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0)
    cpu_score = ((cpu - 70) / 30).clip(lower=0, upper=1)
    qos_score = ((0.75 - qos) / 0.35).clip(lower=0, upper=1)
    traffic_score = ((voix + data - 1.05) / 0.75).clip(lower=0, upper=1)
    anomaly_score = (0.45 * residual.clip(0, 1) + 0.20 * cpu_score + 0.25 * qos_score + 0.10 * traffic_score).clip(0, 1)

    if "anomalie_score_ensemble" not in df.columns:
        df["anomalie_score_ensemble"] = anomaly_score.round(3)
    if "nb_votes_anomalie" not in df.columns:
        votes = (
            residual.gt(0.25).astype(int)
            + residual.gt(0.40).astype(int)
            + cpu_score.gt(0.35).astype(int)
            + cpu_score.gt(0.65).astype(int)
            + qos_score.gt(0.25).astype(int)
            + qos_score.gt(0.55).astype(int)
            + traffic_score.gt(0.35).astype(int)
        )
        df["nb_votes_anomalie"] = votes.astype(int)
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
    df = _ensure_temporal_columns(df)
    df = _simulate_nb1_prediction(df)
    df = _simulate_nb2_anomalies(df)

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
            merged = df.merge(
                decisions[[c for c in keep if c in decisions.columns]],
                on=["station_id", "heure"],
                how="left",
                suffixes=("", "_nb3"),
            )
            for col in ["action_rl", "economie_rl_kwh", "mode_majoritaire"]:
                src = f"{col}_nb3"
                if src not in merged.columns:
                    continue
                if col not in merged.columns:
                    merged[col] = merged[src]
                else:
                    missing = _blank_mask(merged[col])
                    if missing.any():
                        merged.loc[missing, col] = merged.loc[missing, src]
                merged = merged.drop(columns=[src], errors="ignore")
            df = merged

    # 3. Fallbacks for RL columns (notebook: RL inherits expert when not computed)
    if "action_proposee" in df.columns:
        if "action_rl" not in df.columns:
            df["action_rl"] = df["action_proposee"]
        else:
            missing_action = _blank_mask(df["action_rl"])
            if missing_action.any():
                df.loc[missing_action, "action_rl"] = df.loc[missing_action, "action_proposee"]

    if "economie_estimee_kwh" in df.columns:
        if "economie_rl_kwh" not in df.columns:
            df["economie_rl_kwh"] = df["economie_estimee_kwh"]
        else:
            rl = pd.to_numeric(df["economie_rl_kwh"], errors="coerce")
            est = pd.to_numeric(df["economie_estimee_kwh"], errors="coerce")
            missing_rl = _blank_mask(df["economie_rl_kwh"]) | ((rl.fillna(0) <= 0) & (est.fillna(0) > 0))
            if missing_rl.any():
                df.loc[missing_rl, "economie_rl_kwh"] = df.loc[missing_rl, "economie_estimee_kwh"]

    return harmonize_nb3_economies(df)
