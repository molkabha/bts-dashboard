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
  --tt-bg:#f6f8fb; --tt-card:#ffffff; --tt-border:#e2e8f0;
  --tt-text:#0f172a; --tt-muted:#64748b;
  --tt-success:#059669; --tt-warning:#d97706; --tt-danger:#c8102e;
  --tt-info:#3b82f6; --tt-eco:#0ea5e9; --tt-live:#22c55e;
}
html, body, [data-testid="stAppViewContainer"] { background:var(--tt-bg); font-family:'Inter',sans-serif; }
.block-container { padding-top:0.9rem; padding-bottom:2.5rem; max-width:1500px; }

/* Topbar */
.topbar { border-bottom:1px solid var(--tt-border); padding:12px 0 14px 0; margin-bottom:16px; display:flex; align-items:center; gap:18px; background:linear-gradient(180deg,rgba(200,16,46,0.04) 0%,rgba(200,16,46,0) 100%); }
.topbar-logo { width:74px; height:42px; object-fit:contain; }
.topbar-content { min-width:0; flex:1; }
.brand { color:var(--tt-red); font-size:11px; font-weight:800; letter-spacing:1.6px; text-transform:uppercase; }
.title { color:var(--tt-text); font-size:24px; font-weight:800; line-height:1.2; }
.subtitle { color:var(--tt-muted); font-size:13px; margin-top:3px; }

/* Role pills */
.role-pill { display:inline-block; background:var(--tt-text); color:#f8fafc; padding:4px 10px; border-radius:4px; font-size:11px; font-weight:800; text-transform:uppercase; }
.role-pill.admin { background:var(--tt-red); }

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
.kpi { border:1px solid var(--tt-border); border-left:4px solid var(--tt-blue-soft); border-radius:8px; padding:14px 16px; background:var(--tt-card); min-height:96px; box-shadow:0 1px 2px rgba(15,23,42,0.04); transition:transform .12s ease,box-shadow .12s ease; }
.kpi:hover { transform:translateY(-1px); box-shadow:0 6px 14px rgba(15,23,42,0.07); }
.kpi.green { border-left-color:var(--tt-success); }
.kpi.orange { border-left-color:var(--tt-warning); }
.kpi.red { border-left-color:var(--tt-danger); }
.kpi.blue { border-left-color:var(--tt-blue-soft); }
.kpi.eco { border-left-color:var(--tt-eco); }
.kpi.gray { border-left-color:var(--tt-muted); }
.kpi-row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
.kpi-label { color:var(--tt-muted); font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; }
.kpi-value { color:var(--tt-text); font-size:26px; font-weight:800; margin-top:6px; line-height:1.1; }
.kpi-help { color:var(--tt-muted); font-size:12px; margin-top:4px; }
.kpi-delta { font-size:11px; font-weight:700; padding:2px 8px; border-radius:999px; display:inline-block; margin-top:6px; }
.kpi-delta.up { background:#ecfdf5; color:#047857; }
.kpi-delta.down { background:#fee2e2; color:#991b1b; }

/* Section headings */
.section { color:var(--tt-blue); font-size:13px; font-weight:800; text-transform:uppercase; border-left:3px solid var(--tt-blue); padding-left:10px; margin:22px 0 12px 0; letter-spacing:0.6px; }

/* Alert banners */
.alert { display:flex; gap:12px; align-items:flex-start; border:1px solid var(--tt-border); border-left:4px solid var(--tt-info); background:#fff; border-radius:8px; padding:12px 14px; margin-bottom:8px; box-shadow:0 1px 2px rgba(15,23,42,0.03); }
.alert.success { border-left-color:var(--tt-success); background:#f0fdf4; }
.alert.warning { border-left-color:var(--tt-warning); background:#fffbeb; }
.alert.danger { border-left-color:var(--tt-danger); background:#fef2f2; }
.alert .alert-title { font-weight:800; font-size:13px; margin-bottom:2px; }
.alert .alert-body { font-size:12.5px; color:var(--tt-muted); }
.alert .alert-meta { font-size:11px; color:var(--tt-muted); margin-top:4px; font-weight:600; }

/* Nav cards (Page 0) */
.nav-card { border:1px solid var(--tt-border); border-radius:10px; padding:20px; background:var(--tt-card); cursor:pointer; transition:all .15s ease; box-shadow:0 1px 3px rgba(15,23,42,0.04); }
.nav-card:hover { transform:translateY(-2px); box-shadow:0 8px 20px rgba(15,23,42,0.08); border-color:var(--tt-blue-soft); }
.nav-card .nc-title { font-size:16px; font-weight:800; color:var(--tt-text); margin-bottom:4px; }
.nav-card .nc-value { font-size:28px; font-weight:900; color:var(--tt-blue); margin:8px 0; }
.nav-card .nc-desc { font-size:12px; color:var(--tt-muted); }

/* Anomaly feed cards (Page 3) */
.anomaly-card { border:1px solid var(--tt-border); border-radius:8px; padding:14px 16px; background:var(--tt-card); margin-bottom:8px; transition:all .12s ease; }
.anomaly-card.critique { border-left:4px solid var(--tt-danger); }
.anomaly-card.attention { border-left:4px solid var(--tt-warning); }
.anomaly-card.faible { border-left:4px solid var(--tt-muted); }
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
.cockpit-clock { font-family:'Courier New',monospace; font-size:36px; font-weight:900; color:var(--tt-text); text-align:center; padding:12px; background:var(--tt-card); border:1px solid var(--tt-border); border-radius:8px; letter-spacing:3px; }
.decision-card { border:1px solid var(--tt-border); border-left:4px solid var(--tt-success); border-radius:8px; padding:16px; background:var(--tt-card); }
.decision-card .dc-mode { font-size:18px; font-weight:900; margin-bottom:6px; }
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
[data-testid="stDataFrame"] { border:1px solid var(--tt-border); border-radius:8px; overflow:hidden; }

/* Sidebar */
[data-testid="stSidebar"] { background:linear-gradient(180deg,#ffffff 0%,#f1f5f9 100%); border-right:1px solid var(--tt-border); }
[data-testid="stSidebar"] .sb-section { font-size:10.5px; font-weight:800; text-transform:uppercase; letter-spacing:1px; color:var(--tt-muted); margin:14px 6px 4px 6px; padding-bottom:4px; border-bottom:1px solid var(--tt-border); }
[data-testid="stSidebar"] .sb-user { display:flex; align-items:center; gap:10px; padding:8px 10px; border-radius:8px; background:#fff; border:1px solid var(--tt-border); margin-bottom:8px; }
[data-testid="stSidebar"] .sb-user .sb-avatar { width:34px; height:34px; border-radius:50%; background:var(--tt-red); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:13px; }
[data-testid="stSidebar"] .sb-user .sb-name { font-weight:800; font-size:13px; color:var(--tt-text); line-height:1.2; }
[data-testid="stSidebar"] .sb-user .sb-role { font-size:11px; color:var(--tt-muted); }
.data-freshness { font-size:11px; color:var(--tt-muted); padding:6px 10px; background:#f1f5f9; border-radius:6px; border:1px solid var(--tt-border); margin:8px 0; }

/* Login */
.login-hero { max-width:480px; margin:28px auto 0 auto; padding:30px 34px 28px 34px; border:1px solid var(--tt-border); border-top:4px solid var(--tt-red); border-radius:8px; background:#ffffff; box-shadow:0 18px 45px rgba(15,23,42,0.08); }
.login-logo { display:block; width:156px; height:auto; object-fit:contain; margin:0 auto 18px auto; }
.login-kicker { color:var(--tt-red); text-align:center; font-size:11px; font-weight:800; letter-spacing:1.4px; text-transform:uppercase; }
.login-heading { color:var(--tt-text); text-align:center; font-size:26px; font-weight:850; margin-top:6px; line-height:1.15; }
.login-footer { color:var(--tt-muted); text-align:center; font-size:12px; margin-top:16px; }

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
.kpi, .alert, .info-box, [data-testid="stDataFrame"], .nav-card, .anomaly-card, .decision-card, .cockpit-clock, .podium-item { background:var(--tt-card) !important; border-color:var(--tt-border) !important; }
.section { color:#93c5fd; border-left-color:#93c5fd; }
.brand { color:#fca5a5; }
.badge-normal { background:#022c22; color:#86efac; border-color:#14532d; }
.badge-eco { background:#082f49; color:#7dd3fc; border-color:#0c4a6e; }
.badge-warning { background:#3a2606; color:#fcd34d; border-color:#78350f; }
.badge-critical { background:#450a0a; color:#fca5a5; border-color:#7f1d1d; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0b1220 0%,#111827 100%) !important; border-right:1px solid var(--tt-border) !important; }
[data-testid="stSidebar"] .sb-user { background:#0f172a; border-color:#1f2937; }
.login-hero { background:#111827; border-color:#1f2937; }
.login-heading { color:var(--tt-text); }
</style>
"""
