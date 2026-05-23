"""Reusable Streamlit widgets and UI components."""

from __future__ import annotations

import base64
import html
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

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


def kpi_card(label: str, value: str, help_text: str = "", color: str = "", delta: str = "", delta_class: str = ""):
    safe_label = html.escape(label)
    safe_value = html.escape(value)
    safe_help = html.escape(help_text)
    safe_color = html.escape(color)
    delta_html = f'<div class="kpi-delta {delta_class}">{html.escape(delta)}</div>' if delta else ""
    st.markdown(
        f"""
<div class="kpi {safe_color}">
  <div class="kpi-row"><div class="kpi-label">{safe_label}</div></div>
  <div class="kpi-value">{safe_value}</div>
  <div class="kpi-row">
    <div class="kpi-help">{safe_help}</div>
    {delta_html}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def status_badge(label: str, status_type: str = "info"):
    """Render a status badge."""
    colors = {"info": "blue", "success": "green", "warning": "orange", "error": "red"}
    color = colors.get(status_type, "grey")
    st.markdown(
        (
            f'<span style="background-color:{color}; color:white; padding:2px 8px; '
            f'border-radius:4px; font-size:0.85em; font-weight:600;">{html.escape(label)}</span>'
        ),
        unsafe_allow_html=True,
    )


def alert_banner(title: str, body: str, style: str = "info", meta: str = ""):
    meta_html = f'<div class="alert-meta">{html.escape(meta)}</div>' if meta else ""
    st.markdown(
        f"""
<div class="alert {style}">
  <div style="flex:1">
    <div class="alert-title">{html.escape(title)}</div>
    <div class="alert-body">{html.escape(body)}</div>
    {meta_html}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def context_badge(label: str, value: str, tone: str = "info"):
    st.markdown(
        f"""
<div class="context-badge {html.escape(tone)}">
  <span>{html.escape(label)}</span>
  <strong>{html.escape(value)}</strong>
</div>
""",
        unsafe_allow_html=True,
    )


def section(title: str):
    st.markdown(f'<div class="section">{html.escape(title)}</div>', unsafe_allow_html=True)
    return st.container()


def live_indicator():
    st.markdown('<div class="live-indicator"><div class="live-dot"></div>LIVE</div>', unsafe_allow_html=True)


def global_status_bar(metrics: dict | None = None):
    """Fleet-wide status strip: alerts, OK stations, instant consumption."""
    if metrics is None:
        try:
            from ui.page_helpers import fleet_status_metrics, load_dashboard_df

            metrics = fleet_status_metrics(load_dashboard_df())
        except Exception:
            metrics = {}

    st.markdown(
        f"""
<div class="global-status-bar">
  <div class="gsb-item gsb-danger"><span>Critiques</span><strong>{metrics.get('critiques', 0)}</strong></div>
  <div class="gsb-item gsb-warning"><span>Attention</span><strong>{metrics.get('attention', 0)}</strong></div>
  <div class="gsb-item gsb-success"><span>Stations OK</span><strong>{metrics.get('ok', 0)}</strong></div>
  <div class="gsb-item gsb-info"><span>Conso instantanee</span><strong>{metrics.get('conso_instant', 0):,.1f} kWh</strong></div>
</div>
""",
        unsafe_allow_html=True,
    )


def page_footer():
    st.markdown(
        '<div class="page-footer">Simulation dataset — 3 ans Tunisie Telecom</div>',
        unsafe_allow_html=True,
    )


def header(title: str, subtitle: str, logo_path: Path | None = None, *, show_status: bool = True):
    if logo_path is None:
        logo_path = Path("static/logo.png")
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
    <div class="brand">Tunisie Telecom — BTS Energy Management</div>
    <div class="title">{html.escape(title)}</div>
    <div class="subtitle">{html.escape(subtitle)}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    if show_status and st.session_state.get("authenticated"):
        global_status_bar()


def render_artifact_gallery(
    images: Iterable[tuple[str, str]],
    *,
    title: str = "Images notebook",
    links: Iterable[tuple[str, str]] | None = None,
    columns: int = 2,
):
    """Render notebook images consistently with filter context."""
    from services.data_service import artifact_image_path, artifact_url
    from ui.utils import selected_station_filter, active_filter_label

    selected_station = selected_station_filter()
    filter_label = active_filter_label()

    st.markdown(
        f"""
<div class="artifact-toolbar">
  <div>
    <div class="artifact-title">{html.escape(title)}</div>
    <div class="artifact-subtitle">
      {html.escape(filter_label)}
    </div>
  </div>
  <div class="artifact-scope {'station' if selected_station else 'global'}">
    {'Station filtree' if selected_station else 'Vue globale'}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    cols = st.columns(max(1, columns))
    shown = 0
    for i, (filename, caption) in enumerate(images):
        path = artifact_image_path(filename)
        if not path:
            continue
        shown += 1
        with cols[i % len(cols)]:
            st.markdown('<div class="artifact-card">', unsafe_allow_html=True)
            st.image(str(path), width="stretch")
            extra = (
                f"Artefact global NB, contexte dashboard filtre sur {selected_station}."
                if selected_station
                else "Artefact global genere par notebook."
            )
            st.markdown(
                f"""
<div class="artifact-caption">
  <strong>{html.escape(caption)}</strong>
  <span>{html.escape(extra)}</span>
</div>
""",
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

    if shown == 0:
        st.info("Aucune image notebook disponible pour cette section.")

    if links:
        link_html = " ".join(
            f'<a href="{html.escape(artifact_url(filename))}" target="_blank">{html.escape(label)}</a>'
            for filename, label in links
        )
        st.markdown(f'<div class="artifact-links">{link_html}</div>', unsafe_allow_html=True)


def _data_freshness_label() -> str:
    from services.data_service import active_dataset_info, artifact_path
    info = active_dataset_info()
    pub = str(info.get("published_at") or "").strip()
    if pub:
        return pub
    path = artifact_path("streamlit_data.parquet")
    if path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return "Non disponible"


ENGINEER_PAGE_LABELS = [
    "Monitoring",
    "Anomalies",
    "Predictions",
    "Decision",
    "Agents RL",
    "Simulation",
]

ADMIN_PAGE_LABELS = [
    "Vue executive",
    "Parc",
    "Rapport",
    "Comparaison",
    "Donnees",
    "Configuration",
    "Gestion Utilisateurs",
]

ENGINEER_PAGE_INDEX = {
    "Monitoring": 7,
    "Anomalies": 3,
    "Predictions": 2,
    "Decision": 4,
    "Agents RL": 5,
    "Simulation": 6,
}

ADMIN_PAGE_INDEX = {
    "Vue executive": 0,
    "Parc": 1,
    "Rapport": 9,
    "Comparaison": 10,
    "Donnees": 11,
    "Configuration": 12,
    "Gestion Utilisateurs": 13,
}

# Legacy aliases (tests / deep links)
PAGE_LABELS = ADMIN_PAGE_LABELS
PAGE_INDEX_BY_LABEL = ADMIN_PAGE_INDEX


def sidebar_global(
    role: str,
    display: str,
    username: str,
    logo_path: Path | None = None,
    station_options: list | None = None,
) -> tuple[int, dict]:
    """Render the global sidebar. Returns (selected_page_index, filters_dict)."""
    station_options = station_options or []

    initials = "".join([n[0] for n in display.split()[:2]]).upper() if display else "?"
    is_admin = role == "admin"
    badge_cls = "role-badge-admin" if is_admin else "role-badge-engineer"
    badge_text = "ADMIN" if is_admin else "INGENIEUR RESEAU"

    st.sidebar.markdown(
        f"""
<div class="sb-user">
  <div class="sb-avatar">{html.escape(initials)}</div>
  <div>
    <div class="sb-name">{html.escape(display)}</div>
    <span class="role-badge {badge_cls}">{badge_text}</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if "_session_start" in st.session_state:
        elapsed = time.time() - st.session_state["_session_start"]
        remaining = max(0, 3600 - int(elapsed))
        st.sidebar.caption(f"Session expire dans {remaining // 60} min")

    st.sidebar.divider()

    # Navigation — role-filtered page list
    if is_admin:
        visible_pages = list(ADMIN_PAGE_LABELS)
        page_map = ADMIN_PAGE_INDEX
        default_page = "Vue executive"
    else:
        visible_pages = list(ENGINEER_PAGE_LABELS)
        page_map = ENGINEER_PAGE_INDEX
        default_page = "Monitoring"

    st.sidebar.markdown('<div class="sb-section">Navigation</div>', unsafe_allow_html=True)
    nav_key = f"nav_page_{role}"
    if nav_key not in st.session_state:
        st.session_state[nav_key] = default_page
    current = st.session_state[nav_key]
    if current not in visible_pages:
        current = default_page
    selected_label = st.sidebar.radio(
        "Page", visible_pages,
        index=visible_pages.index(current) if current in visible_pages else 0,
        label_visibility="collapsed",
        key=nav_key,
    )
    page_index = page_map.get(selected_label, page_map.get(default_page, 0))

    st.sidebar.divider()

    # Global Filters
    st.sidebar.markdown('<div class="sb-section">Filtres Globaux</div>', unsafe_allow_html=True)

    filters = {}

    if station_options:
        stations = [str(station) for station in station_options]
        default_stations = st.session_state.get("sb_stations", [])
        default_stations = [s for s in default_stations if s in stations]
        sel_stations = st.sidebar.multiselect(
            "Station",
            stations,
            default=default_stations,
            key="sb_stations",
            placeholder="Toutes les stations",
        )
        if sel_stations:
            filters["stations"] = sel_stations

    with st.sidebar.expander("Filtres avances", expanded=False):
        date_from = st.date_input("Debut periode", value=None, key="sb_date_from")
        date_to = st.date_input("Fin periode", value=None, key="sb_date_to")
        if date_from and date_to:
            filters["date_range"] = (date_from, date_to)

        from services.data_service import load_filtered_main_data
        ds = load_filtered_main_data(["gouvernorat", "technologie", "type_zone"])

        if "gouvernorat" in ds.columns:
            govs = sorted(ds["gouvernorat"].dropna().unique().astype(str).tolist())
            sel_govs = st.multiselect(
                "Gouvernorat", govs, default=[], key="sb_govs", placeholder="Tous les gouvernorats"
            )
            if sel_govs:
                filters["gouvernorats"] = sel_govs

        if "technologie" in ds.columns:
            techs = sorted(ds["technologie"].dropna().unique().astype(str).tolist())
            sel_techs = st.multiselect(
                "Technologie", techs, default=[], key="sb_techs", placeholder="Toutes les technologies"
            )
            if sel_techs:
                filters["technologies"] = sel_techs

        if "type_zone" in ds.columns:
            zones = sorted(ds["type_zone"].dropna().unique().astype(str).tolist())
            sel_zones = st.multiselect(
                "Type zone", zones, default=[], key="sb_zones", placeholder="Toutes les zones"
            )
            if sel_zones:
                filters["zones"] = sel_zones

    st.sidebar.divider()

    # Logout
    if st.sidebar.button("Deconnexion", width="stretch"):
        try:
            from services.data_service import db_execute
            session_id = st.session_state.get("session_id")
            if session_id:
                db_execute("end_user_session", (datetime.now().isoformat(timespec="seconds"), session_id))
        except Exception:
            pass
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.session_state["global_filters"] = filters
    return page_index, filters
