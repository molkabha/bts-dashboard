from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from config.theme import mode_badge_css, mode_color, normalize_mode_key
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


def sidebar_label(text: str) -> None:
    st.markdown(f'<div class="sim-sidebar-label">{html.escape(text)}</div>', unsafe_allow_html=True)


def sidebar_divider() -> None:
    st.markdown('<div class="sim-divider"></div>', unsafe_allow_html=True)


def kpi_strip(running: bool, tick: int, total: int, n_alerts: int, n_decisions: int, conso: float, eco_dt: float) -> None:
    state = "Simulation en cours" if running else "En attente"
    prog = f"{tick}/{total}" if total else "—"
    items = [
        ("Etat", state, "gsb-info" if running else ""),
        ("Progression", prog, ""),
        ("Alertes", str(n_alerts), "gsb-danger" if n_alerts else ""),
        ("Decisions", str(n_decisions), "gsb-warning" if n_decisions else ""),
        ("Conso heure", f"{conso:.1f} kWh", "gsb-success"),
        ("Economie", f"{eco_dt:.2f} DT", "gsb-success"),
    ]
    blocks = "".join(
        f'<div class="gsb-item {cls}"><span>{html.escape(lbl)}</span><strong>{html.escape(val)}</strong></div>'
        for lbl, val, cls in items
    )
    st.markdown(f'<div class="global-status-bar">{blocks}</div>', unsafe_allow_html=True)


def hero_time(latest_ts, sim_date) -> None:
    t = pd.Timestamp(latest_ts).strftime("%H:%M") if latest_ts is not None else "—:—"
    d = pd.Timestamp(latest_ts).strftime("%d/%m/%Y") if latest_ts is not None else "—"
    st.markdown(
        f"""
<div>
  <div class="sim-hero-time">{html.escape(t)}</div>
  <div class="sim-hero-sub">{html.escape(d)} · {html.escape(calendar_label(sim_date))}</div>
</div>""",
        unsafe_allow_html=True,
    )


def render_decision_card(row, action: str, reason: str) -> None:
    mode = str(row.get("mode_operation", "NORMAL"))
    station = str(row.get("station_id", "—"))
    color = mode_color(mode)
    badge_cls = mode_badge_css(mode)
    st.markdown(
        f"""
<div class="decision-card" style="border-left-color:{color};">
  <div class="dc-header">
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
    card_cls = "critique" if normalize_mode_key(sev) == "CRITIQUE" else "attention"
    st.markdown(
        f"""
<div class="anomaly-card {card_cls}">
  <div class="ac-header">
    <span class="ac-station">{html.escape(str(item.get("station_id","")))}</span>
    <span class="ac-badge {card_cls}">{html.escape(sev)}</span>
  </div>
  <div class="ac-detail">{html.escape(str(item.get("message","")))}</div>
  <div class="ac-meta">{html.escape(str(item.get("timestamp",""))[:19])}</div>
</div>""",
        unsafe_allow_html=True,
    )
