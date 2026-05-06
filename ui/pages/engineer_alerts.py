import streamlit as st
import pandas as pd
from datetime import datetime
from security.middleware import security_middleware
from services.data_service import (
    load_station_anomalies, engineer_assigned_stations, db_execute, db_read, log_event
)
from ui.layout import header, section


def _latest_alert_overrides(station: str | None = None) -> pd.DataFrame:
    history = db_read("get_alert_history", (station,)) if station else db_read(
        "select created_at, user, station_id, alert_ref, verdict, comment from alert_decisions order by id desc"
    )
    if history.empty:
        return pd.DataFrame(columns=["alert_ref", "statut_humain", "modifie_par", "modifie_le", "commentaire"])
    latest = history.drop_duplicates("alert_ref").copy()
    return latest.rename(
        columns={
            "verdict": "statut_humain",
            "user": "modifie_par",
            "created_at": "modifie_le",
            "comment": "commentaire",
        }
    )[["alert_ref", "statut_humain", "modifie_par", "modifie_le", "commentaire"]]


def engineer_alerts_page(station: str | None = None):
    security_middleware.enforce()
    role = st.session_state.get("role")
    if role != "engineer":
        st.error("Acces refuse. Cette page est reservee aux engineers.")
        return
    
    # Verify engineer is assigned to this station
    if station:
        assigned_stations = engineer_assigned_stations(st.session_state.get("user", ""))
        if station not in assigned_stations:
            st.error(f"Vous n'avez pas acces a la station {station}. Stations assignees: {', '.join(assigned_stations)}")
            return
    
    header("Alertes NB2", "Alertes automatiques actives sur vos stations, avec modification humaine possible")
    
    if not station:
        st.warning("Veuillez selectionner une station.")
        return
    
    with st.spinner("Lecture des anomalies..."):
        df = load_station_anomalies(station)
            
    if df.empty:
        st.warning("Aucune anomalie disponible pour cette station.")
        return
        
    score_col = "anomalie_score_ensemble"
    if score_col in df.columns:
        df = df.sort_values(score_col, ascending=False)

    df = df.copy()
    df["alert_ref"] = df.index.astype(str)
    df["statut_auto"] = "Alerte active automatiquement"
    overrides = _latest_alert_overrides(station)
    if not overrides.empty:
        df = df.merge(overrides, on="alert_ref", how="left")
    if "statut_humain" not in df.columns:
        df["statut_humain"] = pd.NA
    df["statut_humain"] = df["statut_humain"].fillna("Aucune modification")

    display_cols = [
        "alert_ref", "statut_auto", "statut_humain", "station_id", "timestamp",
        "technologie", "anomalie_score_ensemble", "nb_votes_anomalie",
        "niveau_anomalie", "type_anomalie", "score_qos", "modifie_par", "modifie_le"
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols].head(500), width="stretch", hide_index=True)
    
    selected = st.selectbox("Alerte a modifier", df["alert_ref"].astype(str).tolist())
    selected_alert = df[df["alert_ref"].astype(str) == str(selected)]
    if selected_alert.empty:
        selected_alert = df.head(1)
    alert = selected_alert.iloc[0]
    station_id = str(alert.get("station_id", station or ""))
    action = st.radio(
        "Modification humaine",
        ["Traiter maintenant", "Modifier", "Rejeter faux positif", "Escalader NOC", "En investigation"],
        horizontal=True,
    )
    custom_alert = ""
    if action == "Modifier":
        custom_alert = st.text_input("Nouvelle alerte / consigne", value=str(alert.get("type_anomalie", "")))
    comment = st.text_area("Commentaire", key=f"alert_comment_{station or 'admin'}")
    stored_comment = f"Nouvelle alerte: {custom_alert}\n{comment}".strip() if custom_alert else comment
    
    if st.button("Enregistrer modification", type="primary"):
        db_execute(
            "insert_alert_decision",
            (datetime.now().isoformat(timespec="seconds"), st.session_state.get("user", ""), station_id, selected, action, stored_comment),
        )
        log_event("alert_override", {"station_id": station_id, "alert_ref": selected, "verdict": action})
        st.success("Modification enregistree. Sans modification, l'alerte reste active automatiquement.")
        
    history = db_read("get_alert_history", (station,)) if station else db_read(
        "select created_at, user, station_id, alert_ref, verdict, comment from alert_decisions order by id desc limit 100"
    )
    if not history.empty:
        section("Historique modifications")
        st.dataframe(history, width="stretch", hide_index=True)
