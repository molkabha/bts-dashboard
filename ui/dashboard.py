"""Main dashboard router."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from security.middleware import security_middleware
from services.data_service import (
    available_stations,
    db_execute,
    engineer_assigned_stations,
    init_db,
    load_outputs,
)
from ui.layout import configure_page
from ui.auth import login_page, force_password_change_page
from ui.components import sidebar_global, page_footer
from ui.page_helpers import fleet_status_metrics, load_dashboard_df

from views.p0_accueil import page_accueil
from views.p1_vue_reseau import page_vue_reseau
from views.p2_prediction import page_prediction
from views.p3_anomalies import page_anomalies
from views.p4_decision import page_decision
from views.p4_optimisation_rl import page_optimisation_rl
from views.p5_agents_rl import page_agents_rl
from views.p5_simulation import page_simulation
from views.p7_monitoring import page_monitoring
from views.p8_station import page_station_detail
from views.p9_rapport import page_rapport
from views.p10_comparaison import page_comparaison
from views.p6_upload_admin import page_upload_admin
from views.p7_configuration import page_configuration
from views.p8_utilisateurs import page_utilisateurs

PAGE_FUNCTIONS = {
    0: page_accueil,
    1: page_vue_reseau,
    2: page_prediction,
    3: page_anomalies,
    4: page_decision,
    5: page_agents_rl,
    6: page_simulation,
    14: page_optimisation_rl,
    7: page_monitoring,
    8: page_station_detail,
    9: page_rapport,
    10: page_comparaison,
    11: page_upload_admin,
    12: page_configuration,
    13: page_utilisateurs,
}


def _default_home_page(role: str) -> int:
    return 0 if role == "admin" else 7


def main():
    configure_page()
    init_db()
    logo_path = Path("static/logo.png")

    security_middleware.enforce()

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        login_page(logo_path)
        return

    if st.session_state.get("must_change_password"):
        force_password_change_page()
        return

    if "data" not in st.session_state:
        with st.spinner("Chargement des artefacts NB1/NB2/NB3..."):
            st.session_state["data"] = load_outputs()

    role = st.session_state.get("role")
    user_display = st.session_state.get("display", "")
    username = st.session_state.get("user", "")

    if st.session_state.get("session_id"):
        db_execute(
            "touch_user_session",
            (datetime.now().isoformat(timespec="seconds"), st.session_state["session_id"]),
        )

    if role == "admin":
        stations = available_stations()
    else:
        stations = engineer_assigned_stations(username)
        st.session_state["engineer_visible_stations"] = stations

    nav_override = st.session_state.pop("_nav_override", None)

    page_index, filters = sidebar_global(role, user_display, username, logo_path, stations)

    if nav_override is not None:
        page_index = nav_override

    # Redirect to role home on first load
    if st.session_state.pop("_goto_home", False):
        page_index = _default_home_page(role)

    st.session_state["global_filters"] = filters

    page_fn = PAGE_FUNCTIONS.get(page_index, PAGE_FUNCTIONS[_default_home_page(role)])
    if page_index not in {13, 11, 12}:
        _df = load_dashboard_df()
        st.session_state["_dashboard_df"] = _df
        st.session_state["_fleet_metrics"] = fleet_status_metrics(_df)
    else:
        st.session_state.pop("_dashboard_df", None)
        st.session_state.pop("_fleet_metrics", None)
    page_fn()
    page_footer()


if __name__ == "__main__":
    main()
