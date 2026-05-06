import io
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

def metric_value(source: dict, key: str, suffix: str = "", decimals: int | None = None) -> str:
    if not source or key not in source or source.get(key) is None:
        return "N/D"
    value = source[key]
    if isinstance(value, (int, np.integer)):
        return f"{value:,}{suffix}"
    if isinstance(value, (float, np.floating)):
        return f"{value:.{decimals if decimals is not None else 2}f}{suffix}"
    return f"{value}{suffix}"

def download_df_button(df: pd.DataFrame, name: str, label: str = "Exporter CSV"):
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    st.download_button(
        label,
        data=buf.getvalue(),
        file_name=name,
        mime="text/csv",
        key=f"download_{name}_{np.random.randint(0, 1000000)}",
        width="stretch",
    )

def artifact_notebook(label: str) -> str:
    if label.startswith("NB1"):
        return "NB1"
    if label.startswith("NB2"):
        return "NB2"
    if label.startswith("NB3"):
        return "NB3"
    return "Commun"

def fix_mojibake(value):
    if isinstance(value, str) and any(token in value for token in ("Ãƒ", "Ã¢", "ÃŽ")):
        try:
            return value.encode("latin1").decode("utf-8")
        except UnicodeError:
            return value
    if isinstance(value, dict):
        return {fix_mojibake(k): fix_mojibake(v) for k, v in value.items()}
    if isinstance(value, list):
        return [fix_mojibake(v) for v in value]
    return value
