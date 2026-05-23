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


NB3_ZERO_AS_MISSING = frozenset({
    "economie_estimee_kwh",
    "economie_rl_kwh",
    "action_rl",
    "action_proposee",
    "mode_operation",
})


def _needs_fill_mask(series: pd.Series, column: str, zero_as_missing: bool) -> pd.Series:
    missing = blank_mask(series)
    if zero_as_missing and column in NB3_ZERO_AS_MISSING:
        numeric = pd.to_numeric(series, errors="coerce")
        missing = missing | numeric.fillna(0).le(0)
    return missing


def _coerce_merge_key(series: pd.Series, key: str) -> pd.Series:
    """Align merge key dtypes (upload CSV vs notebook parquet)."""
    if key == "station_id":
        return series.astype(str).str.strip()
    if key == "timestamp":
        ts = pd.to_datetime(series, errors="coerce")
        if getattr(ts.dt, "tz", None) is not None:
            ts = ts.dt.tz_convert("UTC").dt.tz_localize(None)
        return ts
    if key == "heure":
        return pd.to_numeric(series, errors="coerce").astype("Int64")
    return series


def _prepare_merge_keys(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    out = df.copy()
    for key in keys:
        if key in out.columns:
            out[key] = _coerce_merge_key(out[key], key)
    return out


def merge_business_columns(
    df: pd.DataFrame,
    source: pd.DataFrame,
    columns: list[str],
    keys: list[str],
    *,
    zero_as_missing: bool = False,
) -> pd.DataFrame:
    """Fill missing or blank business columns from notebook artefacts (NB2/NB3)."""
    if df.empty or source.empty:
        return df
    if not set(keys).issubset(df.columns) or not set(keys).issubset(source.columns):
        return df

    available = [col for col in columns if col in source.columns and col not in keys]
    if not available:
        return df

    left = _prepare_merge_keys(df, keys)
    right = _prepare_merge_keys(
        source[keys + available].drop_duplicates(subset=keys, keep="last"),
        keys,
    )
    merged = left.merge(right, on=keys, how="left", suffixes=("", "_nb_src"))

    for col in available:
        src_name = f"{col}_nb_src"
        if src_name not in merged.columns:
            continue
        if col not in merged.columns:
            merged[col] = merged[src_name]
        else:
            missing = _needs_fill_mask(merged[col], col, zero_as_missing)
            if missing.any():
                merged.loc[missing, col] = merged.loc[missing, src_name]
        merged = merged.drop(columns=[src_name], errors="ignore")

    return merged


def cap_economies_to_consumption(df: pd.DataFrame) -> pd.DataFrame:
    """Une économie horaire ne peut pas dépasser la conso de la même ligne."""
    if df.empty or "consommation_kwh" not in df.columns:
        return df
    out = df.copy()
    conso = numeric_series(out, "consommation_kwh", np.nan)
    valid_conso = conso > 0
    for col in ("economie_estimee_kwh", "economie_rl_kwh"):
        if col not in out.columns:
            continue
        eco = numeric_series(out, col, 0.0)
        capped = eco.copy()
        capped[valid_conso] = np.minimum(eco[valid_conso], conso[valid_conso])
        out[col] = capped
    return out


def harmonize_nb3_economies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Align NB3 columns for display:
    - plafonne les économies à la conso horaire
    - economie_kwh = max(RL, expert) par ligne
    - action_rl complété depuis action_proposee si vide
    """
    if df.empty:
        return df

    out = cap_economies_to_consumption(df.copy())
    est = numeric_series(out, "economie_estimee_kwh", 0.0)
    rl = numeric_series(out, "economie_rl_kwh", 0.0)
    out["economie_kwh"] = np.maximum(est, rl)
    if "consommation_kwh" in out.columns:
        conso = numeric_series(out, "consommation_kwh", np.nan)
        out["economie_kwh"] = np.where(conso > 0, np.minimum(out["economie_kwh"], conso), out["economie_kwh"])

    if "action_proposee" in out.columns:
        if "action_rl" not in out.columns:
            out["action_rl"] = out["action_proposee"]
        else:
            missing_action = blank_mask(out["action_rl"])
            if missing_action.any():
                out.loc[missing_action, "action_rl"] = out.loc[missing_action, "action_proposee"]

    return out


def economie_rl_kwh_series(df: pd.DataFrame) -> pd.Series:
    """Hourly RL economy (expert fallback when RL is empty/zero)."""
    if df.empty:
        return pd.Series(dtype=float)
    harmonized = harmonize_nb3_economies(df)
    return numeric_series(harmonized, "economie_rl_kwh", 0.0)


def effective_economie_kwh(df: pd.DataFrame) -> pd.Series:
    """Per-row NB3 economy (max RL vs expert), matching notebook / simulation."""
    if df.empty:
        return pd.Series(dtype=float)
    harmonized = harmonize_nb3_economies(df)
    return numeric_series(harmonized, "economie_kwh", 0.0)
