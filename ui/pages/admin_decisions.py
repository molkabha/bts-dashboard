import streamlit as st
import pandas as pd
from datetime import datetime
from security.middleware import security_middleware
from services.data_service import (
    load_outputs, apply_admin_dimension_filters, apply_time_filters, db_execute, db_read, log_event
)
from ui.layout import header, section
from ui.components_filters import render_admin_global_filters
from ui.common import render_empty_state


def _latest_decision_overrides() -> pd.DataFrame:
    """Get latest decision overrides across all stations for admin view."""
    history = db_read(
        "select created_at, user, station_id, decision_ref, verdict, comment from nb3_validations order by id desc"
    )
    if history.empty:
        return pd.DataFrame(columns=["decision_ref", "statut_humain", "modifie_par", "modifie_le", "station_id", "commentaire"])
    latest = history.drop_duplicates("decision_ref").copy()
    return latest.rename(
        columns={
            "verdict": "statut_humain",
            "user": "modifie_par",
            "created_at": "modifie_le",
            "comment": "commentaire",
        }
    )[["decision_ref", "statut_humain", "modifie_par", "modifie_le", "station_id", "commentaire"]]


def admin_decisions_page():
    """Admin view: Supervise and approve all optimization decisions (NB3) across network."""
    security_middleware.enforce()
    role = st.session_state.get("role")
    if role != "admin":
        st.error("Acces refuse. Cette page est reservee aux administrateurs.")
        return
        
    header("Decisions NB3 - Vue reseau", "Supervision des optimisations energetiques, approbations globales par admin")
    
    outputs = st.session_state.get("data", load_outputs())
    df_decisions = outputs.get("decisions", pd.DataFrame())
    
    if df_decisions.empty:
        render_empty_state(
            title="Aucune recommandation",
            message="Aucune recommandation NB3 disponible."
        )
        return

    # Display filter UI
    render_admin_global_filters(df_decisions)
    
    # Apply admin filters
    decisions = apply_admin_dimension_filters(df_decisions.copy())
    filters = st.session_state.get("admin_time_filters", {})
    if filters:
        decisions = apply_time_filters(decisions, {
            "date_range": filters.get("date_range"),
            "hours": filters.get("hours"),
            "months": None, "day_type": "Tous", "days": None
        })
    
    if decisions.empty:
        render_empty_state(
            title="Aucune recommandation apres filtres",
            message="Aucune recommandation NB3 pour les criteres selectionnes."
        )
        return

    decisions["decision_ref"] = decisions.index.astype(str)
    decisions["statut_auto"] = "Appliquee automatiquement"
    overrides = _latest_decision_overrides()
    if not overrides.empty:
        decisions = decisions.merge(overrides, on="decision_ref", how="left")
    if "statut_humain" not in decisions.columns:
        decisions["statut_humain"] = pd.NA
    decisions["statut_humain"] = decisions["statut_humain"].fillna("Aucune modification")

    # Display filters
    c1, c2, c3 = st.columns(3)
    with c1:
        stations = sorted(decisions["station_id"].dropna().unique()) if "station_id" in decisions.columns else []
        sel_stations = st.multiselect("Filtrer stations", stations, default=stations[:30])
    with c2:
        actions_list = sorted(decisions["action_rl"].dropna().unique()) if "action_rl" in decisions.columns else []
        sel_actions = st.multiselect("Filtrer actions", actions_list[:20], default=actions_list[:10])
    with c3:
        min_eco = st.number_input("Economie min (kWh)", 0, 10000, 10, 100)
        
    if sel_stations and "station_id" in decisions.columns:
        decisions = decisions[decisions["station_id"].isin(sel_stations)]
    if sel_actions and "action_rl" in decisions.columns:
        decisions = decisions[decisions["action_rl"].isin(sel_actions)]
    if "economie_rl_kwh" in decisions.columns:
        decisions = decisions[decisions["economie_rl_kwh"] >= min_eco]

    display_cols = [
        "decision_ref", "statut_auto", "statut_humain", "station_id", "heure",
        "mode_majoritaire", "mode_operation", "action_proposee", "action_rl",
        "economie_estimee_kwh", "economie_rl_kwh", "score_qos", "modifie_par", "modifie_le"
    ]
    display_cols = [c for c in display_cols if c in decisions.columns]
    
    st.subheader(f"Decisions NB3 ({len(decisions)} total)")
    st.dataframe(decisions[display_cols].head(500), width="stretch", hide_index=True)
    
    st.divider()
    st.subheader("Modifier une decision")
    
    row_id = st.selectbox("Decision a modifier", decisions["decision_ref"].astype(str).tolist())
    selected_decision = decisions[decisions["decision_ref"].astype(str) == str(row_id)]
    if selected_decision.empty:
        selected_decision = decisions.head(1)
    decision = selected_decision.iloc[0]
    station_id = str(decision.get("station_id", ""))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Station", station_id)
    with col2:
        st.metric("Economie RL (kWh)", f"{decision.get('economie_rl_kwh', 0):,.0f}")
    with col3:
        st.metric("Score QoS", f"{decision.get('score_qos', 0):.2f}")
    
    decision_table = decision.astype(str).reset_index()
    decision_table.columns = ["champ", "valeur"]
    st.dataframe(decision_table, width="stretch", hide_index=True)
    
    verdict = st.radio(
        "Modification humaine par admin",
        ["Appliquer maintenant", "Modifier", "Rejeter", "Reporter", "Escalader"],
        horizontal=True,
    )
    custom_action = ""
    if verdict == "Modifier":
        custom_action = st.text_input("Nouvelle action / decision", value=str(decision.get("action_rl", decision.get("action_proposee", ""))))
    comment = st.text_area("Commentaire admin", placeholder="Ex: Rejete - coherence avec contrainte operationnelle")
    stored_comment = f"Nouvelle action: {custom_action}\n{comment}".strip() if custom_action else comment
    
    if st.button("Enregistrer modification admin NB3", type="primary"):
        db_execute(
            "insert_nb3_validation",
            (datetime.now().isoformat(timespec="seconds"), st.session_state.get("user", ""), station_id, str(row_id), verdict, stored_comment),
        )
        log_event("admin_nb3_override", {"station_id": station_id, "decision_ref": str(row_id), "verdict": verdict, "user": st.session_state.get("user", "")})
        st.success("Modification NB3 enregistree par admin. L'application est suspendue en attente d'analyse.")
        
    st.divider()
    section("Historique modifications (top 100)")
    history = db_read(
        "select created_at, user, station_id, decision_ref, verdict, comment from nb3_validations order by id desc limit 100"
    )
    if not history.empty:
        st.dataframe(history, width="stretch", hide_index=True)
