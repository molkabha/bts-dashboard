"""Common UI helpers and components."""

from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Optional

def render_empty_state(
    title: str = "Aucune donnée disponible",
    message: str = "Veuillez ajuster vos filtres ou vérifier l'importation des fichiers.",
    icon: str = "📊",
    type: str = "info"
):
    """Render a standardized empty state for pages."""
    st.markdown(f"### {icon} {title}")
    if type == "info":
        st.info(message)
    elif type == "warning":
        st.warning(message)
    elif type == "error":
        st.error(message)

def render_data_loading():
    """Context manager for data loading feedback."""
    return st.spinner("Chargement des données...")
