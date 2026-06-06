from __future__ import annotations

import numpy as np

import pandas as pd

from config.settings import settings


def blank_mask(series: pd.Series) -> pd.Series:

    if pd.api.types.is_string_dtype(series) or series.dtype == object:

        return series.isna() | series.astype(str).str.strip().isin(
            ["", "None", "nan", "NaN"]
        )

    numeric = pd.to_numeric(series, errors="coerce")

    return series.isna() | numeric.isna()


def numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:

    if column not in df.columns:

        return pd.Series(default, index=df.index, dtype=float)

    return pd.to_numeric(df[column], errors="coerce").fillna(default)


NB3_ZERO_AS_MISSING = frozenset(
    {
        "economie_estimee_kwh",
        "economie_rl_kwh",
        "action_rl",
        "action_proposee",
        "mode_operation",
    }
)


def _needs_fill_mask(
    series: pd.Series, column: str, zero_as_missing: bool
) -> pd.Series:

    missing = blank_mask(series)

    if zero_as_missing and column in NB3_ZERO_AS_MISSING:

        numeric = pd.to_numeric(series, errors="coerce")

        missing = missing | numeric.fillna(0).le(0)

    return missing


def _coerce_merge_key(series: pd.Series, key: str) -> pd.Series:

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

    if df.empty or source.empty:

        return df

    if not set(keys).issubset(df.columns) or not set(keys).issubset(source.columns):

        return df

    available = [col for col in columns if col in source.columns and col not in keys]

    if not available:

        return df

    left = _prepare_merge_keys(df, keys)

    right = _prepare_merge_keys(
        source[keys + available].drop_duplicates(subset=keys, keep="last"), keys
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


def compute_ecart_pct(conso: pd.Series, pred: pd.Series) -> pd.Series:

    c = pd.to_numeric(conso, errors="coerce")

    p = pd.to_numeric(pred, errors="coerce")

    return ((c - p) / p.replace(0, pd.NA) * 100).fillna(0.0)


def ecart_pct_series(df: pd.DataFrame) -> pd.Series:

    if df.empty or "conso_predite" not in df.columns:

        return pd.Series(0.0, index=df.index, dtype=float)

    return compute_ecart_pct(df["consommation_kwh"], df["conso_predite"])


def cap_economies_to_consumption(df: pd.DataFrame) -> pd.DataFrame:

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

    if df.empty:

        return df

    out = cap_economies_to_consumption(df.copy())

    exported = (
        numeric_series(out, "economie_kwh", 0.0)
        if "economie_kwh" in out.columns
        else pd.Series(0.0, index=out.index, dtype=float)
    )

    has_export = exported.gt(1e-9)

    est = numeric_series(out, "economie_estimee_kwh", 0.0)

    rl = numeric_series(out, "economie_rl_kwh", 0.0)

    computed = np.maximum(est, rl)

    if "consommation_kwh" in out.columns:

        conso = numeric_series(out, "consommation_kwh", np.nan)

        cap = conso * float(settings.NB3_MAX_ECO_FRAC)

        computed = np.where(conso > 0, np.minimum(computed, cap), computed)

    out["economie_kwh"] = np.where(has_export, exported, computed)

    if "consommation_kwh" in out.columns:

        conso = numeric_series(out, "consommation_kwh", np.nan)

        out["conso_optimisee_kwh"] = np.maximum(
            conso - numeric_series(out, "economie_kwh", 0.0), 0.0
        )

    if "action_proposee" in out.columns:

        if "action_rl" not in out.columns:

            out["action_rl"] = out["action_proposee"]

        else:

            missing_action = blank_mask(out["action_rl"])

            if missing_action.any():

                out.loc[missing_action, "action_rl"] = out.loc[
                    missing_action, "action_proposee"
                ]

    return out


def nb3_export_economie_kwh(df: pd.DataFrame) -> pd.Series:

    if df.empty:

        return pd.Series(dtype=float)

    if "economie_kwh" in df.columns:

        exported = numeric_series(df, "economie_kwh", 0.0)

        if exported.gt(1e-9).any():

            return exported

    est = numeric_series(df, "economie_estimee_kwh", 0.0)

    rl = numeric_series(df, "economie_rl_kwh", 0.0)

    if est.gt(1e-9).any() or rl.gt(1e-9).any():

        return np.maximum(est, rl)

    return effective_economie_kwh(df)


def effective_economie_kwh(df: pd.DataFrame) -> pd.Series:

    if df.empty:

        return pd.Series(dtype=float)

    harmonized = harmonize_nb3_economies(df)

    return numeric_series(harmonized, "economie_kwh", 0.0)


def conso_optimisee_kwh_series(df: pd.DataFrame) -> pd.Series:

    if df.empty:

        return pd.Series(dtype=float)

    harmonized = harmonize_nb3_economies(df)

    if "conso_optimisee_kwh" in harmonized.columns:

        return numeric_series(harmonized, "conso_optimisee_kwh", 0.0)

    conso = numeric_series(harmonized, "consommation_kwh", 0.0)

    eco = effective_economie_kwh(harmonized)

    return np.maximum(conso - eco, 0.0)
