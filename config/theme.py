from __future__ import annotations

from typing import Iterable

import pandas as pd

COLOR_PRIMARY = "#c8102e"

COLOR_SECONDARY = "#1e3a8a"

COLOR_ACCENT = "#1e40af"

COLOR_BG = "#f8fafc"

COLOR_TEXT = "#0f172a"

COLOR_MUTED = "#64748b"

COLOR_SUCCESS = "#16a34a"

COLOR_WARNING = "#ca8a04"

COLOR_DANGER = "#dc2626"

COLOR_INFO = "#3b82f6"

COLOR_ECO = "#0ea5e9"

COLOR_LIVE = "#22c55e"

OPT_ECONOMIE_EXPERT_COLOR = "#6d28d9"

OPT_ECONOMIE_RL_COLOR = "#ea580c"

OPT_TOP_STATIONS_COLOR = "#65a30d"

PLOTLY_LIGHT = {
    "layout": {
        "font": {"family": "Inter, Segoe UI, Arial", "color": "#0f172a"},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": [
            "#c8102e",
            "#1e3a8a",
            "#0ea5e9",
            "#059669",
            "#d97706",
            "#7c3aed",
            "#0891b2",
        ],
        "xaxis": {"gridcolor": "#e2e8f0", "zerolinecolor": "#e2e8f0"},
        "yaxis": {"gridcolor": "#e2e8f0", "zerolinecolor": "#e2e8f0"},
        "margin": {"l": 40, "r": 20, "t": 30, "b": 40},
        "legend": {"bgcolor": "rgba(255,255,255,0.6)", "bordercolor": "#e2e8f0"},
    }
}

PLOTLY_DARK = {
    "layout": {
        "font": {"family": "Inter, Segoe UI, Arial", "color": "#e2e8f0"},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": [
            "#f87171",
            "#60a5fa",
            "#38bdf8",
            "#34d399",
            "#fbbf24",
            "#a78bfa",
            "#22d3ee",
        ],
        "xaxis": {"gridcolor": "#1f2937", "zerolinecolor": "#1f2937"},
        "yaxis": {"gridcolor": "#1f2937", "zerolinecolor": "#1f2937"},
        "margin": {"l": 40, "r": 20, "t": 30, "b": 40},
        "legend": {"bgcolor": "rgba(15,23,42,0.6)", "bordercolor": "#334155"},
    }
}

MODE_COLORS = {
    "CRITIQUE": "#dc2626",
    "ATTENTION": "#eab308",
    "NORMAL": "#16a34a",
    "ECO": "#0891b2",
}

MODE_ORDER = ["CRITIQUE", "ATTENTION", "NORMAL", "ECO"]

SEVERITY_COLORS = {
    "CRITIQUE": MODE_COLORS["CRITIQUE"],
    "ATTENTION": MODE_COLORS["ATTENTION"],
    "FAIBLE": "#64748b",
}

STATUS_BADGE_COLORS = {
    "success": MODE_COLORS["NORMAL"],
    "warning": MODE_COLORS["ATTENTION"],
    "error": MODE_COLORS["CRITIQUE"],
    "eco": MODE_COLORS["ECO"],
    "info": COLOR_INFO,
}


def normalize_mode_key(mode: str | None) -> str:

    return str(mode or "").strip().upper()


def mode_color(mode: str | None, default: str = "#64748b") -> str:

    return MODE_COLORS.get(normalize_mode_key(mode), default)


def mode_status_type(mode: str | None) -> str:

    key = normalize_mode_key(mode)

    if key == "CRITIQUE":

        return "error"

    if key == "ATTENTION":

        return "warning"

    if key == "NORMAL":

        return "success"

    if key == "ECO":

        return "eco"

    return "info"


def mode_kpi_class(mode: str | None) -> str:

    return {
        "CRITIQUE": "red",
        "ATTENTION": "orange",
        "NORMAL": "green",
        "ECO": "eco",
    }.get(normalize_mode_key(mode), "gray")


def mode_badge_css(mode: str | None) -> str:

    return {
        "CRITIQUE": "badge-critical",
        "ATTENTION": "badge-warning",
        "NORMAL": "badge-normal",
        "ECO": "badge-eco",
    }.get(normalize_mode_key(mode), "badge-muted")


ACTION_COLORS = {
    "Maintien": "#64748b",
    "Aucune action": "#94a3b8",
    "Réduction de puissance": "#0891b2",
    "Réduire la puissance": "#0891b2",
    "Passage mode ECO": "#059669",
    "Éco calendaire": "#0d9488",
    "Veille secteur": "#7c3aed",
    "Free cooling": "#0284c7",
    "Alerte QoS": "#dc2626",
    "Intervention terrain": "#b91c1c",
    "Couper un porteur": "#d97706",
}

MAP_ACTION_COLORS = {
    "Maintien": "#64748b",
    "Aucune action": "#94a3b8",
    "Réduction de puissance": "#2563eb",
    "Réduire la puissance": "#2563eb",
    "Passage mode ECO": "#16a34a",
    "Éco calendaire": "#ca8a04",
    "Veille secteur": "#9333ea",
    "Free cooling": "#06b6d4",
    "Alerte QoS": "#f97316",
    "Intervention terrain": "#dc2626",
    "Couper un porteur": "#db2777",
    "Maintien de la consommation": "#475569",
    "Forcer mode ECO": "#059669",
}


def action_color_discrete_map(
    values: Iterable | pd.Series | None = None,
) -> dict[str, str]:

    cmap = dict(ACTION_COLORS)

    if values is not None:

        for raw in pd.Series(values).dropna().astype(str).unique():

            label = str(raw).strip()

            if label and label not in cmap:

                cmap[label] = "#64748b"

    return cmap


def map_action_color_discrete_map(
    values: Iterable | pd.Series | None = None,
) -> dict[str, str]:

    cmap = dict(MAP_ACTION_COLORS)

    fallback = ["#6366f1", "#14b8a6", "#f43f5e", "#84cc16", "#8b5cf6", "#0ea5e9"]

    if values is not None:

        idx = 0

        for raw in pd.Series(values).dropna().astype(str).unique():

            label = str(raw).strip()

            if label and label not in cmap:

                cmap[label] = fallback[idx % len(fallback)]

                idx += 1

    return cmap


def mode_color_discrete_map(
    values: Iterable | pd.Series | None = None,
) -> dict[str, str]:

    cmap = dict(MODE_COLORS)

    if values is not None:

        for raw in pd.Series(values).dropna().astype(str).unique():

            key = normalize_mode_key(raw)

            if key and key not in cmap:

                cmap[key] = "#64748b"

    return cmap


def mode_category_order(values: Iterable | pd.Series | None = None) -> list[str]:

    if values is None:

        return list(MODE_ORDER)

    present = {normalize_mode_key(v) for v in pd.Series(values).dropna()}

    ordered = [m for m in MODE_ORDER if m in present]

    ordered.extend(sorted(present - set(ordered)))

    return ordered


APP_CSS = '\n<style>\n@import url(\'https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap\');\n:root {\n  --tt-red:#c8102e; --tt-red-dark:#a30c25;\n  --tt-blue:#1e3a8a; --tt-blue-soft:#1e40af;\n  --tt-bg:#f7f9fc; --tt-card:#ffffff; --tt-border:#dbe3ee;\n  --tt-text:#0f172a; --tt-muted:#64748b;\n  --tt-success:#16a34a; --tt-warning:#eab308; --tt-danger:#dc2626;\n  --tt-mode-critique:#dc2626; --tt-mode-attention:#eab308; --tt-mode-normal:#16a34a; --tt-mode-eco:#0891b2;\n  --tt-info:#3b82f6; --tt-eco:#0ea5e9; --tt-live:#22c55e;\n}\nhtml, body, [data-testid="stAppViewContainer"] { background:var(--tt-bg); font-family:\'Inter\',\'Segoe UI\',Arial,sans-serif; }\n.block-container { padding-top:0.75rem; padding-bottom:2.2rem; max-width:1360px; }\n\n/* Streamlit base cleanup */\n[data-testid="stHeader"] { background:transparent; }\ndiv[data-testid="stVerticalBlock"] { gap:0.75rem; }\n.stButton > button, .stDownloadButton > button, [data-testid="stBaseButton-secondary"],\n[data-testid="stBaseButton-primary"] { border-radius:6px !important; font-weight:750 !important; min-height:38px; }\n.stSelectbox label, .stMultiSelect label, .stDateInput label, .stSlider label,\n.stRadio label, .stTextInput label, .stFileUploader label {\n  color:var(--tt-text) !important; font-size:12px !important; font-weight:750 !important;\n}\n\n/* Topbar */\n.topbar { border:1px solid var(--tt-border); border-left:4px solid var(--tt-red); padding:12px 16px; margin-bottom:14px; display:flex; align-items:center; gap:14px; background:var(--tt-card); border-radius:8px; box-shadow:0 1px 2px rgba(15,23,42,0.04); }\n.topbar-logo { width:66px; height:38px; object-fit:contain; }\n.topbar-content { min-width:0; flex:1; }\n.brand { color:var(--tt-red); font-size:10.5px; font-weight:800; letter-spacing:1.2px; text-transform:uppercase; }\n.title { color:var(--tt-text); font-size:22px; font-weight:820; line-height:1.18; }\n.subtitle { color:var(--tt-muted); font-size:12.5px; margin-top:2px; }\n.topbar-role { text-align:right; margin-top:2px; flex:0 0 auto; }\n.topbar-meta { display:flex; flex-wrap:wrap; gap:8px; margin-top:9px; }\n.topbar-meta span { display:inline-flex; gap:4px; align-items:center; color:var(--tt-muted); background:#f8fafc; border:1px solid var(--tt-border); border-radius:999px; padding:3px 8px; font-size:10.5px; line-height:1.3; max-width:100%; }\n.topbar-meta strong { color:var(--tt-text); font-weight:800; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px; }\n\n/* Role pills */\n.role-pill { display:inline-block; background:#f1f5f9; color:var(--tt-text); border:1px solid var(--tt-border); padding:4px 9px; border-radius:999px; font-size:10.5px; font-weight:800; text-transform:uppercase; }\n.role-pill.admin { background:var(--tt-red); color:#fff; border-color:var(--tt-red); }\n.role-badge { display:inline-block; margin-top:6px; padding:4px 10px; border-radius:999px; font-size:10px; font-weight:850; letter-spacing:0.5px; text-transform:uppercase; }\n.role-badge-admin { background:var(--tt-red); color:#fff; border:1px solid var(--tt-red-dark); }\n.role-badge-engineer { background:#2563eb; color:#fff; border:1px solid #1d4ed8; }\n.global-status-bar { display:flex; flex-wrap:wrap; gap:10px; margin:-4px 0 14px 0; padding:10px 12px; background:var(--tt-card); border:1px solid var(--tt-border); border-radius:8px; }\n.gsb-item { flex:1; min-width:120px; display:flex; flex-direction:column; gap:2px; padding:6px 10px; border-radius:6px; border:1px solid var(--tt-border); background:#f8fafc; }\n.gsb-item span { font-size:10px; font-weight:750; text-transform:uppercase; color:var(--tt-muted); letter-spacing:0.3px; }\n.gsb-item strong { font-size:18px; font-weight:850; color:var(--tt-text); }\n.gsb-item.gsb-danger { border-left:3px solid var(--tt-danger); }\n.gsb-item.gsb-warning { border-left:3px solid var(--tt-warning); }\n.gsb-item.gsb-success { border-left:3px solid var(--tt-success); }\n.gsb-item.gsb-info { border-left:3px solid var(--tt-blue-soft); }\n.page-footer { text-align:center; font-size:10.5px; color:var(--tt-muted); margin-top:28px; padding:10px; border-top:1px dashed var(--tt-border); opacity:0.85; }\n\n/* Badges */\n.badge { display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px; font-size:11px; font-weight:800; letter-spacing:0.6px; text-transform:uppercase; border:1px solid transparent; }\n.badge-normal { background:#ecfdf5; color:#15803d; border-color:#86efac; }\n.badge-eco { background:#ecfeff; color:#0e7490; border-color:#67e8f9; }\n.badge-warning { background:#fefce8; color:#a16207; border-color:#fde047; }\n.badge-critical { background:#fef2f2; color:#b91c1c; border-color:#fca5a5; }\n.badge-info { background:#eff6ff; color:#1d4ed8; border-color:#bfdbfe; }\n.badge-muted { background:#f1f5f9; color:#475569; border-color:#e2e8f0; }\n.badge-live { background:#022c22; color:#bbf7d0; border-color:#16a34a; animation:live-pulse 1.6s ease-in-out infinite; }\n@keyframes live-pulse { 0%,100%{box-shadow:0 0 0 0 rgba(34,197,94,0.55);} 50%{box-shadow:0 0 0 8px rgba(34,197,94,0);} }\n.badge .dot { display:inline-block; width:6px; height:6px; border-radius:50%; background:currentColor; }\n\n/* KPI cards */\n.kpi { border:1px solid var(--tt-border); border-left:3px solid var(--tt-blue-soft); border-radius:6px; padding:12px 14px; background:var(--tt-card); min-height:84px; box-shadow:0 1px 2px rgba(15,23,42,0.035); transition:border-color .12s ease,box-shadow .12s ease; }\n.kpi:hover { box-shadow:0 4px 10px rgba(15,23,42,0.055); border-color:#cbd5e1; }\n.kpi.green { border-left-color:var(--tt-success); }\n.kpi.orange { border-left-color:var(--tt-mode-attention); }\n.kpi.red { border-left-color:var(--tt-danger); }\n.kpi.blue { border-left-color:var(--tt-blue-soft); }\n.kpi.eco { border-left-color:var(--tt-eco); }\n.kpi.gray { border-left-color:var(--tt-muted); }\n.kpi-row { display:flex; align-items:center; justify-content:space-between; gap:10px; }\n.kpi-label { color:var(--tt-muted); font-size:10.5px; font-weight:750; text-transform:uppercase; letter-spacing:0.35px; }\n.kpi-value { color:var(--tt-text); font-size:24px; font-weight:820; margin-top:5px; line-height:1.08; }\n.kpi-help { color:var(--tt-muted); font-size:11.5px; margin-top:4px; }\n.kpi-delta { font-size:11px; font-weight:700; padding:2px 8px; border-radius:999px; display:inline-block; margin-top:6px; }\n.kpi-delta.up { background:#ecfdf5; color:#047857; }\n.kpi-delta.down { background:#fee2e2; color:#991b1b; }\n\n/* Section headings */\n.section { color:var(--tt-text); font-size:13px; font-weight:820; text-transform:none; border-left:0; padding-left:0; margin:20px 0 8px 0; letter-spacing:0; }\n.section::after { content:""; display:block; width:100%; height:1px; background:var(--tt-border); margin-top:8px; }\n\n/* Alert banners */\n.alert { display:flex; gap:12px; align-items:flex-start; border:1px solid var(--tt-border); border-left:3px solid var(--tt-info); background:#fff; border-radius:6px; padding:11px 13px; margin-bottom:8px; box-shadow:0 1px 2px rgba(15,23,42,0.025); }\n.alert.success { border-left-color:var(--tt-success); background:#f0fdf4; }\n.alert.warning { border-left-color:var(--tt-warning); background:#fffbeb; }\n.alert.danger { border-left-color:var(--tt-danger); background:#fef2f2; }\n.alert .alert-title { font-weight:800; font-size:13px; margin-bottom:2px; }\n.alert .alert-body { font-size:12.5px; color:var(--tt-muted); }\n.alert .alert-meta { font-size:11px; color:var(--tt-muted); margin-top:4px; font-weight:600; }\n\n.summary-strip { border:1px solid var(--tt-border); border-left:3px solid var(--tt-blue-soft); background:#fff; border-radius:6px; padding:11px 13px; color:var(--tt-text); font-size:13.5px; font-weight:760; line-height:1.45; margin-bottom:8px; }\n\n/* Filter and artefact context */\n.context-badge { display:flex; justify-content:space-between; gap:12px; align-items:center; border:1px solid var(--tt-border); border-left:4px solid var(--tt-info); background:var(--tt-card); border-radius:8px; padding:10px 12px; margin:8px 0; font-size:12px; color:var(--tt-muted); }\n.context-badge strong { color:var(--tt-text); font-size:13px; }\n.context-badge.success { border-left-color:var(--tt-success); }\n.context-badge.warning { border-left-color:var(--tt-warning); }\n.artifact-toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; border:1px solid var(--tt-border); background:var(--tt-card); border-radius:8px; padding:12px 14px; margin-bottom:12px; }\n.artifact-title { color:var(--tt-text); font-size:14px; font-weight:850; }\n.artifact-subtitle { color:var(--tt-muted); font-size:12px; margin-top:3px; }\n.artifact-scope { flex:0 0 auto; padding:5px 10px; border-radius:999px; border:1px solid var(--tt-border); font-size:11px; font-weight:850; text-transform:uppercase; color:var(--tt-muted); background:#f8fafc; }\n.artifact-scope.station { color:#047857; border-color:#a7f3d0; background:#ecfdf5; }\n.artifact-card { border:1px solid var(--tt-border); border-radius:8px; background:var(--tt-card); padding:10px; margin-bottom:12px; box-shadow:0 1px 2px rgba(15,23,42,0.04); }\n.artifact-caption { display:flex; flex-direction:column; gap:3px; padding:8px 2px 0 2px; }\n.artifact-caption strong { color:var(--tt-text); font-size:13px; }\n.artifact-caption span { color:var(--tt-muted); font-size:11.5px; line-height:1.35; }\n.artifact-links { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }\n.artifact-links a { color:var(--tt-blue); border:1px solid var(--tt-border); background:var(--tt-card); padding:5px 9px; border-radius:6px; font-size:12px; font-weight:700; text-decoration:none; }\n.artifact-links a:hover { border-color:var(--tt-blue-soft); color:var(--tt-red); }\n\n/* Nav cards (Page 0) */\n.nav-card { border:1px solid var(--tt-border); border-radius:6px; padding:16px; background:var(--tt-card); cursor:pointer; transition:box-shadow .15s ease,border-color .15s ease; box-shadow:0 1px 2px rgba(15,23,42,0.035); }\n.nav-card:hover { box-shadow:0 5px 14px rgba(15,23,42,0.065); border-color:var(--tt-blue-soft); }\n.nav-card .nc-title { font-size:14px; font-weight:820; color:var(--tt-text); margin-bottom:3px; }\n.nav-card .nc-value { font-size:24px; font-weight:850; color:var(--tt-blue); margin:7px 0; }\n.nav-card .nc-desc { font-size:12px; color:var(--tt-muted); }\n\n/* Anomaly feed cards (Page 3) */\n.anomaly-card { border:1px solid var(--tt-border); border-radius:6px; padding:12px 14px; background:var(--tt-card); margin-bottom:8px; transition:all .12s ease; }\n.anomaly-card.critique { border-left:3px solid var(--tt-danger); }\n.anomaly-card.attention { border-left:3px solid var(--tt-warning); }\n.anomaly-card.faible { border-left:3px solid var(--tt-muted); }\n.anomaly-card.traite { opacity:0.55; background:#f8fafc; }\n.anomaly-card .ac-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }\n.anomaly-card .ac-badge { font-size:11px; font-weight:800; text-transform:uppercase; padding:2px 8px; border-radius:4px; }\n.anomaly-card .ac-badge.critique { background:#fee2e2; color:#991b1b; }\n.anomaly-card .ac-badge.attention { background:#fefce8; color:#a16207; }\n.anomaly-card .ac-badge.faible { background:#f1f5f9; color:#475569; }\n.anomaly-card .ac-station { font-weight:800; font-size:14px; color:var(--tt-text); }\n.anomaly-card .ac-detail { font-size:12.5px; color:var(--tt-muted); line-height:1.5; }\n.anomaly-card .ac-meta { font-size:11px; color:var(--tt-muted); font-weight:600; margin-top:6px; }\n\n/* Cockpit (Page 5) */\n.cockpit-clock { font-family:\'Courier New\',monospace; font-size:28px; font-weight:850; color:var(--tt-text); text-align:center; padding:10px; background:var(--tt-card); border:1px solid var(--tt-border); border-radius:6px; letter-spacing:2px; }\n.decision-card { border:1px solid var(--tt-border); border-left:3px solid var(--tt-mode-normal); border-radius:6px; padding:13px 14px; background:var(--tt-card); margin-bottom:8px; }\n.decision-card .dc-mode { font-size:16px; font-weight:850; margin-bottom:6px; }\n.decision-card .dc-action { font-size:13px; font-weight:700; color:var(--tt-text); margin-bottom:4px; }\n.decision-card .dc-reason { font-size:12px; color:var(--tt-muted); line-height:1.5; }\n.decision-card .dc-saving { font-size:13px; font-weight:800; color:var(--tt-mode-normal); margin-top:8px; }\n\n/* Live indicator */\n.live-indicator { display:inline-flex; align-items:center; gap:8px; padding:6px 12px; border-radius:999px; background:#022c22; color:#bbf7d0; font-weight:800; font-size:12px; letter-spacing:1px; text-transform:uppercase; border:1px solid #14532d; }\n.live-indicator .live-dot { width:8px; height:8px; border-radius:50%; background:#22c55e; box-shadow:0 0 0 0 rgba(34,197,94,0.55); animation:live-pulse 1.6s ease-in-out infinite; }\n\n/* Info box */\n.info-box { border:1px solid var(--tt-border); border-radius:8px; padding:12px 14px; background:linear-gradient(180deg,#f8fafc 0%,#ffffff 100%); }\n.info-box .ib-title { font-weight:800; font-size:12px; color:var(--tt-blue); text-transform:uppercase; letter-spacing:0.6px; }\n.info-box .ib-body { font-size:13px; color:var(--tt-text); margin-top:4px; line-height:1.5; }\n\n/* Tables */\n[data-testid="stDataFrame"] { border:1px solid var(--tt-border); border-radius:6px; overflow:hidden; }\n\n/* Sidebar */\n[data-testid="stSidebar"] { background:#ffffff; border-right:1px solid var(--tt-border); }\n[data-testid="stSidebar"] .sb-section { font-size:10.5px; font-weight:820; text-transform:uppercase; letter-spacing:0.8px; color:var(--tt-muted); margin:13px 6px 4px 6px; padding-bottom:4px; border-bottom:1px solid var(--tt-border); }\n[data-testid="stSidebar"] .sb-user { display:flex; align-items:center; gap:10px; padding:8px 10px; border-radius:6px; background:#f8fafc; border:1px solid var(--tt-border); margin-bottom:8px; }\n[data-testid="stSidebar"] .sb-user .sb-avatar { width:34px; height:34px; border-radius:50%; background:var(--tt-red); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:13px; }\n[data-testid="stSidebar"] .sb-user .sb-name { font-weight:800; font-size:13px; color:var(--tt-text); line-height:1.2; }\n[data-testid="stSidebar"] .sb-user .sb-role { font-size:11px; color:var(--tt-muted); }\n.data-freshness { font-size:11px; color:var(--tt-muted); padding:6px 10px; background:#f1f5f9; border-radius:6px; border:1px solid var(--tt-border); margin:8px 0; }\n[data-testid="stSidebar"] [data-baseweb="tag"] { max-width:100%; }\n[data-testid="stSidebar"] [data-baseweb="select"] { font-size:12px; }\n\n/* Expanders: keep technical content secondary */\n[data-testid="stExpander"] { border:1px solid var(--tt-border) !important; border-radius:6px !important; background:var(--tt-card) !important; box-shadow:none !important; }\n[data-testid="stExpander"] summary { font-size:12.5px !important; font-weight:760 !important; color:var(--tt-muted) !important; }\n\n@media (max-width: 760px) {\n  .block-container { padding-left:0.85rem; padding-right:0.85rem; }\n  .topbar { padding:10px 12px; align-items:flex-start; }\n  .topbar-logo { width:52px; height:32px; }\n  .title { font-size:19px; }\n  .subtitle { font-size:12px; }\n  .topbar-role { display:none; }\n  .topbar-meta span { font-size:10px; }\n  .kpi { min-height:auto; padding:11px 12px; }\n  .kpi-value { font-size:21px; }\n  .cockpit-clock { font-size:22px; letter-spacing:1px; }\n}\n\n/* Login */\n.login-panel { border:1px solid var(--tt-border); border-top:4px solid var(--tt-red); border-radius:10px; background:#fff; box-shadow:0 12px 30px rgba(15,23,42,0.07); margin:18px 0 12px 0; }\n.brand-panel { padding:30px 34px 26px 34px; display:flex; flex-direction:column; align-items:center; text-align:center; }\n.login-logo { display:block; width:150px; height:auto; object-fit:contain; margin:0 auto 20px auto; }\n.login-kicker { color:var(--tt-red); font-size:11px; font-weight:850; letter-spacing:1.4px; text-transform:uppercase; }\n.login-heading { color:var(--tt-text); font-size:28px; font-weight:850; margin-top:8px; line-height:1.08; max-width:420px; }\n.login-subtitle { color:var(--tt-muted); font-size:13.5px; line-height:1.5; margin-top:10px; max-width:440px; }\n.login-points { display:flex; flex-wrap:wrap; justify-content:center; gap:8px; margin-top:20px; }\n.login-points span { border:1px solid var(--tt-border); border-radius:999px; background:#f8fafc; color:var(--tt-text); padding:6px 10px; font-size:11.5px; font-weight:800; }\n.form-title { color:var(--tt-text); font-size:24px; font-weight:850; line-height:1.15; }\n.form-subtitle { color:var(--tt-muted); font-size:13px; margin:4px 0 18px 0; }\n.login-footer { color:var(--tt-muted); text-align:center; font-size:11.5px; margin-top:14px; line-height:1.4; }\n.login-panel + div [data-testid="stVerticalBlockBorderWrapper"],\n[data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"] {\n  border:1px solid var(--tt-border) !important;\n  border-radius:10px !important;\n  box-shadow:0 12px 30px rgba(15,23,42,0.07) !important;\n  background:#fff !important;\n}\n[data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"] > div {\n  padding:24px 30px 22px 30px !important;\n}\n\n/* Podium */\n.podium { display:flex; gap:12px; justify-content:center; margin:16px 0; }\n.podium-item { text-align:center; padding:16px 20px; border:1px solid var(--tt-border); border-radius:10px; background:var(--tt-card); min-width:140px; }\n.podium-item.gold { border-color:#fbbf24; border-width:2px; background:linear-gradient(180deg,#fffbeb 0%,#fff 100%); }\n.podium-item.silver { border-color:#94a3b8; border-width:2px; }\n.podium-item.bronze { border-color:#d97706; border-width:2px; }\n.podium-rank { font-size:22px; font-weight:900; color:var(--tt-text); }\n.podium-name { font-size:12px; font-weight:700; color:var(--tt-muted); margin-top:4px; }\n.podium-score { font-size:16px; font-weight:800; color:var(--tt-blue); margin-top:4px; }\n\n/* Progress bar steps */\n.pipeline-step { display:flex; align-items:center; gap:8px; padding:4px 0; font-size:13px; }\n.pipeline-step .step-icon { width:20px; text-align:center; font-weight:800; }\n.pipeline-step.done .step-icon { color:var(--tt-success); }\n.pipeline-step.active .step-icon { color:var(--tt-warning); }\n.pipeline-step.pending .step-icon { color:var(--tt-muted); }\n\n/* Simulation */\n.sim-sidebar-box { border:1px solid var(--tt-border); border-radius:10px; background:var(--tt-card); padding:16px 14px; position:sticky; top:0; }\n.sim-sidebar-label { font-size:10.5px; font-weight:850; letter-spacing:0.8px; text-transform:uppercase; color:var(--tt-muted); margin:14px 0 8px 0; }\n.sim-sidebar-label:first-child { margin-top:0; }\n.sim-divider { height:1px; background:var(--tt-border); margin:14px 0; }\n.sim-empty { text-align:center; padding:48px 24px; border:1px dashed var(--tt-border); border-radius:10px; background:#f8fafc; }\n.sim-empty-title { font-size:16px; font-weight:820; color:var(--tt-text); margin-bottom:8px; }\n.sim-empty-body { font-size:13px; color:var(--tt-muted); line-height:1.55; }\n.sim-hero-time { font-size:32px; font-weight:850; letter-spacing:1px; color:var(--tt-text); line-height:1.1; }\n.sim-hero-sub { font-size:13px; color:var(--tt-muted); margin-top:4px; }\n/* Barre simulation : bouton stations (une ligne) */\nsection.main [data-testid="stPopover"] > button {\n  min-height: 38px !important;\n  max-height: 38px !important;\n  font-size: 0.88rem !important;\n  font-weight: 500 !important;\n  white-space: nowrap !important;\n  overflow: hidden !important;\n  text-overflow: ellipsis !important;\n}\n/* Panneau stations : chips sur une ligne + scroll horizontal */\nsection.main [data-testid="stPopoverBody"] div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {\n  display: flex !important;\n  flex-wrap: nowrap !important;\n  align-items: center !important;\n  max-height: 2.5rem !important;\n  min-height: 2.5rem !important;\n  overflow-x: auto !important;\n  overflow-y: hidden !important;\n  scrollbar-width: thin;\n}\nsection.main [data-testid="stPopoverBody"] div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {\n  flex: 0 0 auto !important;\n  margin: 1px 3px !important;\n  font-size: 0.78rem !important;\n}\nsection.main [data-testid="stPopoverBody"] div[data-testid="stMultiSelect"] div[data-baseweb="menu"] {\n  max-height: 240px !important;\n  overflow-y: auto !important;\n}\n.decision-card .dc-header { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:6px; }\n.decision-card .dc-station { font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.5px; color:var(--tt-muted); }\n\n/* Actions par station (Optimisation) — groupes par mode */\n.station-actions-panel { display:flex; flex-direction:column; gap:14px; margin-top:4px; }\n.sap-group { border:1px solid var(--tt-border); border-radius:8px; overflow:hidden; background:var(--tt-card); }\n.sap-group-title { display:flex; align-items:center; justify-content:space-between; padding:10px 14px; font-size:12px; font-weight:850; letter-spacing:0.6px; text-transform:uppercase; border-bottom:1px solid var(--tt-border); }\n.sap-group-count { font-size:11px; font-weight:700; opacity:0.85; text-transform:none; letter-spacing:0; }\n.sap-group--critique .sap-group-title { color:#b91c1c; background:#fef2f2; border-bottom-color:#fecaca; }\n.sap-group--critique .sap-row { border-left:3px solid #dc2626; }\n.sap-group--critique .sap-station, .sap-group--critique .sap-action, .sap-group--critique .sap-saving { color:#991b1b; }\n.sap-group--attention .sap-group-title { color:#a16207; background:#fffbeb; border-bottom-color:#fde68a; }\n.sap-group--attention .sap-row { border-left:3px solid #eab308; }\n.sap-group--attention .sap-station, .sap-group--attention .sap-action { color:#854d0e; }\n.sap-group--normal .sap-group-title { color:#15803d; background:#f0fdf4; border-bottom-color:#bbf7d0; }\n.sap-group--normal .sap-row { border-left:3px solid #16a34a; }\n.sap-group--normal .sap-station, .sap-group--normal .sap-action, .sap-group--normal .sap-saving { color:#166534; }\n.sap-group--eco .sap-group-title { color:#0e7490; background:#ecfeff; border-bottom-color:#a5f3fc; }\n.sap-group--eco .sap-row { border-left:3px solid #0891b2; }\n.sap-group--eco .sap-station, .sap-group--eco .sap-action, .sap-group--eco .sap-saving { color:#155e75; }\n.sap-row { padding:10px 14px 10px 12px; border-bottom:1px solid var(--tt-border); background:var(--tt-card); }\n.sap-row:last-child { border-bottom:none; }\n.sap-station { font-size:14px; font-weight:850; line-height:1.35; margin-bottom:3px; }\n.sap-action { font-size:13px; font-weight:700; line-height:1.4; margin-bottom:2px; }\n.sap-saving { font-size:12px; font-weight:800; line-height:1.35; opacity:0.92; }\n.sap-gov { font-size:11px; color:var(--tt-muted); font-weight:600; margin-top:2px; }\n.sap-pagination {\n  margin-top: 14px;\n  padding: 10px 14px 10px;\n  border-top: 1px dashed var(--tt-border);\n  font-size: 11px;\n  font-weight: 600;\n  color: var(--tt-muted);\n  text-align: center;\n  line-height: 1.4;\n}\n.sap-pagination-buttons-gap { height: 14px; margin-bottom: 2px; }\n.sap-pagination-nav-wrap { margin-top: 4px; margin-bottom: 22px; }\n\n/* Page Optimisation — bandeau synthèse et cartes graphiques */\n.opt-summary { display:flex; flex-wrap:wrap; gap:10px; margin:4px 0 18px; }\n.opt-summary-item { flex:1 1 160px; min-width:140px; border:1px solid var(--tt-border); border-radius:8px; padding:12px 14px; background:var(--tt-card); }\n.opt-summary-item .osi-label { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.4px; color:var(--tt-muted); margin-bottom:4px; }\n.opt-summary-item .osi-value { font-size:22px; font-weight:850; color:var(--tt-text); line-height:1.2; }\n.opt-summary-item .osi-help { font-size:11px; color:var(--tt-muted); margin-top:4px; font-weight:600; }\n.opt-mode-chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }\n.opt-mode-chip { display:inline-flex; align-items:center; gap:6px; padding:6px 12px; border-radius:999px; font-size:12px; font-weight:800; border:1px solid var(--tt-border); background:var(--tt-card); }\n.opt-mode-chip .omc-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }\n.opt-chart-note { font-size:12px; color:var(--tt-muted); margin:0 0 8px; line-height:1.45; }\n.rl-best-banner { border:1px solid #bbf7d0; background:#f0fdf4; border-radius:8px; padding:10px 14px; margin-bottom:12px; font-size:13px; font-weight:700; color:#166534; }\n</style>\n'

DARK_CSS = '\n<style>\n:root { --tt-bg:#0b1220; --tt-card:#111827; --tt-border:#1f2937; --tt-text:#e5e7eb; --tt-muted:#94a3b8; --tt-blue:#60a5fa; --tt-blue-soft:#3b82f6; }\nhtml, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background:var(--tt-bg) !important; }\n.block-container { background:var(--tt-bg); }\n.topbar { background:linear-gradient(180deg,rgba(248,113,113,0.05) 0%,rgba(0,0,0,0) 100%); border-bottom-color:var(--tt-border); }\n.title, .kpi-value, .info-box .ib-body, .alert .alert-title { color:var(--tt-text) !important; }\n.subtitle, .kpi-label, .kpi-help, .alert .alert-body, .alert .alert-meta { color:var(--tt-muted) !important; }\n.kpi, .alert, .context-badge, .artifact-toolbar, .artifact-card, .artifact-links a, .info-box, [data-testid="stDataFrame"], .nav-card, .anomaly-card, .decision-card, .cockpit-clock, .podium-item { background:var(--tt-card) !important; border-color:var(--tt-border) !important; }\n.section { color:#93c5fd; border-left-color:#93c5fd; }\n.brand { color:#fca5a5; }\n.badge-normal { background:#022c22; color:#86efac; border-color:#14532d; }\n.badge-eco { background:#082f49; color:#7dd3fc; border-color:#0c4a6e; }\n.badge-warning { background:#3a2606; color:#fcd34d; border-color:#78350f; }\n.badge-critical { background:#450a0a; color:#fca5a5; border-color:#7f1d1d; }\n[data-testid="stSidebar"] { background:linear-gradient(180deg,#0b1220 0%,#111827 100%) !important; border-right:1px solid var(--tt-border) !important; }\n[data-testid="stSidebar"] .sb-user { background:#0f172a; border-color:#1f2937; }\n.login-panel, [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"] { background:#111827 !important; border-color:#1f2937 !important; }\n.login-heading, .form-title { color:var(--tt-text); }\n.login-points span { background:#0f172a; border-color:#1f2937; color:#e5e7eb; }\n.sim-sidebar-box, .sim-empty { background:var(--tt-card) !important; border-color:var(--tt-border) !important; }\n.sap-group { background:var(--tt-card) !important; border-color:var(--tt-border) !important; }\n.sap-group--critique .sap-group-title { background:#450a0a !important; color:#fca5a5 !important; border-bottom-color:#7f1d1d !important; }\n.sap-group--critique .sap-station, .sap-group--critique .sap-action, .sap-group--critique .sap-saving { color:#fca5a5 !important; }\n.sap-group--attention .sap-group-title { background:#3a2606 !important; color:#fcd34d !important; }\n.sap-group--attention .sap-station, .sap-group--attention .sap-action { color:#fde68a !important; }\n.sap-group--normal .sap-group-title { background:#022c22 !important; color:#86efac !important; }\n.sap-group--normal .sap-station, .sap-group--normal .sap-action, .sap-group--normal .sap-saving { color:#86efac !important; }\n.sap-group--eco .sap-group-title { background:#082f49 !important; color:#7dd3fc !important; }\n.sap-group--eco .sap-station, .sap-group--eco .sap-action, .sap-group--eco .sap-saving { color:#bae6fd !important; }\n.rl-best-banner { background:#022c22 !important; border-color:#14532d !important; color:#86efac !important; }\n.opt-summary-item, .opt-mode-chip { background:var(--tt-card) !important; border-color:var(--tt-border) !important; }\n.opt-summary-item .osi-value { color:var(--tt-text) !important; }\n.sap-pagination { color:var(--tt-muted) !important; border-top-color:var(--tt-border) !important; }\n</style>\n'
