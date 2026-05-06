import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from services.data_service import (
    load_filtered_main_data, compute_filtered_kpis, station_summary_from_df,
    apply_admin_dimension_filters, apply_time_filters, apply_station_criticite_filter
)
from ui.layout import header, kpi_card, section
from ui.components_filters import render_admin_global_filters
from security.middleware import security_middleware

def metric_value(source: dict, key: str, suffix: str = "", decimals: int | None = None) -> str:
    import numpy as np
    if not source or key not in source or source.get(key) is None:
        return "N/D"
    value = source[key]
    if isinstance(value, (int, np.integer)):
        return f"{value:,}{suffix}"
    if isinstance(value, (float, np.floating)):
        return f"{value:.{decimals if decimals is not None else 2}f}{suffix}"
    return f"{value}{suffix}"

def render_network_map(df: pd.DataFrame):
    map_df = station_summary_from_df(df)
    map_df = apply_station_criticite_filter(map_df)
    if map_df.empty or not {"latitude", "longitude"}.issubset(map_df.columns):
        st.warning("Carte indisponible pour les filtres selectionnes.")
        return
    size_col = "score_criticite" if "score_criticite" in map_df.columns else "conso_moy"
    color_col = "categorie" if "categorie" in map_df.columns else "technologie"
    map_func = getattr(px, "scatter_map", px.scatter_mapbox)
    fig = map_func(
        map_df,
        lat="latitude",
        lon="longitude",
        hover_name="station_id",
        hover_data=[c for c in ["gouvernorat", "technologie", "score_criticite", "score_qos_moy", "score_anom_moy"] if c in map_df.columns],
        color=color_col,
        size=size_col if size_col in map_df.columns else None,
        zoom=6,
        height=520,
    )
    if map_func == px.scatter_mapbox:
        fig.update_layout(mapbox_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
    else:
        fig.update_layout(map_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch")

def render_time_evolution(df: pd.DataFrame):
    if df.empty or "timestamp" not in df.columns:
        return
    ts = df.copy()
    ts["date"] = pd.to_datetime(ts["timestamp"], errors="coerce").dt.date
    for col in ["economie_estimee_kwh", "economie_rl_kwh", "anomalie_score_ensemble"]:
        if col not in ts.columns:
            ts[col] = 0
    daily = ts.groupby("date", as_index=False).agg(
        consommation_kwh=("consommation_kwh", "sum"),
        economie_experte_kwh=("economie_estimee_kwh", "sum"),
        economie_rl_kwh=("economie_rl_kwh", "sum"),
        score_anomalie=("anomalie_score_ensemble", "mean"),
    )
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["date"], y=daily["consommation_kwh"], name="Consommation"))
    fig.add_trace(go.Scatter(x=daily["date"], y=daily["economie_rl_kwh"], name="Economie RL"))
    fig.add_trace(go.Scatter(x=daily["date"], y=daily["score_anomalie"], name="Score anomalie", yaxis="y2"))
    fig.update_layout(yaxis_title="kWh", yaxis2=dict(title="Score", overlaying="y", side="right"), margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, width="stretch")

def admin_network_page():
    security_middleware.enforce(role="admin")
    header("Vue reseau", "Synthese decisionnelle NB1/NB2/NB3")
    
    cols = [
        "timestamp", "station_id", "gouvernorat", "type_zone", "technologie",
        "consommation_kwh", "conso_predite", "score_qos", "anomalie_score_ensemble",
        "mode_operation", "action_proposee", "economie_estimee_kwh", "action_rl",
        "economie_rl_kwh", "latitude", "longitude", "mois", "heure", "jour_semaine", "est_weekend"
    ]
    
    df_raw = load_filtered_main_data(cols)
    
    # Display filter UI
    render_admin_global_filters(df_raw)
    
    # Apply filters from session state
    df = apply_admin_dimension_filters(df_raw)
    filters = st.session_state.get("admin_time_filters", {})
    if filters:
        df = apply_time_filters(df, {
            "date_range": filters.get("date_range"),
            "hours": filters.get("hours"),
            "months": None, "day_type": "Tous", "days": None
        })
    
    if df.empty:
        render_empty_state(
            message="Veuillez ajuster vos filtres (Gouvernorat, Technologie, Date) ou vérifier l'importation des fichiers Parquet."
        )
        return
        
    outputs = st.session_state.get("data", {})
    # Use pre-computed KPIs only if they exist and we don't need filtered ones
    # For now, always compute on the filtered dataframe for accuracy
    kpi = compute_filtered_kpis(df)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("Stations", metric_value(kpi, "nb_stations"), "filtre actif")
    with c2:
        kpi_card("Mesures", metric_value(kpi, "nb_mesures"), "observations")
    with c3:
        kpi_card("Anomalies", metric_value(kpi, "pct_anomalies", "%", 2), "NB2", "orange")
    with c4:
        kpi_card("Economie RL", metric_value(kpi, "economie_rl_pct", "%", 2), "NB3", "green")
    with c5:
        kpi_card("QoS moyen", metric_value(kpi, "score_qos_moyen", decimals=3), "reseau")
        
    tab_map, tab_rank, tab_time = st.tabs(["Carte", "Stations critiques", "Evolution"])
    with tab_map:
        render_network_map(df)
    with tab_rank:
        scores = apply_station_criticite_filter(station_summary_from_df(df))
        if not scores.empty:
            fig = px.bar(scores.sort_values("score_criticite", ascending=False).head(20), x="station_id", y="score_criticite", color="categorie")
            st.plotly_chart(fig, width="stretch")
            st.dataframe(scores.sort_values("score_criticite", ascending=False), width="stretch", hide_index=True)
    with tab_time:
        render_time_evolution(df)
