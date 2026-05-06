"""Theme and aesthetic configuration for the BTS EMS dashboard."""

from __future__ import annotations

# Primary colors
COLOR_PRIMARY = "#c8102e"  # Tunisie Telecom Red
COLOR_SECONDARY = "#1e3a8a" # Dark Blue
COLOR_ACCENT = "#1e40af"
COLOR_BG = "#f8fafc"
COLOR_TEXT = "#0f172a"
COLOR_MUTED = "#64748b"

# Status colors
COLOR_SUCCESS = "#059669"
COLOR_WARNING = "#d97706"
COLOR_DANGER = "#c8102e"
COLOR_INFO = "#3b82f6"

# CSS styles
APP_CSS = """
<style>
.block-container { padding-top: 1.1rem; }
.topbar {
  border-bottom: 2px solid #e2e8f0; padding: 10px 0 14px 0; margin-bottom: 14px;
  display:flex; align-items:center; gap:16px;
}
.topbar-logo {
  width:74px; height:42px; object-fit:contain; flex:0 0 auto;
}
.topbar-content { min-width:0; }
.brand { color:#c8102e; font-size:11px; font-weight:800; letter-spacing:1.5px; text-transform:uppercase; }
.title { color:#0f172a; font-size:23px; font-weight:800; line-height:1.15; }
.subtitle { color:#64748b; font-size:13px; margin-top:3px; }
.kpi {
  border:1px solid #e2e8f0; border-left:4px solid #1e40af; border-radius:6px;
  padding:12px 14px; background:#ffffff; min-height:82px;
}
.kpi.green { border-left-color:#059669; }
.kpi.orange { border-left-color:#d97706; }
.kpi.red { border-left-color:#c8102e; }
.kpi.gray { border-left-color:#64748b; }
.kpi-label { color:#64748b; font-size:11px; font-weight:700; text-transform:uppercase; margin-bottom:5px; }
.kpi-value { color:#0f172a; font-size:24px; font-weight:800; }
.kpi-help { color:#64748b; font-size:12px; margin-top:2px; }
.section {
  color:#1e3a8a; font-size:13px; font-weight:800; text-transform:uppercase;
  border-left:3px solid #1e3a8a; padding-left:9px; margin:20px 0 12px 0;
}
.role-pill {
  display:inline-block; background:#0f172a; color:#f8fafc; padding:4px 10px;
  border-radius:4px; font-size:11px; font-weight:800; text-transform:uppercase;
}
.role-pill.admin { background:#c8102e; }
.login-hero {
  max-width:480px; margin:28px auto 0 auto; padding:30px 34px 28px 34px;
  border:1px solid #e2e8f0; border-top:4px solid #c8102e; border-radius:8px;
  background:#ffffff; box-shadow:0 18px 45px rgba(15, 23, 42, 0.08);
}
.login-logo { display:block; width:156px; height:auto; object-fit:contain; margin:0 auto 18px auto; }
.login-kicker { color:#c8102e; text-align:center; font-size:11px; font-weight:800; letter-spacing:1.4px; text-transform:uppercase; }
.login-heading { color:#0f172a; text-align:center; font-size:26px; font-weight:850; margin-top:6px; line-height:1.15; }
.login-subtitle { color:#64748b; text-align:center; font-size:13px; margin:8px 0 22px 0; }
.login-footer { color:#64748b; text-align:center; font-size:12px; margin-top:16px; }
</style>
"""
