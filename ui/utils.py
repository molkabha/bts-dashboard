import io
import json
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np

from services.data_service import (
    apply_admin_dimension_filters,
    apply_time_filters,
    get_user_stations,
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


def clear_dashboard_data_cache() -> None:
    """Drop session caches so the next rerun reloads with new filters."""
    for key in ("_df_session_key", "_df_session_val", "_map_data_key", "_map_data_val", "_fleet_metrics", "_dashboard_df"):
        st.session_state.pop(key, None)


def reset_global_filters() -> None:
    """Clear sidebar filter widgets and cached dataframes."""
    for key in list(st.session_state.keys()):
        if key.startswith("sb_"):
            del st.session_state[key]
    st.session_state["global_filters"] = {}
    clear_dashboard_data_cache()


def merged_active_filters() -> dict:
    """Active filters = sidebar global_filters only (single source)."""
    return dict(st.session_state.get("global_filters") or {})


def filters_cache_key() -> str:
    """Stable key for session-level filtered dataframe cache."""
    gf = merged_active_filters()
    role = st.session_state.get("role", "")
    user = st.session_state.get("username") or st.session_state.get("user", "")
    assigned: tuple[str, ...] = ()
    if role != "admin" and user:
        assigned = tuple(sorted(str(s) for s in get_user_stations(user)))
    return json.dumps({"gf": gf, "role": role, "assigned": assigned}, sort_keys=True, default=str)


def apply_current_admin_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    filters = merged_active_filters()
    out = df

    if st.session_state.get("role") != "admin":
        username = st.session_state.get("username") or st.session_state.get("user")
        assigned = get_user_stations(username) if username else []
        if "station_id" in out.columns:
            if assigned:
                allowed = {str(s) for s in assigned}
                out = out[out["station_id"].astype(str).isin(allowed)]
            else:
                return out.iloc[0:0]

    if filters:
        out = apply_admin_dimension_filters(out, filters)
        out = apply_time_filters(out, filters)

    return out


def selected_station_filter() -> str | None:
    stations = merged_active_filters().get("stations") or []
    stations = [str(station) for station in stations if str(station).strip()]
    return stations[0] if len(stations) == 1 else None


def active_filter_label() -> str:
    gf = merged_active_filters()
    if not gf:
        return "Filtres : vue globale (toutes les donnees)"
    parts = []
    station = selected_station_filter()
    if station:
        parts.append(f"station {station}")
    elif gf.get("stations"):
        parts.append(f"{len(gf['stations'])} stations")
    if gf.get("gouvernorats"):
        parts.append(", ".join(gf["gouvernorats"][:3]) + ("…" if len(gf["gouvernorats"]) > 3 else ""))
    if gf.get("technologies"):
        parts.append(f"{len(gf['technologies'])} techno")
    if gf.get("modes"):
        parts.append("/".join(gf["modes"]))
    if gf.get("date_range"):
        start, end = gf["date_range"]
        parts.append(f"{start} → {end}")
    return "Filtres actifs : " + " · ".join(parts)


def filter_artifact_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return apply_current_admin_filters(df)


def selected_ref_from_table_event(event, table: pd.DataFrame, ref_col: str) -> str | None:
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
    if df.empty:
        return pd.Series(dtype=bool)

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

    return pd.Series(False, index=df.index)


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
