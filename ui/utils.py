"""Streamlit session helpers: filters, exports, artefact session."""

from __future__ import annotations

import io
import json

import pandas as pd
import streamlit as st

from services.data_service import (
    apply_admin_dimension_filters,
    apply_time_filters,
    get_user_stations,
    load_inactive_stations,
    load_outputs,
)


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


def is_admin() -> bool:
    return st.session_state.get("role") == "admin"


def redirect_engineer_home() -> None:
    """Send non-admin users to their default page (Accueil)."""
    st.session_state["_nav_override"] = 0
    st.rerun()


def session_outputs() -> dict:
    outputs = st.session_state.get("data")
    if outputs is None:
        outputs = load_outputs()
        st.session_state["data"] = outputs
    return outputs


def clear_dashboard_data_cache() -> None:
    for key in ("_df_session_key", "_df_session_val", "_map_data_key", "_map_data_val", "_dashboard_df"):
        st.session_state.pop(key, None)


def reset_global_filters() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("sb_"):
            del st.session_state[key]
    st.session_state["global_filters"] = {}
    clear_dashboard_data_cache()


def merged_active_filters() -> dict:
    return dict(st.session_state.get("global_filters") or {})


def filters_cache_key() -> str:
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

    if "station_id" in out.columns:
        inactive = load_inactive_stations()
        if inactive:
            out = out[~out["station_id"].astype(str).isin(inactive)]

    return out


def selected_station_filter() -> str | None:
    stations = merged_active_filters().get("stations") or []
    stations = [str(station) for station in stations if str(station).strip()]
    return stations[0] if len(stations) == 1 else None


def active_filter_label() -> str:
    gf = merged_active_filters()
    if not gf:
        return "Periode et stations : tout le parc"
    parts = []
    station = selected_station_filter()
    if station:
        parts.append(station)
    elif gf.get("stations"):
        parts.append(f"{len(gf['stations'])} stations")
    if gf.get("date_range"):
        start, end = gf["date_range"]
        parts.append(f"{start} → {end}")
    if gf.get("gouvernorats"):
        parts.append(", ".join(gf["gouvernorats"][:2]))
    if gf.get("modes"):
        parts.append("/".join(gf["modes"]))
    return " · ".join(parts)
