import streamlit as st
from pathlib import Path
from services.data_service import init_db, load_outputs
from ui.layout import configure_page, sidebar, header
from ui.auth import login_page, force_password_change_page

# Import Admin Pages
from ui.pages.admin_network import admin_network_page
from ui.pages.admin_stations import admin_stations_page
from ui.pages.admin_anomalies import admin_anomalies_page
from ui.pages.admin_optimization import admin_optimization_page
from ui.pages.admin_alerts import admin_alerts_page
from ui.pages.admin_decisions import admin_decisions_page
from ui.pages.admin_models import admin_models_page
from ui.pages.admin_simulation import admin_simulation_page
from ui.pages.admin_admin import admin_admin_page
from ui.pages.operations import operations_page
from ui.pages.profile import profile_page

# Import Engineer Pages
from ui.pages.engineer_stations import engineer_my_stations_page
from ui.pages.engineer_monitoring import engineer_monitoring_page
from ui.pages.engineer_alerts import engineer_alerts_page
from ui.pages.engineer_actions import engineer_actions_page
from ui.pages.engineer_simulation import engineer_simulation_page

# Import helpers
from services.data_service import available_stations, engineer_assigned_stations, db_execute
from security.middleware import security_middleware

def main():
    configure_page()
    init_db()
    LOGO_PATH = Path("static/logo.png")
    
    # Enforce session and rate limits
    security_middleware.enforce()
    
    # Initialize session state for global data (thread-safe)
    if "data" not in st.session_state:
        with st.spinner("Chargement des artefacts NB1/NB2/NB3..."):
            st.session_state["data"] = load_outputs()
        
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        
    if not st.session_state["authenticated"]:
        login_page(LOGO_PATH)
        return
        
    if st.session_state.get("must_change_password"):
        force_password_change_page()
        return
        
    role = st.session_state.get("role")
    user_display = st.session_state.get("display", "")
    username = st.session_state.get("user", "")
    if st.session_state.get("session_id"):
        from datetime import datetime
        db_execute("touch_user_session", (datetime.now().isoformat(timespec="seconds"), st.session_state["session_id"]))
    
    # Navigation options
    if role == "admin":
        nav_options = [
            "Vue reseau", "Stations", "Anomalies NB2", "Alertes NB2", "Optimisation NB3", "Decisions NB3",
            "Modeles & Provenance", "Simulation reseau", "Centre operations", "Mon profil", "Administration"
        ]
        stations = []
    else:
        nav_options = [
            "Mes stations", "Monitoring station", "Alertes NB2",
            "Actions NB3", "Simulation station", "Mon profil"
        ]
        stations = engineer_assigned_stations(username)
        st.session_state["engineer_visible_stations"] = stations
        
    nav, selected_station = sidebar(role, user_display, username, LOGO_PATH, nav_options, stations)
    
    # Routing
    if role == "admin":
        if nav == "Vue reseau":
            admin_network_page()
        elif nav == "Stations":
            admin_stations_page()
        elif nav == "Anomalies NB2":
            admin_anomalies_page()
        elif nav == "Alertes NB2":
            admin_alerts_page()
        elif nav == "Optimisation NB3":
            admin_optimization_page()
        elif nav == "Decisions NB3":
            admin_decisions_page()
        elif nav == "Modeles & Provenance":
            admin_models_page()
        elif nav == "Simulation reseau":
            admin_simulation_page()
        elif nav == "Centre operations":
            operations_page()
        elif nav == "Mon profil":
            profile_page()
        elif nav == "Administration":
            admin_admin_page()
    else:
        if nav == "Mes stations":
            engineer_my_stations_page()
        elif nav == "Monitoring station":
            engineer_monitoring_page(selected_station)
        elif nav == "Alertes NB2":
            engineer_alerts_page(selected_station)
        elif nav == "Actions NB3":
            engineer_actions_page(selected_station)
        elif nav == "Simulation station":
            engineer_simulation_page(selected_station)
        elif nav == "Mon profil":
            profile_page()

if __name__ == "__main__":
    main()
