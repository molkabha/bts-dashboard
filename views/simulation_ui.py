from __future__ import annotations

import html
from datetime import date

import pandas as pd
import streamlit as st

from config.theme import mode_badge_css, mode_color, mode_status_type, normalize_mode_key
from services.calendar_tn import calendar_label


def empty_state(title: str, body: str) -> None:
    st.markdown(
        f"""
<div class="sim-empty">
  <div class="sim-empty-title">{html.escape(title)}</div>
  <div class="sim-empty-body">{html.escape(body)}</div>
</div>""",
        unsafe_allow_html=True,
    )


def live_badge(running: bool) -> None:
    if running:
        st.markdown(
            '<span class="live-indicator"><span class="live-dot"></span>Simulation active</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<span class="badge badge-muted">En attente</span>', unsafe_allow_html=True)


def status_pills(
    running: bool,
    tick: int,
    total: int,
    n_stations: int,
    sim_date: date,
    n_alerts: int = 0,
    n_decisions: int = 0,
) -> None:
    state_cls = "live" if running else "idle"
    state_label = "En cours" if running else "Arretee"
    prog = f"{tick} / {total}" if total else "—"
    pills = [
        f'<span class="sim-status-pill {state_cls}"><span>Etat</span> <strong>{html.escape(state_label)}</strong></span>',
        f'<span class="sim-status-pill"><span>Progression</span> <strong>{html.escape(prog)}</strong></span>',
        f'<span class="sim-status-pill"><span>Stations</span> <strong>{n_stations}</strong></span>',
        f'<span class="sim-status-pill"><span>Calendrier</span> <strong>{html.escape(calendar_label(sim_date))}</strong></span>',
        f'<span class="sim-status-pill"><span>Alertes</span> <strong>{n_alerts}</strong></span>',
        f'<span class="sim-status-pill"><span>Decisions</span> <strong>{n_decisions}</strong></span>',
    ]
    st.markdown(
        f'<div class="sim-status-row">{"".join(pills)}</div>',
        unsafe_allow_html=True,
    )


def render_toolbar_shell() -> None:
    st.markdown(
        """
<div class="sim-toolbar">
  <div class="sim-toolbar-head">
    <div class="sim-toolbar-title">Parametres du scenario</div>
  </div>
""",
        unsafe_allow_html=True,
    )


def close_toolbar_shell() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_clock(latest_ts) -> None:
    label = pd.Timestamp(latest_ts).strftime("%Y-%m-%d  %H:%M") if latest_ts is not None else "—"
    st.markdown(f'<div class="sim-clock">{html.escape(label)}</div>', unsafe_allow_html=True)


def render_decision_card(row, action: str, reason: str) -> None:
    mode = str(row.get("mode_operation", "NORMAL"))
    station = str(row.get("station_id", "—"))
    color = mode_color(mode)
    badge_cls = mode_badge_css(mode)
    st.markdown(
        f"""
<div class="decision-card" style="border-left-color:{color};">
  <div class="dc-header">
    <div class="dc-station">Station {html.escape(station)}</div>
    <span class="badge {badge_cls}">{html.escape(normalize_mode_key(mode) or "NORMAL")}</span>
  </div>
  <div class="dc-mode" style="color:{color};">{html.escape(station)}</div>
  <div class="dc-action">{html.escape(action)}</div>
  <div class="dc-reason">{html.escape(reason)}</div>
</div>""",
        unsafe_allow_html=True,
    )


def render_alert_card(item: dict) -> None:
    sev = str(item.get("severity", "ATTENTION"))
    sev_key = normalize_mode_key(sev) if sev in {"CRITIQUE", "ATTENTION"} else "ATTENTION"
    card_cls = "critique" if sev_key == "CRITIQUE" else "attention"
    station = str(item.get("station_id", ""))
    ts = str(item.get("timestamp", ""))[:19]
    msg = str(item.get("message", ""))
    st.markdown(
        f"""
<div class="anomaly-card {card_cls}">
  <div class="ac-header">
    <span class="ac-station">{html.escape(station)}</span>
    <span class="ac-badge {card_cls}">{html.escape(sev)}</span>
  </div>
  <div class="ac-detail">{html.escape(msg)}</div>
  <div class="ac-meta">{html.escape(ts)}</div>
</div>""",
        unsafe_allow_html=True,
    )


def filter_panel(title: str = "Filtres") -> None:
    st.markdown(f'<div class="sim-filter-bar"><div class="sim-panel-title">{html.escape(title)}</div>', unsafe_allow_html=True)


def close_filter_panel() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def panel_open(title: str) -> None:
    st.markdown(
        f'<div class="sim-panel"><div class="sim-panel-title">{html.escape(title)}</div>',
        unsafe_allow_html=True,
    )


def panel_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def tab_labels(n_alerts: int, n_decisions: int) -> list[str]:
    return [
        "Pilotage",
        "Temps reel",
        f"Alertes ({n_alerts})" if n_alerts else "Alertes",
        f"Decisions ({n_decisions})" if n_decisions else "Decisions",
        "Carte",
    ]
