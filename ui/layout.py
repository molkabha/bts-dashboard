"""Layout helpers and style injection."""

from __future__ import annotations

import streamlit as st
from config.theme import APP_CSS
from ui.components import (
    header,
    image_data_uri,
    kpi_card,
    section,
    sidebar,
)

def configure_page():
    """Configure Streamlit page and inject global CSS."""
    st.set_page_config(
        page_title="BTS EMS - Tunisie Telecom",
        page_icon="TT",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(APP_CSS, unsafe_allow_html=True)
