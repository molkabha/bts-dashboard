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


def nb3_row_economie_kwh(df: pd.DataFrame) -> pd.Series:

    if df.empty:

        return pd.Series(dtype=float)

    est = numeric_series(df, "economie_estimee_kwh", 0.0)

    rl = numeric_series(df, "economie_rl_kwh", 0.0)

    combined = np.maximum(est.to_numpy(), rl.to_numpy())

    if "economie_kwh" not in df.columns:

        return pd.Series(combined, index=df.index, dtype=float)

    exported = numeric_series(df, "economie_kwh", 0.0)

    values = np.where(
        exported.gt(1e-9).to_numpy(),
        exported.to_numpy(),
        combined,
    )

    return pd.Series(values, index=df.index, dtype=float)


def harmonize_nb3_economies(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty:

        return df

    out = cap_economies_to_consumption(df.copy())

    out["economie_kwh"] = nb3_row_economie_kwh(out)

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

    return nb3_row_economie_kwh(df)


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


NB_STATION_SCORE_ARTIFACT = "streamlit_score_stations.parquet"

NB_SCORE_CRITICITE_WEIGHTS = (0.5, 0.3, 0.0286)

NB_CATEGORIE_EFFICACE_MAX = 0.05

NB_CATEGORIE_CRITIQUE_MIN = 0.15


def nb_categorie_from_criticite(score: float | pd.Series) -> str | pd.Series:

    crit = pd.to_numeric(score, errors="coerce")

    if isinstance(score, pd.Series):

        out = pd.Series("ATTENTION", index=crit.index, dtype=object)

        out.loc[crit.le(NB_CATEGORIE_EFFICACE_MAX)] = "EFFICACE"

        out.loc[crit.ge(NB_CATEGORIE_CRITIQUE_MIN)] = "CRITIQUE"

        return out

    if pd.isna(crit):

        return "ATTENTION"

    val = float(crit)

    if val <= NB_CATEGORIE_EFFICACE_MAX:

        return "EFFICACE"

    if val >= NB_CATEGORIE_CRITIQUE_MIN:

        return "CRITIQUE"

    return "ATTENTION"


def nb_score_criticite_from_components(
    pct_anomalie: pd.Series | float,
    score_moy: pd.Series | float,
    nb_votes_moy: pd.Series | float,
) -> pd.Series | float:

    w_pct, w_score, w_votes = NB_SCORE_CRITICITE_WEIGHTS

    crit = (
        pd.to_numeric(pct_anomalie, errors="coerce") * w_pct
        + pd.to_numeric(score_moy, errors="coerce") * w_score
        + pd.to_numeric(nb_votes_moy, errors="coerce") * w_votes
    )

    if isinstance(pct_anomalie, pd.Series):

        return crit.clip(lower=0)

    return float(max(0.0, crit))


def compute_nb_station_scores_from_df(
    df: pd.DataFrame, *, seuil_anom: float | None
) -> pd.DataFrame:

    if df.empty or "station_id" not in df.columns:

        return pd.DataFrame()

    work = df.copy()

    score_col = "anomalie_score_ensemble"

    if score_col not in work.columns:

        return pd.DataFrame()

    work["_score"] = pd.to_numeric(work[score_col], errors="coerce")

    if seuil_anom is not None:

        work["_pct_anom"] = work["_score"].gt(float(seuil_anom)).astype(float)

    else:

        work["_pct_anom"] = pd.NA

    if "nb_votes_anomalie" in work.columns:

        work["_votes"] = pd.to_numeric(work["nb_votes_anomalie"], errors="coerce")

    else:

        work["_votes"] = pd.NA

    agg: dict[str, tuple[str, str]] = {
        "score_moy_ensemble": ("_score", "mean"),
        "pct_anomalie_ensemble": ("_pct_anom", "mean"),
        "nb_votes_moy": ("_votes", "mean"),
    }

    for col in ("gouvernorat", "technologie", "type_zone"):

        if col in work.columns:

            agg[col] = (col, "first")

    if "score_qos" in work.columns:

        agg["score_qos_moy"] = ("score_qos", "mean")

    if "consommation_kwh" in work.columns:

        agg["conso_moy"] = ("consommation_kwh", "mean")

    out = work.groupby("station_id", as_index=False).agg(**agg)

    out["score_criticite"] = nb_score_criticite_from_components(
        out["pct_anomalie_ensemble"],
        out["score_moy_ensemble"],
        out["nb_votes_moy"],
    )

    out["categorie"] = nb_categorie_from_criticite(out["score_criticite"])

    return out
