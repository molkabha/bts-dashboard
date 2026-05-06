import streamlit as st
import pandas as pd
import plotly.express as px
from security.middleware import security_middleware
from services.data_service import (
    load_filtered_main_data, apply_admin_dimension_filters, apply_time_filters, load_outputs
)
from ui.layout import header, kpi_card
from ui.components_filters import render_admin_global_filters
from ui.utils import download_df_button

def comparison_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "consommation_kwh" not in df.columns:
        return pd.DataFrame()
    before = df["consommation_kwh"].sum()
    expert_savings = df["economie_estimee_kwh"].fillna(0).sum() if "economie_estimee_kwh" in df.columns else 0
    rl_savings = df["economie_rl_kwh"].fillna(0).sum() if "economie_rl_kwh" in df.columns else 0
    rows = [
        {"scenario": "Avant optimisation", "consommation_kwh": before, "economie_kwh": 0.0, "economie_pct": 0.0},
        {
            "scenario": "Apres optimisation experte",
            "consommation_kwh": max(before - expert_savings, 0),
            "economie_kwh": expert_savings,
            "economie_pct": expert_savings / before * 100 if before else 0,
        },
        {
            "scenario": "Apres optimisation RL",
            "consommation_kwh": max(before - rl_savings, 0),
            "economie_kwh": rl_savings,
            "economie_pct": rl_savings / before * 100 if before else 0,
        },
    ]
    return pd.DataFrame(rows)

def admin_optimization_page():
    security_middleware.enforce()
    header("Optimisation NB3", "Avant/apres, actions et agents RL")
    
    cols = [
        "timestamp", "station_id", "consommation_kwh", "economie_estimee_kwh", "economie_rl_kwh",
        "action_rl", "action_proposee", "score_qos", "gouvernorat", "type_zone", "technologie", "categorie", "anomalie_score_ensemble"
    ]
    
    df_raw = load_filtered_main_data(cols)
    
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
        st.warning("Aucune donnee disponible pour les filtres selectionnes.")
        return
        
    tab_compare, tab_actions, tab_agents = st.tabs(["Avant apres", "Actions", "Agents RL"])
    
    with tab_compare:
        comp = comparison_frame(df)
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Avant", f"{comp.iloc[0]['consommation_kwh']:,.0f} kWh", "brut")
        with c2:
            kpi_card("Apres expert", f"{comp.iloc[1]['consommation_kwh']:,.0f} kWh", f"-{comp.iloc[1]['economie_pct']:.2f}%", "green")
        with c3:
            kpi_card("Apres RL", f"{comp.iloc[2]['consommation_kwh']:,.0f} kWh", f"-{comp.iloc[2]['economie_pct']:.2f}%", "green")
            
        fig = px.bar(comp, x="scenario", y="consommation_kwh", color="scenario")
        fig.update_layout(showlegend=False, yaxis_title="kWh", xaxis_title="")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(comp, width="stretch", hide_index=True)
        download_df_button(comp, "comparaison_avant_apres.csv", "Exporter comparaison")
        
    with tab_actions:
        action_col = "action_rl" if "action_rl" in df.columns else "action_proposee"
        if action_col in df.columns:
            actions = df.groupby(action_col, as_index=False).agg(
                nb_mesures=(action_col, "size"),
                economie_rl_kwh=("economie_rl_kwh", "sum") if "economie_rl_kwh" in df.columns else ("economie_rl_kwh", "size"), # Fallback
                conso_moy=("consommation_kwh", "mean") if "consommation_kwh" in df.columns else ("consommation_kwh", "size"), # Fallback
                score_qos_moy=("score_qos", "mean") if "score_qos" in df.columns else ("score_qos", "size"), # Fallback
            )
            fig = px.bar(actions.sort_values("economie_rl_kwh", ascending=False), x=action_col, y="economie_rl_kwh", color="score_qos_moy")
            st.plotly_chart(fig, width="stretch")
            st.dataframe(actions.sort_values("economie_rl_kwh", ascending=False), width="stretch", hide_index=True)
            download_df_button(actions, "actions_nb3_filtrees.csv", "Exporter actions")
        else:
            st.info("Donnees d'actions non disponibles.")
            
    with tab_agents:
        outputs = st.session_state.get("data", load_outputs())
        nb3 = outputs.get("nb3", {})
        rl = nb3.get("rl_resultats_tous_agents", {})
        if rl:
            df_rl = pd.DataFrame.from_dict(rl, orient="index").reset_index(names="agent")
            fig = px.bar(df_rl.sort_values("economie_pct", ascending=False), x="agent", y="economie_pct", color="pct_violations")
            st.plotly_chart(fig, width="stretch")
            st.dataframe(df_rl.sort_values("economie_pct", ascending=False), width="stretch", hide_index=True)
        else:
            st.info("Donnees agents RL non disponibles.")
