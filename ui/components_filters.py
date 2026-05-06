"""Reusable filter components for admin views."""
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd


def render_admin_global_filters(df: pd.DataFrame) -> dict:
    """
    Render filter UI for admin global views (period, stations, dimensions).
    Stores filters in st.session_state["admin_global_filters"] and ["admin_time_filters"]
    Returns the filter configuration dict.
    """
    st.subheader("🔍 Filtres globaux")
    
    filters = {}
    
    # --- PERIOD FILTERS (Time dimension) ---
    period_cols = st.columns(3)
    
    with period_cols[0]:
        date_from = st.date_input(
            "Date début",
            value=datetime.now().date() - timedelta(days=30),
            key="admin_filter_date_from"
        )
    
    with period_cols[1]:
        date_to = st.date_input(
            "Date fin",
            value=datetime.now().date(),
            key="admin_filter_date_to"
        )
    
    with period_cols[2]:
        hour_range = st.slider(
            "Plage horaire",
            0, 23, (6, 22),
            key="admin_filter_hours"
        )
    
    # Store time filters
    time_filters = {
        "date_range": (date_from, date_to),
        "hours": hour_range,
    }
    st.session_state["admin_time_filters"] = time_filters
    filters["date_range"] = (date_from, date_to)
    filters["hours"] = hour_range
    
    # --- DIMENSION FILTERS ---
    st.divider()
    dim_cols = st.columns(4)
    
    # Stations
    with dim_cols[0]:
        if "station_id" in df.columns:
            stations = sorted(df["station_id"].dropna().unique().astype(str).tolist())
            sel_stations = st.multiselect(
                "Stations",
                stations,
                default=stations[:50] if len(stations) > 50 else stations,
                key="admin_filter_stations"
            )
            filters["stations"] = sel_stations
        else:
            filters["stations"] = []
    
    # Governorats
    with dim_cols[1]:
        if "gouvernorat" in df.columns:
            govs = sorted(df["gouvernorat"].dropna().unique().astype(str).tolist())
            sel_govs = st.multiselect(
                "Gouvernorats",
                govs,
                default=govs,
                key="admin_filter_govs"
            )
            filters["gouvernorats"] = sel_govs
        else:
            filters["gouvernorats"] = []
    
    # Technologies
    with dim_cols[2]:
        if "technologie" in df.columns:
            techs = sorted(df["technologie"].dropna().unique().astype(str).tolist())
            sel_techs = st.multiselect(
                "Technologies",
                techs,
                default=techs,
                key="admin_filter_techs"
            )
            filters["technologies"] = sel_techs
        else:
            filters["technologies"] = []
    
    # Zone types
    with dim_cols[3]:
        if "type_zone" in df.columns:
            zones = sorted(df["type_zone"].dropna().unique().astype(str).tolist())
            sel_zones = st.multiselect(
                "Types zone",
                zones,
                default=zones,
                key="admin_filter_zones"
            )
            filters["zones"] = sel_zones
        else:
            filters["zones"] = []
    
    # --- THRESHOLD FILTERS ---
    st.divider()
    thresh_cols = st.columns(3)
    
    with thresh_cols[0]:
        qos_min = st.slider(
            "Score QoS minimum",
            0.0, 1.0, 0.0, 0.05,
            key="admin_filter_qos_min"
        )
        filters["qos_min"] = qos_min
    
    with thresh_cols[1]:
        if "anomalie_score_ensemble" in df.columns:
            score_min = st.slider(
                "Score anomalie minimum",
                0.0, 1.0, 0.0, 0.05,
                key="admin_filter_score_min"
            )
            filters["score_min"] = score_min
        else:
            filters["score_min"] = 0.0
    
    with thresh_cols[2]:
        if "categorie" in df.columns:
            categories = sorted(df["categorie"].dropna().unique().astype(str).tolist())
            sel_cats = st.multiselect(
                "Criticité",
                categories,
                default=categories,
                key="admin_filter_criticites"
            )
            filters["criticites"] = sel_cats
        else:
            filters["criticites"] = []
    
    # Store dimension filters
    st.session_state["admin_global_filters"] = filters
    
    # Display active filters summary
    with st.expander("📋 Résumé des filtres actifs", expanded=False):
        summary = f"""
        **Période :** {date_from} à {date_to} | Heures {hour_range[0]:02d}-{hour_range[1]:02d}  
        **Stations :** {len(sel_stations) if 'sel_stations' in locals() else 0} sélectionnées  
        **Gouvernorats :** {len(sel_govs) if 'sel_govs' in locals() else 0} sélectionnés  
        **Technologies :** {len(sel_techs) if 'sel_techs' in locals() else 0} sélectionnées  
        **Seuils :** QoS ≥ {qos_min:.2f} | Score anomalie ≥ {filters.get('score_min', 0):.2f}
        """
        st.markdown(summary)
    
    return filters
