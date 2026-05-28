from __future__ import annotations

import html

import streamlit as st

from config.theme import mode_badge_css, mode_color, normalize_mode_key


def empty_state(title: str, body: str) -> None:

    st.markdown(
        f'\n<div class="sim-empty">\n  <div class="sim-empty-title">{html.escape(title)}</div>\n  <div class="sim-empty-body">{html.escape(body)}</div>\n</div>',
        unsafe_allow_html=True,
    )


def decision_block(
    station: str,
    mode: str,
    action: str,
    detail: str,
    *,
    gain_dt: float | None = None,
    gain_kwh: float | None = None,
    ecart_pct: float | None = None,
) -> None:

    color = mode_color(mode)

    badge = mode_badge_css(mode)

    extra = ""

    if ecart_pct is not None:

        extra += f'<div class="dc-saving">Écart réel/prédit : {ecart_pct:+.1f} %</div>'

    if gain_dt is not None and gain_kwh is not None and (gain_kwh > 0):

        extra += f'<div class="dc-saving">Gain estimé : {gain_dt:.2f} DT · {gain_kwh:.2f} kWh</div>'

    st.markdown(
        f"""\n<div class="decision-card" style="border-left-color:{color};">\n  <span class="badge {badge}">{html.escape(normalize_mode_key(mode) or 'NORMAL')}</span>\n  <div class="dc-mode" style="color:{color};margin-top:8px;">{html.escape(station)}</div>\n  <div class="dc-action">{html.escape(action)}</div>\n  <div class="dc-reason">{html.escape(detail)}</div>\n  {extra}\n</div>""",
        unsafe_allow_html=True,
    )
