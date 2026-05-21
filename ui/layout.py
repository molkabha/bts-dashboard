"""Layout helpers and style injection."""

from __future__ import annotations

import streamlit as st
from config.theme import APP_CSS, DARK_CSS


def configure_page():
    """Inject global CSS after app.py has configured the Streamlit page."""
    st.markdown(APP_CSS, unsafe_allow_html=True)
    if st.session_state.get("ui_dark_mode"):
        st.markdown(DARK_CSS, unsafe_allow_html=True)
