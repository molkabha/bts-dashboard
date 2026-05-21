"""Common UI helpers and components."""

from __future__ import annotations

import streamlit as st


def render_empty_state(
    title: str = "Aucune donnee disponible",
    message: str = "Veuillez ajuster vos filtres ou verifier l'importation des fichiers.",
    type: str = "info",
):
    """Render a standardized empty state for pages."""
    st.markdown(f"### {title}")
    if type == "warning":
        st.warning(message)
    elif type == "error":
        st.error(message)
    else:
        st.info(message)


def render_data_loading():
    """Context manager for data loading feedback."""
    return st.spinner("Chargement des donnees...")
