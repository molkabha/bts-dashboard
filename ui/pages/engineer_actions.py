import streamlit as st
import pandas as pd
from datetime import datetime
from security.middleware import security_middleware
from services.data_service import (
    load_outputs, engineer_assigned_stations, db_execute, db_read, log_event
)
from ui.layout import header, section
from ui.common import render_empty_state


def _latest_decision_overrides(station: str | None = None) -> pd.DataFrame:
    history = db_read("get_nb3_history", (station,)) if station else db_read(
        "select created_at, user, station_id, decision_ref, verdict, comment from nb3_validations order by id desc"
    )
    if history.empty:
        return pd.DataFrame(columns=["decision_ref", "statut_humain", "modifie_par", "modifie_le", "commentaire"])
    latest = history.drop_duplicates("decision_ref").copy()
    return latest.rename(
        columns={
            "verdict": "statut_humain",
            "user": "modifie_par",
            "created_at": "modifie_le",
            "comment": "commentaire",
        }
    )[["decision_ref", "statut_humain", "modifie_par", "modifie_le", "commentaire"]]


def engineer_actions_page(station: str | None = None):
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
    
    header("Decisions NB3", "Optimisations automatiques recommandees sur vos stations, avec modification humaine possible")
    
    if not station:
        st.warning("Veuillez selectionner une station.")
        return
        
    outputs = st.session_state.get("data", load_outputs())
    df_decisions = outputs.get("decisions", pd.DataFrame())
    if "station_id" not in df_decisions.columns:
        decisions = pd.DataFrame()
    elif station:
        decisions = df_decisions[df_decisions["station_id"].astype(str) == str(station)].copy()
    else:
        decisions = df_decisions.copy()
    
    if decisions.empty:
        render_empty_state(
            title="Aucune recommandation",
            message="Aucune recommandation NB3 disponible pour le perimetre selectionne."
        )
        return

    decisions["decision_ref"] = decisions.index.astype(str)
    decisions["statut_auto"] = "Appliquee automatiquement"
    overrides = _latest_decision_overrides(station)
    if not overrides.empty:
        decisions = decisions.merge(overrides, on="decision_ref", how="left")
    if "statut_humain" not in decisions.columns:
        decisions["statut_humain"] = pd.NA
    decisions["statut_humain"] = decisions["statut_humain"].fillna("Aucune modification")

    display_cols = [
        "decision_ref", "statut_auto", "statut_humain", "station_id", "heure",
        "mode_majoritaire", "mode_operation", "action_proposee", "action_rl",
        "economie_estimee_kwh", "economie_rl_kwh", "score_qos", "modifie_par", "modifie_le"
    ]
    display_cols = [c for c in display_cols if c in decisions.columns]
    st.dataframe(decisions[display_cols].head(500), width="stretch", hide_index=True)
    
    row_id = st.selectbox("Decision a modifier", decisions["decision_ref"].astype(str).tolist())
    selected_decision = decisions[decisions["decision_ref"].astype(str) == str(row_id)]
    if selected_decision.empty:
        selected_decision = decisions.head(1)
    decision = selected_decision.iloc[0]
    station_id = str(decision.get("station_id", station or ""))
    
    decision_table = decision.astype(str).reset_index()
    decision_table.columns = ["champ", "valeur"]
    st.dataframe(decision_table, width="stretch", hide_index=True)
    
    verdict = st.radio(
        "Modification humaine",
        ["Appliquer maintenant", "Modifier", "Rejeter", "Reporter", "Escalader"],
        horizontal=True,
    )
    custom_action = ""
    if verdict == "Modifier":
        custom_action = st.text_input("Nouvelle action / decision", value=str(decision.get("action_rl", decision.get("action_proposee", ""))))
    comment = st.text_area("Commentaire operationnel")
    stored_comment = f"Nouvelle action: {custom_action}\n{comment}".strip() if custom_action else comment
    
    if st.button("Enregistrer modification NB3", type="primary"):
        db_execute(
            "insert_nb3_validation",
            (datetime.now().isoformat(timespec="seconds"), st.session_state.get("user", ""), station_id, str(row_id), verdict, stored_comment),
        )
        log_event("nb3_override", {"station_id": station_id, "decision_ref": str(row_id), "verdict": verdict})
        st.success("Modification NB3 enregistree. Sans modification, la decision reste appliquee automatiquement.")
        
    history = db_read("get_nb3_history", (station,)) if station else db_read(
        "select created_at, user, station_id, decision_ref, verdict, comment from nb3_validations order by id desc limit 100"
    )
    if not history.empty:
        section("Historique modifications")
        st.dataframe(history, width="stretch", hide_index=True)
