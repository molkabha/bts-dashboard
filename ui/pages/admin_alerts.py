import streamlit as st
import pandas as pd
from datetime import datetime
from security.middleware import security_middleware
from services.data_service import (
    load_top_anomalies, apply_admin_dimension_filters, apply_time_filters, db_execute, db_read, log_event
)
from ui.layout import header, section
from ui.components_filters import render_admin_global_filters


def _latest_alert_overrides() -> pd.DataFrame:
    """Get latest alert overrides across all stations for admin view."""
    history = db_read(
        "select created_at, user, station_id, alert_ref, verdict, comment from alert_decisions order by id desc"
    )
    if history.empty:
        return pd.DataFrame(columns=["alert_ref", "statut_humain", "modifie_par", "modifie_le", "station_id", "commentaire"])
    latest = history.drop_duplicates("alert_ref").copy()
    return latest.rename(
        columns={
            "verdict": "statut_humain",
            "user": "modifie_par",
            "created_at": "modifie_le",
            "comment": "commentaire",
        }
    )[["alert_ref", "statut_humain", "modifie_par", "modifie_le", "station_id", "commentaire"]]


def admin_alerts_page():
    """Admin view: Supervise all anomaly alerts across network."""
    security_middleware.enforce()
    role = st.session_state.get("role")
    if role != "admin":
        st.error("Acces refuse. Cette page est reservee aux administrateurs.")
        return
        
    header("Alertes NB2 - Vue reseau", "Supervision de toutes les anomalies detectees, modifications globales par admin")
    
    with st.spinner("Lecture des anomalies reseau..."):
        df_raw = load_top_anomalies(2000)
        
        # Display filter UI
        render_admin_global_filters(df_raw)
        
        df = apply_admin_dimension_filters(df_raw)
        
        filters = st.session_state.get("admin_time_filters", {})
        if filters:
            df = apply_time_filters(df, {
                "date_range": filters.get("date_range"),
                "hours": filters.get("hours"),
                "months": None, "day_type": "Tous", "days": None
            })
            
    if df.empty:
        st.warning("Aucune anomalie disponible.")
        return
        
    score_col = "anomalie_score_ensemble"
    if score_col in df.columns:
        df = df.sort_values(score_col, ascending=False)

    df = df.copy()
    df["alert_ref"] = df.index.astype(str)
    df["statut_auto"] = "Alerte active automatiquement"
    overrides = _latest_alert_overrides()
    if not overrides.empty:
        df = df.merge(overrides, on="alert_ref", how="left")
    if "statut_humain" not in df.columns:
        df["statut_humain"] = pd.NA
    df["statut_humain"] = df["statut_humain"].fillna("Aucune modification")

    # Display filters
    c1, c2, c3 = st.columns(3)
    with c1:
        stations = sorted(df["station_id"].dropna().unique()) if "station_id" in df.columns else []
        sel_stations = st.multiselect("Filtrer stations", stations, default=stations[:30])
    with c2:
        techs = sorted(df["technologie"].dropna().unique()) if "technologie" in df.columns else []
        sel_techs = st.multiselect("Filtrer technologies", techs, default=techs)
    with c3:
        min_score = st.slider("Score anomalie minimum", 0.0, 1.0, 0.3, 0.01)
        
    if sel_stations and "station_id" in df.columns:
        df = df[df["station_id"].isin(sel_stations)]
    if sel_techs and "technologie" in df.columns:
        df = df[df["technologie"].isin(sel_techs)]
    if "anomalie_score_ensemble" in df.columns:
        df = df[df["anomalie_score_ensemble"] >= min_score]

    display_cols = [
        "alert_ref", "statut_auto", "statut_humain", "station_id", "timestamp",
        "technologie", "anomalie_score_ensemble", "nb_votes_anomalie",
        "niveau_anomalie", "type_anomalie", "score_qos", "modifie_par", "modifie_le"
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols].head(500), width="stretch", hide_index=True)
    
    st.divider()
    st.subheader("Modifier une alerte")
    
    selected = st.selectbox("Alerte a modifier", df["alert_ref"].astype(str).tolist())
    selected_alert = df[df["alert_ref"].astype(str) == str(selected)]
    if selected_alert.empty:
        selected_alert = df.head(1)
    alert = selected_alert.iloc[0]
    station_id = str(alert.get("station_id", ""))
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Station:** {station_id} | **Tech:** {alert.get('technologie', 'N/A')} | **Score:** {alert.get('anomalie_score_ensemble', 'N/A')}")
    
    action = st.radio(
        "Modification humaine",
        ["Traiter maintenant", "Modifier", "Rejeter faux positif", "Escalader NOC", "En investigation"],
        horizontal=True,
    )
    custom_alert = ""
    if action == "Modifier":
        custom_alert = st.text_input("Nouvelle alerte / consigne", value=str(alert.get("type_anomalie", "")))
    comment = st.text_area("Commentaire", key="admin_alert_comment")
    stored_comment = f"Nouvelle alerte: {custom_alert}\n{comment}".strip() if custom_alert else comment
    
    if st.button("Enregistrer modification admin", type="primary"):
        db_execute(
            "insert_alert_decision",
            (datetime.now().isoformat(timespec="seconds"), st.session_state.get("user", ""), station_id, selected, action, stored_comment),
        )
        log_event("admin_alert_override", {"station_id": station_id, "alert_ref": selected, "verdict": action, "user": st.session_state.get("user", "")})
        st.success("Modification enregistree par admin.")
        
    st.divider()
    section("Historique modifications (top 100)")
    history = db_read(
        "select created_at, user, station_id, alert_ref, verdict, comment from alert_decisions order by id desc limit 100"
    )
    if not history.empty:
        st.dataframe(history, width="stretch", hide_index=True)
