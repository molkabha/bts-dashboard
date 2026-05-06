import streamlit as st
import pandas as pd
from security.middleware import security_middleware
from services.data_service import (
    station_summary_from_df, load_outputs, engineer_assigned_stations
)
from ui.layout import header, kpi_card, section
from ui.utils import download_df_button

def engineer_my_stations_page():
    security_middleware.enforce()
    header("Mes stations", "Priorites operationnelles des stations assignees")
    
    assigned = engineer_assigned_stations()
    if not assigned:
        st.warning("Aucune station assignee.")
        return
        
    outputs = st.session_state.get("data", load_outputs())
    df_scores = outputs.get("scores", pd.DataFrame())
    
    if df_scores.empty:
        st.warning("Aucune donnee de score disponible.")
        return
        
    # Filter scores for assigned stations
    my_scores = df_scores[df_scores["station_id"].astype(str).isin(assigned)].copy()
    
    if my_scores.empty:
        st.warning("Aucune donnee disponible pour vos stations assignees.")
        return
        
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Stations", str(len(my_scores)), "assignees")
    with c2:
        critical = int((my_scores.get("categorie", pd.Series()).astype(str) == "Critique").sum()) if "categorie" in my_scores.columns else 0
        kpi_card("Critiques", str(critical), "a prioriser", "red" if critical else "green")
    with c3:
        qos_val = my_scores['score_qos_moy'].mean() if 'score_qos_moy' in my_scores.columns else 0
        kpi_card("QoS moyen", f"{qos_val:.3f}", "stations")
        
    section("File de travail")
    decisions = outputs.get("decisions", pd.DataFrame())
    if isinstance(decisions, pd.DataFrame) and not decisions.empty:
        queue = decisions[decisions["station_id"].astype(str).isin(assigned)].copy()
        queue["decision_ref"] = queue.index.astype(str)
        queue["statut_auto"] = "Appliquee automatiquement"
        st.dataframe(queue.head(50), width="stretch", hide_index=True)
        
    section("Inventaire de mes stations")
    st.dataframe(my_scores.sort_values("score_criticite", ascending=False), width="stretch", hide_index=True)
    download_df_button(my_scores, "mes_stations_assignees.csv")
