"""Shared NB1/NB2/NB3 metric helpers — align dashboard values with notebook artefacts."""

from __future__ import annotations

import numpy as np
import pandas as pd


def blank_mask(series: pd.Series) -> pd.Series:
    """Rows where a business column has no usable value."""
    if pd.api.types.is_string_dtype(series) or series.dtype == object:
        return series.isna() | series.astype(str).str.strip().isin(["", "None", "nan", "NaN"])
    numeric = pd.to_numeric(series, errors="coerce")
    return series.isna() | numeric.isna()


def numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(default)


def merge_business_columns(
    df: pd.DataFrame,
    source: pd.DataFrame,
    columns: list[str],
    keys: list[str],
) -> pd.DataFrame:
    """Fill missing or blank business columns from notebook artefacts (NB2/NB3)."""
    if df.empty or source.empty:
        return df
    if not set(keys).issubset(df.columns) or not set(keys).issubset(source.columns):
        return df

    available = [col for col in columns if col in source.columns and col not in keys]
    if not available:
        return df

    right = source[keys + available].drop_duplicates(subset=keys, keep="last")
    merged = df.merge(right, on=keys, how="left", suffixes=("", "_nb_src"))

    for col in available:
        src_name = f"{col}_nb_src"
        if src_name not in merged.columns:
            continue
        if col not in merged.columns:
            merged[col] = merged[src_name]
        else:
            missing = blank_mask(merged[col])
            if missing.any():
                merged.loc[missing, col] = merged.loc[missing, src_name]
        merged = merged.drop(columns=[src_name], errors="ignore")

    return merged


def harmonize_nb3_economies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Align NB3 economy columns with notebook logic:
    - fill RL / action gaps from expert columns when RL is empty or zero
    - expose economie_kwh = max(RL, expert) for KPIs and charts
    """
    if df.empty:
        return df

    out = df.copy()
    est = numeric_series(out, "economie_estimee_kwh", 0.0)
    rl = numeric_series(out, "economie_rl_kwh", np.nan)

    if "economie_estimee_kwh" in out.columns:
        rl_missing = rl.isna() | ((rl <= 0) & (est > 0))
        if "economie_rl_kwh" not in out.columns:
            out["economie_rl_kwh"] = est
        elif rl_missing.any():
            out.loc[rl_missing, "economie_rl_kwh"] = est.loc[rl_missing]

    if "action_proposee" in out.columns:
        if "action_rl" not in out.columns:
            out["action_rl"] = out["action_proposee"]
        else:
            missing_action = blank_mask(out["action_rl"])
            if missing_action.any():
                out.loc[missing_action, "action_rl"] = out.loc[missing_action, "action_proposee"]

    rl_final = numeric_series(out, "economie_rl_kwh", 0.0)
    est_final = numeric_series(out, "economie_estimee_kwh", 0.0)
    out["economie_kwh"] = np.maximum(rl_final, est_final)
    return out


def effective_economie_kwh(df: pd.DataFrame) -> pd.Series:
    """Per-row NB3 economy (max RL vs expert), matching notebook / simulation."""
    if "economie_kwh" in df.columns:
        return numeric_series(df, "economie_kwh", 0.0)
    if df.empty:
        return pd.Series(dtype=float)
    harmonized = harmonize_nb3_economies(df)
    return numeric_series(harmonized, "economie_kwh", 0.0)
