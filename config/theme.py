"""Theme and aesthetic configuration for the BTS EMS dashboard."""

from __future__ import annotations

COLOR_PRIMARY = "#c8102e"
COLOR_SECONDARY = "#1e3a8a"
COLOR_ACCENT = "#1e40af"
COLOR_BG = "#f8fafc"
COLOR_TEXT = "#0f172a"
COLOR_MUTED = "#64748b"
COLOR_SUCCESS = "#059669"
COLOR_WARNING = "#d97706"
COLOR_DANGER = "#c8102e"
COLOR_INFO = "#3b82f6"
COLOR_ECO = "#0ea5e9"
COLOR_LIVE = "#22c55e"

PLOTLY_LIGHT = {
    "layout": {
        "font": {"family": "Inter, Segoe UI, Arial", "color": "#0f172a"},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": ["#c8102e", "#1e3a8a", "#0ea5e9", "#059669", "#d97706", "#7c3aed", "#0891b2"],
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
        "colorway": ["#f87171", "#60a5fa", "#38bdf8", "#34d399", "#fbbf24", "#a78bfa", "#22d3ee"],
        "xaxis": {"gridcolor": "#1f2937", "zerolinecolor": "#1f2937"},
        "yaxis": {"gridcolor": "#1f2937", "zerolinecolor": "#1f2937"},
        "margin": {"l": 40, "r": 20, "t": 30, "b": 40},
        "legend": {"bgcolor": "rgba(15,23,42,0.6)", "bordercolor": "#334155"},
    }
}

MODE_COLORS = {
    "ECO": "#059669",
    "NORMAL": "#2563eb",
    "ATTENTION": "#d97706",
    "CRITIQUE": "#c8102e",
}

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
:root {
  --tt-red:#c8102e; --tt-red-dark:#a30c25;
  --tt-blue:#1e3a8a; --tt-blue-soft:#1e40af;
  --tt-bg:#f7f9fc; --tt-card:#ffffff; --tt-border:#dbe3ee;
  --tt-text:#0f172a; --tt-muted:#64748b;
  --tt-success:#059669; --tt-warning:#d97706; --tt-danger:#c8102e;
  --tt-info:#3b82f6; --tt-eco:#0ea5e9; --tt-live:#22c55e;
}
html, body, [data-testid="stAppViewContainer"] { background:var(--tt-bg); font-family:'Inter','Segoe UI',Arial,sans-serif; }
.block-container { padding-top:0.75rem; padding-bottom:2.2rem; max-width:1360px; }

/* Streamlit base cleanup */
[data-testid="stHeader"] { background:transparent; }
div[data-testid="stVerticalBlock"] { gap:0.75rem; }
.stButton > button, .stDownloadButton > button, [data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"] { border-radius:6px !important; font-weight:750 !important; min-height:38px; }
.stSelectbox label, .stMultiSelect label, .stDateInput label, .stSlider label,
.stRadio label, .stTextInput label, .stFileUploader label {
  color:var(--tt-text) !important; font-size:12px !important; font-weight:750 !important;
}

/* Topbar */
.topbar { border:1px solid var(--tt-border); border-left:4px solid var(--tt-red); padding:12px 16px; margin-bottom:14px; display:flex; align-items:center; gap:14px; background:var(--tt-card); border-radius:8px; box-shadow:0 1px 2px rgba(15,23,42,0.04); }
.topbar-logo { width:66px; height:38px; object-fit:contain; }
.topbar-content { min-width:0; flex:1; }
.brand { color:var(--tt-red); font-size:10.5px; font-weight:800; letter-spacing:1.2px; text-transform:uppercase; }
.title { color:var(--tt-text); font-size:22px; font-weight:820; line-height:1.18; }
.subtitle { color:var(--tt-muted); font-size:12.5px; margin-top:2px; }
.topbar-role { text-align:right; margin-top:2px; flex:0 0 auto; }
.topbar-meta { display:flex; flex-wrap:wrap; gap:8px; margin-top:9px; }
.topbar-meta span { display:inline-flex; gap:4px; align-items:center; color:var(--tt-muted); background:#f8fafc; border:1px solid var(--tt-border); border-radius:999px; padding:3px 8px; font-size:10.5px; line-height:1.3; max-width:100%; }
.topbar-meta strong { color:var(--tt-text); font-weight:800; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px; }

/* Role pills */
.role-pill { display:inline-block; background:#f1f5f9; color:var(--tt-text); border:1px solid var(--tt-border); padding:4px 9px; border-radius:999px; font-size:10.5px; font-weight:800; text-transform:uppercase; }
.role-pill.admin { background:var(--tt-red); color:#fff; border-color:var(--tt-red); }

/* Badges */
.badge { display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px; font-size:11px; font-weight:800; letter-spacing:0.6px; text-transform:uppercase; border:1px solid transparent; }
.badge-normal { background:#ecfdf5; color:#047857; border-color:#a7f3d0; }
.badge-eco { background:#e0f2fe; color:#0369a1; border-color:#bae6fd; }
.badge-warning { background:#fef3c7; color:#92400e; border-color:#fde68a; }
.badge-critical { background:#fee2e2; color:#991b1b; border-color:#fecaca; }
.badge-info { background:#eff6ff; color:#1d4ed8; border-color:#bfdbfe; }
.badge-muted { background:#f1f5f9; color:#475569; border-color:#e2e8f0; }
.badge-live { background:#022c22; color:#bbf7d0; border-color:#16a34a; animation:live-pulse 1.6s ease-in-out infinite; }
@keyframes live-pulse { 0%,100%{box-shadow:0 0 0 0 rgba(34,197,94,0.55);} 50%{box-shadow:0 0 0 8px rgba(34,197,94,0);} }
.badge .dot { display:inline-block; width:6px; height:6px; border-radius:50%; background:currentColor; }

/* KPI cards */
.kpi { border:1px solid var(--tt-border); border-left:3px solid var(--tt-blue-soft); border-radius:6px; padding:12px 14px; background:var(--tt-card); min-height:84px; box-shadow:0 1px 2px rgba(15,23,42,0.035); transition:border-color .12s ease,box-shadow .12s ease; }
.kpi:hover { box-shadow:0 4px 10px rgba(15,23,42,0.055); border-color:#cbd5e1; }
.kpi.green { border-left-color:var(--tt-success); }
.kpi.orange { border-left-color:var(--tt-warning); }
.kpi.red { border-left-color:var(--tt-danger); }
.kpi.blue { border-left-color:var(--tt-blue-soft); }
.kpi.eco { border-left-color:var(--tt-eco); }
.kpi.gray { border-left-color:var(--tt-muted); }
.kpi-row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
.kpi-label { color:var(--tt-muted); font-size:10.5px; font-weight:750; text-transform:uppercase; letter-spacing:0.35px; }
.kpi-value { color:var(--tt-text); font-size:24px; font-weight:820; margin-top:5px; line-height:1.08; }
.kpi-help { color:var(--tt-muted); font-size:11.5px; margin-top:4px; }
.kpi-delta { font-size:11px; font-weight:700; padding:2px 8px; border-radius:999px; display:inline-block; margin-top:6px; }
.kpi-delta.up { background:#ecfdf5; color:#047857; }
.kpi-delta.down { background:#fee2e2; color:#991b1b; }

/* Section headings */
.section { color:var(--tt-text); font-size:13px; font-weight:820; text-transform:none; border-left:0; padding-left:0; margin:20px 0 8px 0; letter-spacing:0; }
.section::after { content:""; display:block; width:100%; height:1px; background:var(--tt-border); margin-top:8px; }

/* Alert banners */
.alert { display:flex; gap:12px; align-items:flex-start; border:1px solid var(--tt-border); border-left:3px solid var(--tt-info); background:#fff; border-radius:6px; padding:11px 13px; margin-bottom:8px; box-shadow:0 1px 2px rgba(15,23,42,0.025); }
.alert.success { border-left-color:var(--tt-success); background:#f0fdf4; }
.alert.warning { border-left-color:var(--tt-warning); background:#fffbeb; }
.alert.danger { border-left-color:var(--tt-danger); background:#fef2f2; }
.alert .alert-title { font-weight:800; font-size:13px; margin-bottom:2px; }
.alert .alert-body { font-size:12.5px; color:var(--tt-muted); }
.alert .alert-meta { font-size:11px; color:var(--tt-muted); margin-top:4px; font-weight:600; }

.summary-strip { border:1px solid var(--tt-border); border-left:3px solid var(--tt-blue-soft); background:#fff; border-radius:6px; padding:11px 13px; color:var(--tt-text); font-size:13.5px; font-weight:760; line-height:1.45; margin-bottom:8px; }

/* Filter and artefact context */
.context-badge { display:flex; justify-content:space-between; gap:12px; align-items:center; border:1px solid var(--tt-border); border-left:4px solid var(--tt-info); background:var(--tt-card); border-radius:8px; padding:10px 12px; margin:8px 0; font-size:12px; color:var(--tt-muted); }
.context-badge strong { color:var(--tt-text); font-size:13px; }
.context-badge.success { border-left-color:var(--tt-success); }
.context-badge.warning { border-left-color:var(--tt-warning); }
.artifact-toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; border:1px solid var(--tt-border); background:var(--tt-card); border-radius:8px; padding:12px 14px; margin-bottom:12px; }
.artifact-title { color:var(--tt-text); font-size:14px; font-weight:850; }
.artifact-subtitle { color:var(--tt-muted); font-size:12px; margin-top:3px; }
.artifact-scope { flex:0 0 auto; padding:5px 10px; border-radius:999px; border:1px solid var(--tt-border); font-size:11px; font-weight:850; text-transform:uppercase; color:var(--tt-muted); background:#f8fafc; }
.artifact-scope.station { color:#047857; border-color:#a7f3d0; background:#ecfdf5; }
.artifact-card { border:1px solid var(--tt-border); border-radius:8px; background:var(--tt-card); padding:10px; margin-bottom:12px; box-shadow:0 1px 2px rgba(15,23,42,0.04); }
.artifact-caption { display:flex; flex-direction:column; gap:3px; padding:8px 2px 0 2px; }
.artifact-caption strong { color:var(--tt-text); font-size:13px; }
.artifact-caption span { color:var(--tt-muted); font-size:11.5px; line-height:1.35; }
.artifact-links { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }
.artifact-links a { color:var(--tt-blue); border:1px solid var(--tt-border); background:var(--tt-card); padding:5px 9px; border-radius:6px; font-size:12px; font-weight:700; text-decoration:none; }
.artifact-links a:hover { border-color:var(--tt-blue-soft); color:var(--tt-red); }

/* Nav cards (Page 0) */
.nav-card { border:1px solid var(--tt-border); border-radius:6px; padding:16px; background:var(--tt-card); cursor:pointer; transition:box-shadow .15s ease,border-color .15s ease; box-shadow:0 1px 2px rgba(15,23,42,0.035); }
.nav-card:hover { box-shadow:0 5px 14px rgba(15,23,42,0.065); border-color:var(--tt-blue-soft); }
.nav-card .nc-title { font-size:14px; font-weight:820; color:var(--tt-text); margin-bottom:3px; }
.nav-card .nc-value { font-size:24px; font-weight:850; color:var(--tt-blue); margin:7px 0; }
.nav-card .nc-desc { font-size:12px; color:var(--tt-muted); }

/* Anomaly feed cards (Page 3) */
.anomaly-card { border:1px solid var(--tt-border); border-radius:6px; padding:12px 14px; background:var(--tt-card); margin-bottom:8px; transition:all .12s ease; }
.anomaly-card.critique { border-left:3px solid var(--tt-danger); }
.anomaly-card.attention { border-left:3px solid var(--tt-warning); }
.anomaly-card.faible { border-left:3px solid var(--tt-muted); }
.anomaly-card.traite { opacity:0.55; background:#f8fafc; }
.anomaly-card .ac-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }
.anomaly-card .ac-badge { font-size:11px; font-weight:800; text-transform:uppercase; padding:2px 8px; border-radius:4px; }
.anomaly-card .ac-badge.critique { background:#fee2e2; color:#991b1b; }
.anomaly-card .ac-badge.attention { background:#fef3c7; color:#92400e; }
.anomaly-card .ac-badge.faible { background:#f1f5f9; color:#475569; }
.anomaly-card .ac-station { font-weight:800; font-size:14px; color:var(--tt-text); }
.anomaly-card .ac-detail { font-size:12.5px; color:var(--tt-muted); line-height:1.5; }
.anomaly-card .ac-meta { font-size:11px; color:var(--tt-muted); font-weight:600; margin-top:6px; }

/* Cockpit (Page 5) */
.cockpit-clock { font-family:'Courier New',monospace; font-size:28px; font-weight:850; color:var(--tt-text); text-align:center; padding:10px; background:var(--tt-card); border:1px solid var(--tt-border); border-radius:6px; letter-spacing:2px; }
.decision-card { border:1px solid var(--tt-border); border-left:3px solid var(--tt-success); border-radius:6px; padding:13px 14px; background:var(--tt-card); margin-bottom:8px; }
.decision-card .dc-mode { font-size:16px; font-weight:850; margin-bottom:6px; }
.decision-card .dc-action { font-size:13px; font-weight:700; color:var(--tt-text); margin-bottom:4px; }
.decision-card .dc-reason { font-size:12px; color:var(--tt-muted); line-height:1.5; }
.decision-card .dc-saving { font-size:13px; font-weight:800; color:var(--tt-success); margin-top:8px; }

/* Live indicator */
.live-indicator { display:inline-flex; align-items:center; gap:8px; padding:6px 12px; border-radius:999px; background:#022c22; color:#bbf7d0; font-weight:800; font-size:12px; letter-spacing:1px; text-transform:uppercase; border:1px solid #14532d; }
.live-indicator .live-dot { width:8px; height:8px; border-radius:50%; background:#22c55e; box-shadow:0 0 0 0 rgba(34,197,94,0.55); animation:live-pulse 1.6s ease-in-out infinite; }

/* Info box */
.info-box { border:1px solid var(--tt-border); border-radius:8px; padding:12px 14px; background:linear-gradient(180deg,#f8fafc 0%,#ffffff 100%); }
.info-box .ib-title { font-weight:800; font-size:12px; color:var(--tt-blue); text-transform:uppercase; letter-spacing:0.6px; }
.info-box .ib-body { font-size:13px; color:var(--tt-text); margin-top:4px; line-height:1.5; }

/* Tables */
[data-testid="stDataFrame"] { border:1px solid var(--tt-border); border-radius:6px; overflow:hidden; }

/* Sidebar */
[data-testid="stSidebar"] { background:#ffffff; border-right:1px solid var(--tt-border); }
[data-testid="stSidebar"] .sb-section { font-size:10.5px; font-weight:820; text-transform:uppercase; letter-spacing:0.8px; color:var(--tt-muted); margin:13px 6px 4px 6px; padding-bottom:4px; border-bottom:1px solid var(--tt-border); }
[data-testid="stSidebar"] .sb-user { display:flex; align-items:center; gap:10px; padding:8px 10px; border-radius:6px; background:#f8fafc; border:1px solid var(--tt-border); margin-bottom:8px; }
[data-testid="stSidebar"] .sb-user .sb-avatar { width:34px; height:34px; border-radius:50%; background:var(--tt-red); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:13px; }
[data-testid="stSidebar"] .sb-user .sb-name { font-weight:800; font-size:13px; color:var(--tt-text); line-height:1.2; }
[data-testid="stSidebar"] .sb-user .sb-role { font-size:11px; color:var(--tt-muted); }
.data-freshness { font-size:11px; color:var(--tt-muted); padding:6px 10px; background:#f1f5f9; border-radius:6px; border:1px solid var(--tt-border); margin:8px 0; }
[data-testid="stSidebar"] [data-baseweb="tag"] { max-width:100%; }
[data-testid="stSidebar"] [data-baseweb="select"] { font-size:12px; }

/* Expanders: keep technical content secondary */
[data-testid="stExpander"] { border:1px solid var(--tt-border) !important; border-radius:6px !important; background:var(--tt-card) !important; box-shadow:none !important; }
[data-testid="stExpander"] summary { font-size:12.5px !important; font-weight:760 !important; color:var(--tt-muted) !important; }

@media (max-width: 760px) {
  .block-container { padding-left:0.85rem; padding-right:0.85rem; }
  .topbar { padding:10px 12px; align-items:flex-start; }
  .topbar-logo { width:52px; height:32px; }
  .title { font-size:19px; }
  .subtitle { font-size:12px; }
  .topbar-role { display:none; }
  .topbar-meta span { font-size:10px; }
  .kpi { min-height:auto; padding:11px 12px; }
  .kpi-value { font-size:21px; }
  .cockpit-clock { font-size:22px; letter-spacing:1px; }
}

/* Login */
.login-panel { min-height:390px; border:1px solid var(--tt-border); border-radius:10px; background:#fff; box-shadow:0 12px 30px rgba(15,23,42,0.07); }
.brand-panel { padding:34px 36px; border-left:4px solid var(--tt-red); display:flex; flex-direction:column; justify-content:center; }
.login-logo { display:block; width:150px; height:auto; object-fit:contain; margin:0 0 24px 0; }
.login-kicker { color:var(--tt-red); font-size:11px; font-weight:850; letter-spacing:1.4px; text-transform:uppercase; }
.login-heading { color:var(--tt-text); font-size:30px; font-weight:850; margin-top:8px; line-height:1.08; max-width:420px; }
.login-subtitle { color:var(--tt-muted); font-size:14px; line-height:1.55; margin-top:12px; max-width:440px; }
.login-points { display:flex; flex-wrap:wrap; gap:8px; margin-top:24px; }
.login-points span { border:1px solid var(--tt-border); border-radius:999px; background:#f8fafc; color:var(--tt-text); padding:6px 10px; font-size:11.5px; font-weight:800; }
.form-title { color:var(--tt-text); font-size:24px; font-weight:850; line-height:1.15; }
.form-subtitle { color:var(--tt-muted); font-size:13px; margin:4px 0 18px 0; }
.login-footer { color:var(--tt-muted); text-align:center; font-size:11.5px; margin-top:14px; line-height:1.4; }
.login-panel + div [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"] {
  border:1px solid var(--tt-border) !important;
  border-radius:10px !important;
  box-shadow:0 12px 30px rgba(15,23,42,0.07) !important;
  background:#fff !important;
}
[data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"] > div {
  padding:28px 30px 22px 30px !important;
}

/* Podium */
.podium { display:flex; gap:12px; justify-content:center; margin:16px 0; }
.podium-item { text-align:center; padding:16px 20px; border:1px solid var(--tt-border); border-radius:10px; background:var(--tt-card); min-width:140px; }
.podium-item.gold { border-color:#fbbf24; border-width:2px; background:linear-gradient(180deg,#fffbeb 0%,#fff 100%); }
.podium-item.silver { border-color:#94a3b8; border-width:2px; }
.podium-item.bronze { border-color:#d97706; border-width:2px; }
.podium-rank { font-size:22px; font-weight:900; color:var(--tt-text); }
.podium-name { font-size:12px; font-weight:700; color:var(--tt-muted); margin-top:4px; }
.podium-score { font-size:16px; font-weight:800; color:var(--tt-blue); margin-top:4px; }

/* Progress bar steps */
.pipeline-step { display:flex; align-items:center; gap:8px; padding:4px 0; font-size:13px; }
.pipeline-step .step-icon { width:20px; text-align:center; font-weight:800; }
.pipeline-step.done .step-icon { color:var(--tt-success); }
.pipeline-step.active .step-icon { color:var(--tt-warning); }
.pipeline-step.pending .step-icon { color:var(--tt-muted); }
</style>
"""

DARK_CSS = """
<style>
:root { --tt-bg:#0b1220; --tt-card:#111827; --tt-border:#1f2937; --tt-text:#e5e7eb; --tt-muted:#94a3b8; --tt-blue:#60a5fa; --tt-blue-soft:#3b82f6; }
html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background:var(--tt-bg) !important; }
.block-container { background:var(--tt-bg); }
.topbar { background:linear-gradient(180deg,rgba(248,113,113,0.05) 0%,rgba(0,0,0,0) 100%); border-bottom-color:var(--tt-border); }
.title, .kpi-value, .info-box .ib-body, .alert .alert-title { color:var(--tt-text) !important; }
.subtitle, .kpi-label, .kpi-help, .alert .alert-body, .alert .alert-meta { color:var(--tt-muted) !important; }
.kpi, .alert, .context-badge, .artifact-toolbar, .artifact-card, .artifact-links a, .info-box, [data-testid="stDataFrame"], .nav-card, .anomaly-card, .decision-card, .cockpit-clock, .podium-item { background:var(--tt-card) !important; border-color:var(--tt-border) !important; }
.section { color:#93c5fd; border-left-color:#93c5fd; }
.brand { color:#fca5a5; }
.badge-normal { background:#022c22; color:#86efac; border-color:#14532d; }
.badge-eco { background:#082f49; color:#7dd3fc; border-color:#0c4a6e; }
.badge-warning { background:#3a2606; color:#fcd34d; border-color:#78350f; }
.badge-critical { background:#450a0a; color:#fca5a5; border-color:#7f1d1d; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0b1220 0%,#111827 100%) !important; border-right:1px solid var(--tt-border) !important; }
[data-testid="stSidebar"] .sb-user { background:#0f172a; border-color:#1f2937; }
.login-panel, [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"] { background:#111827 !important; border-color:#1f2937 !important; }
.login-heading, .form-title { color:var(--tt-text); }
.login-points span { background:#0f172a; border-color:#1f2937; color:#e5e7eb; }
</style>
"""
