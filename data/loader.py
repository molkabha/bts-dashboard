from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    import pyarrow.parquet as pq
except Exception:
    pq = None


def existing_columns(path: Path) -> list[str]:
    try:
        if pq is not None:
            return pq.read_schema(path).names
        return pd.read_parquet(path).columns.tolist()
    except Exception:
        return []


def read_parquet_fast(path: Path, columns: list[str] | None = None, filters=None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    cols = None
    if columns:
        available = existing_columns(path)
        cols = [c for c in columns if c in available]
    try:
        df = pd.read_parquet(path, columns=cols, filters=filters)
    except Exception:
        try:
            df = pd.read_parquet(path, columns=cols)
        except Exception:
            return pd.DataFrame()
        if filters:
            for col, op, value in filters:
                if op == "=" and col in df.columns:
                    df = df[df[col].astype(str) == str(value)]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


def read_uploaded(uploaded) -> pd.DataFrame:
    name = str(getattr(uploaded, "name", "")).lower()
    size = getattr(uploaded, "size", 0) or 0
    if size > 250 * 1024 * 1024:
        raise ValueError("Fichier trop volumineux.")
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded)
    elif name.endswith(".parquet"):
        df = pd.read_parquet(uploaded, columns=None)
    else:
        raise ValueError("Format non supporte.")
    if df.empty:
        raise ValueError("Dataset vide.")
    if len(df.columns) > 250:
        raise ValueError("Dataset refuse: trop de colonnes.")
    return df
