from __future__ import annotations

import html

import streamlit as st

from config.theme import mode_badge_css, mode_color, normalize_mode_key


def empty_state(title: str, body: str) -> None:
    st.markdown(
        f"""
<div class="sim-empty">
  <div class="sim-empty-title">{html.escape(title)}</div>
  <div class="sim-empty-body">{html.escape(body)}</div>
</div>""",
        unsafe_allow_html=True,
    )


def decision_block(station: str, mode: str, action: str, detail: str) -> None:
    color = mode_color(mode)
    badge = mode_badge_css(mode)
    st.markdown(
        f"""
<div class="decision-card" style="border-left-color:{color};">
  <span class="badge {badge}">{html.escape(normalize_mode_key(mode) or "NORMAL")}</span>
  <div class="dc-mode" style="color:{color};margin-top:8px;">{html.escape(station)}</div>
  <div class="dc-action">{html.escape(action)}</div>
  <div class="dc-reason">{html.escape(detail)}</div>
</div>""",
        unsafe_allow_html=True,
    )
