"""Reusable Streamlit widgets and UI components."""

from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st


@st.cache_data(ttl=3600, show_spinner=False)
def image_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        suffix = path.suffix.lower().lstrip(".") or "png"
        return f"data:image/{suffix};base64,{encoded}"
    except Exception:
        return ""


def kpi_card(label: str, value: str, help_text: str = "", color: str = ""):
    """Render a stylized KPI card."""
    safe_label = html.escape(label)
    safe_value = html.escape(value)
    safe_help = html.escape(help_text)
    safe_color = html.escape(color)
    
    st.markdown(
        f"""
<div class="kpi {safe_color}">
  <div class="kpi-label">{safe_label}</div>
  <div class="kpi-value">{safe_value}</div>
  <div class="kpi-help">{safe_help}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def section(title: str):
    """Render a section header and return a container context."""
    safe_title = html.escape(title)
    st.markdown(f'<div class="section">{safe_title}</div>', unsafe_allow_html=True)
    return st.container()


def header(title: str, subtitle: str, logo_path: Path | None = None):
    """Render the top bar/header."""
    role = st.session_state.get("role")
    display = "Administrateur" if role == "admin" else "Ingenieur reseau" if role == "engineer" else "Connexion"
    cls = "admin" if role == "admin" else ""
    
    safe_title = html.escape(title)
    safe_subtitle = html.escape(subtitle)
    safe_display = html.escape(display)
    safe_cls = html.escape(cls)
    
    logo_html = ""
    if logo_path:
        logo = image_data_uri(logo_path)
        if logo:
            logo_html = f'<img class="topbar-logo" src="{logo}" alt="Tunisie Telecom">'
            
    st.markdown(
        f"""
<div class="topbar">
  {logo_html}
  <div class="topbar-content">
    <div class="brand">Tunisie Telecom - BTS Energy Management</div>
    <div class="title">{safe_title}</div>
    <div class="subtitle">{safe_subtitle}</div>
    <div style="margin-top:8px;"><span class="role-pill {safe_cls}">{safe_display}</span></div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


import time

def sidebar(role: str, display: str, user: str, logo_path: Path | None = None, nav_options: list = [], station_options: list = []):
    """Render the sidebar navigation."""
    if logo_path and logo_path.exists():
        st.sidebar.image(str(logo_path), width=130)
    
    st.sidebar.markdown(f"**{html.escape(display)}**")
    st.sidebar.caption(html.escape(user))
    
    # Session time indicator
    if "_session_start" in st.session_state:
        elapsed = time.time() - st.session_state["_session_start"]
        remaining = max(0, 3600 - int(elapsed))
        mins = remaining // 60
        st.sidebar.caption(f"⏱ Session expire dans {mins} min")
        
    st.sidebar.divider()
    
    nav = None
    station = None
    
    if role == "admin":
        nav = st.sidebar.radio("Navigation Admin", nav_options)
    else:
        nav = st.sidebar.radio("Navigation Ingenieur", nav_options)
        station = st.sidebar.selectbox("Station assignee", station_options, disabled=not station_options)
    
    st.sidebar.divider()
    if st.sidebar.button("Deconnexion", width="stretch"):
        try:
            from datetime import datetime
            from services.data_service import db_execute
            session_id = st.session_state.get("session_id")
            if session_id:
                db_execute("end_user_session", (datetime.now().isoformat(timespec="seconds"), session_id))
        except Exception:
            pass
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
        
    return nav, station
