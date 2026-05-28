from __future__ import annotations

import base64

import html

import time

from datetime import datetime

from pathlib import Path

import streamlit as st

from ui.display import (
    ADMIN_PAGE_INDEX,
    ADMIN_PAGE_LABELS,
    ENGINEER_PAGE_INDEX,
    ENGINEER_PAGE_LABELS,
)


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


def kpi_card(
    label: str,
    value: str,
    help_text: str = "",
    color: str = "",
    delta: str = "",
    delta_class: str = "",
):

    from ui.formatting import sanitize_kpi_value

    safe_label = html.escape(label)

    safe_value = html.escape(sanitize_kpi_value(value))

    safe_help = html.escape(sanitize_kpi_value(help_text, default=""))

    safe_color = html.escape(color)

    delta_html = (
        f'<div class="kpi-delta {delta_class}">{html.escape(delta)}</div>'
        if delta
        else ""
    )

    st.markdown(
        f'\n<div class="kpi {safe_color}">\n  <div class="kpi-row"><div class="kpi-label">{safe_label}</div></div>\n  <div class="kpi-value">{safe_value}</div>\n  <div class="kpi-row">\n    <div class="kpi-help">{safe_help}</div>\n    {delta_html}\n  </div>\n</div>\n',
        unsafe_allow_html=True,
    )


def status_badge(label: str, status_type: str = "info"):

    from config.theme import MODE_COLORS, mode_badge_css, normalize_mode_key

    css_map = {
        "success": "badge-normal",
        "warning": "badge-warning",
        "error": "badge-critical",
        "eco": "badge-eco",
        "info": "badge-info",
    }

    if normalize_mode_key(label) in MODE_COLORS:

        css_class = mode_badge_css(label)

    else:

        css_class = css_map.get(status_type, "badge-muted")

    st.markdown(
        f'<span class="badge {css_class}">{html.escape(label)}</span>',
        unsafe_allow_html=True,
    )


def alert_banner(title: str, body: str, style: str = "info", meta: str = ""):

    meta_html = f'<div class="alert-meta">{html.escape(meta)}</div>' if meta else ""

    st.markdown(
        f'\n<div class="alert {style}">\n  <div style="flex:1">\n    <div class="alert-title">{html.escape(title)}</div>\n    <div class="alert-body">{html.escape(body)}</div>\n    {meta_html}\n  </div>\n</div>\n',
        unsafe_allow_html=True,
    )


def context_badge(label: str, value: str, tone: str = "info"):

    st.markdown(
        f'\n<div class="context-badge {html.escape(tone)}">\n  <span>{html.escape(label)}</span>\n  <strong>{html.escape(value)}</strong>\n</div>\n',
        unsafe_allow_html=True,
    )


def section(title: str):

    st.markdown(
        f'<div class="section">{html.escape(title)}</div>', unsafe_allow_html=True
    )

    return st.container()


def page_footer():

    from config.settings import settings

    ds_label = (
        f"Artefacts {settings.HF_REPO_ID}"
        if settings.USE_HF_HUB
        else "Jeu de données notebook"
    )

    st.markdown(
        f'<div class="page-footer">{html.escape(ds_label)} · Tunisie Telecom</div>',
        unsafe_allow_html=True,
    )


def header(title: str, subtitle: str, logo_path: Path | None = None):

    if logo_path is None:

        logo_path = Path("static/logo.png")

    logo_html = ""

    if logo_path:

        logo = image_data_uri(logo_path)

        if logo:

            logo_html = f'<img class="topbar-logo" src="{logo}" alt="Tunisie Telecom">'

    st.markdown(
        f'\n<div class="topbar">\n  {logo_html}\n  <div class="topbar-content">\n    <div class="brand">Tunisie Telecom — Gestion énergétique BTS</div>\n    <div class="title">{html.escape(title)}</div>\n    <div class="subtitle">{html.escape(subtitle)}</div>\n  </div>\n</div>\n',
        unsafe_allow_html=True,
    )


def sidebar_global(
    role: str,
    display: str,
    username: str,
    logo_path: Path | None = None,
    station_options: list | None = None,
) -> tuple[int, dict]:

    station_options = station_options or []

    initials = "".join([n[0] for n in display.split()[:2]]).upper() if display else "?"

    is_admin = role == "admin"

    badge_cls = "role-badge-admin" if is_admin else "role-badge-engineer"

    badge_text = "ADMINISTRATEUR" if is_admin else "INGÉNIEUR RÉSEAU"

    st.sidebar.markdown(
        f'\n<div class="sb-user">\n  <div class="sb-avatar">{html.escape(initials)}</div>\n  <div>\n    <div class="sb-name">{html.escape(display)}</div>\n    <span class="role-badge {badge_cls}">{badge_text}</span>\n  </div>\n</div>\n',
        unsafe_allow_html=True,
    )

    if "_session_start" in st.session_state:

        elapsed = time.time() - st.session_state["_session_start"]

        remaining = max(0, 3600 - int(elapsed))

        st.sidebar.caption(f"Session expire dans {remaining // 60} min")

    st.sidebar.divider()

    if is_admin:

        visible_pages = list(ADMIN_PAGE_LABELS)

        page_map = ADMIN_PAGE_INDEX

        default_page = "Accueil"

    else:

        visible_pages = list(ENGINEER_PAGE_LABELS)

        page_map = ENGINEER_PAGE_INDEX

        default_page = "Accueil"

    st.sidebar.markdown(
        '<div class="sb-section">Navigation</div>', unsafe_allow_html=True
    )

    nav_key = f"nav_page_{role}"

    if nav_key not in st.session_state:

        st.session_state[nav_key] = default_page

    current = st.session_state[nav_key]

    if current not in visible_pages:

        current = default_page

    selected_label = st.sidebar.radio(
        "Page",
        visible_pages,
        index=visible_pages.index(current) if current in visible_pages else 0,
        label_visibility="collapsed",
        key=nav_key,
    )

    page_index = page_map.get(selected_label, page_map.get(default_page, 0))

    st.sidebar.divider()

    st.sidebar.markdown('<div class="sb-section">Filtres</div>', unsafe_allow_html=True)

    from services.data_service import (
        clean_station_id_list,
        dataset_cache_key,
        get_dataset_date_bounds,
        load_filter_dimension_options,
    )

    from ui.utils import clear_dashboard_data_cache, reset_global_filters

    cache_key = dataset_cache_key()

    dim_opts = load_filter_dimension_options(cache_key)

    dmin, dmax = get_dataset_date_bounds(cache_key)

    if dmin and dmax and ("sb_date_from" not in st.session_state):

        st.session_state["sb_date_from"] = dmin

        st.session_state["sb_date_to"] = dmax

    filters: dict = {}

    if station_options:

        stations = clean_station_id_list(station_options)

        sel_stations = st.sidebar.multiselect(
            "Station", stations, key="sb_stations", placeholder="Toutes"
        )

        if sel_stations:

            filters["stations"] = [str(s) for s in sel_stations]

    dc1, dc2 = st.sidebar.columns(2)

    with dc1:

        date_from = st.date_input("Début", key="sb_date_from")

    with dc2:

        date_to = st.date_input("Fin", key="sb_date_to")

    if date_from and date_to:

        if date_from <= date_to:

            filters["date_range"] = (date_from, date_to)

        else:

            st.sidebar.warning(
                "La date de début doit être antérieure à la date de fin."
            )

    govs = dim_opts.get("gouvernorats") or []

    if govs:

        sel_govs = st.sidebar.multiselect(
            "Gouvernorat", govs, key="sb_govs", placeholder="Tous"
        )

        if sel_govs:

            filters["gouvernorats"] = sel_govs

    techs = dim_opts.get("technologies") or []

    if techs:

        sel_techs = st.sidebar.multiselect(
            "Technologie", techs, key="sb_techs", placeholder="Toutes"
        )

        if sel_techs:

            filters["technologies"] = sel_techs

    actions = dim_opts.get("actions") or []

    if actions:

        sel_actions = st.sidebar.multiselect(
            "Action (dernière action station)",
            actions,
            key="sb_actions",
            placeholder="Toutes",
        )

        if sel_actions:

            filters["actions"] = sel_actions

    prev_filters = st.session_state.get("global_filters", {})

    if prev_filters != filters:

        clear_dashboard_data_cache()

    if st.sidebar.button("Réinitialiser les filtres", width="stretch"):

        reset_global_filters()

        st.rerun()

    st.sidebar.divider()

    if st.sidebar.button("Déconnexion", width="stretch"):

        try:

            from services.data_service import db_execute

            session_id = st.session_state.get("session_id")

            if session_id:

                db_execute(
                    "end_user_session",
                    (datetime.now().isoformat(timespec="seconds"), session_id),
                )

        except Exception:

            pass

        for key in list(st.session_state.keys()):

            del st.session_state[key]

        st.rerun()

    st.session_state["global_filters"] = filters

    return (page_index, filters)
