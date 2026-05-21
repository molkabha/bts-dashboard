import io
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np

from services.data_service import (
    apply_admin_dimension_filters,
    apply_time_filters,
    load_outputs,
)


def metric_value(source: dict, key: str, suffix: str = "", decimals: int | None = None) -> str:
    if not source or key not in source or source.get(key) is None:
        return "0" + suffix
    value = source[key]
    if pd.isna(value):
        return "0" + suffix
    if isinstance(value, (int, np.integer)):
        return f"{value:,}{suffix}"
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return "0" + suffix
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
        key=f"download_{name}",
        width="stretch",
    )


def session_outputs() -> dict:
    outputs = st.session_state.get("data")
    if outputs is None:
        outputs = load_outputs()
        st.session_state["data"] = outputs
    return outputs


def apply_current_admin_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # RLS Enforcement (Row-Level Security)
    if st.session_state.get("role") != "admin":
        from services.data_service import get_user_stations
        username = st.session_state.get("username")
        assigned = get_user_stations(username) if username else []
        if assigned and "station_id" in df.columns:
            df = df[df["station_id"].isin(assigned)]
        elif not assigned and "station_id" in df.columns:
            # If engineer has 0 stations assigned, return empty dataframe
            df = df.iloc[0:0]

    out = apply_admin_dimension_filters(df)
    filters = st.session_state.get("admin_time_filters", {})
    if filters:
        out = apply_time_filters(out, {
            "date_range": filters.get("date_range"),
            "hours": filters.get("hours"),
            "months": None,
            "day_type": "Tous",
            "days": None,
        })

    # Apply new global sidebar filters
    gf = st.session_state.get("global_filters", {})
    if gf:
        if "date_range" in gf and "timestamp" in out.columns:
            out = apply_time_filters(out, {"date_range": gf["date_range"]})
        stations = gf.get("stations")
        if stations is not None and "station_id" in out.columns:
            out = out[out["station_id"].astype(str).isin([str(s) for s in stations])]
        for key, col in [("gouvernorats", "gouvernorat"), ("technologies", "technologie"), ("zones", "type_zone")]:
            vals = gf.get(key)
            if vals and col in out.columns:
                out = out[out[col].astype(str).isin(vals)]
    return out


def selected_station_filter() -> str | None:
    stations = st.session_state.get("global_filters", {}).get("stations") or []
    stations = [str(station) for station in stations if str(station).strip()]
    return stations[0] if len(stations) == 1 else None


def active_filter_label() -> str:
    gf = st.session_state.get("global_filters", {})
    parts = []
    station = selected_station_filter()
    if station:
        parts.append(f"Station {station}")
    elif gf.get("stations"):
        parts.append(f"{len(gf['stations'])} stations")
    if gf.get("gouvernorats"):
        parts.append(f"{len(gf['gouvernorats'])} gouvernorats")
    if gf.get("technologies"):
        parts.append(f"{len(gf['technologies'])} technologies")
    if gf.get("zones"):
        parts.append(f"{len(gf['zones'])} zones")
    if gf.get("date_range"):
        start, end = gf["date_range"]
        parts.append(f"{start} -> {end}")
    return "Contexte filtre : " + " | ".join(parts) if parts else "Contexte filtre : vue globale"


def filter_artifact_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply dashboard filters to notebook tables when matching columns exist."""
    if df.empty:
        return df
    return apply_current_admin_filters(df)


def selected_ref_from_table_event(event, table: pd.DataFrame, ref_col: str) -> str | None:
    """Extract the selected business reference from a selectable dataframe."""
    rows = None
    selection = getattr(event, "selection", None)
    if selection is not None:
        rows = getattr(selection, "rows", None)
    if rows is None and isinstance(event, dict):
        rows = event.get("selection", {}).get("rows")
    if not rows or ref_col not in table.columns:
        return None
    try:
        row_pos = int(rows[0])
    except (TypeError, ValueError):
        return None
    if row_pos < 0 or row_pos >= len(table):
        return None
    return str(table.iloc[row_pos][ref_col])


def sync_selectbox_with_table_selection(
    event,
    table: pd.DataFrame,
    ref_col: str,
    options: list[str],
    state_key: str,
) -> int:
    """Keep a selectbox key aligned with the last clicked dataframe row."""
    options = [str(option) for option in options]
    clicked_ref = selected_ref_from_table_event(event, table, ref_col)
    current = st.session_state.get(state_key)
    if clicked_ref in options and current != clicked_ref:
        st.session_state[state_key] = clicked_ref
        current = clicked_ref
    if current not in options:
        current = options[0] if options else None
        if current is not None:
            st.session_state[state_key] = current
    return options.index(current) if current in options else 0


def current_operational_mask(df: pd.DataFrame) -> pd.Series:
    """
    Mark rows that represent the current actionable automatic choice.

    Historical rows remain visible for audit/analysis, but NB2/NB3 human
    overrides are only allowed on the latest available timestamp per station.
    If an aggregate table has no timestamp but has `heure`, only the current
    hour is actionable.
    """
    if df.empty:
        return pd.Series(dtype=bool)

    mask = pd.Series(False, index=df.index)
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
        now = pd.Timestamp.now(tz=ts.dt.tz if getattr(ts.dt, "tz", None) else None)
        not_future = ts.notna() & (ts <= now)
        if "station_id" in df.columns:
            latest = ts.groupby(df["station_id"].astype(str)).transform("max")
        else:
            latest = pd.Series(ts.max(), index=df.index)
        return (ts == latest) & not_future

    if "heure" in df.columns:
        hour = pd.to_numeric(df["heure"], errors="coerce")
        return hour == datetime.now().hour

    return mask


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
