from __future__ import annotations

import html
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import (
    PLOTLY_DARK,
    PLOTLY_LIGHT,
    mode_color,
    mode_color_discrete_map,
    mode_kpi_class,
    normalize_mode_key,
)
from security.middleware import security_middleware
from services.calendar_tn import (
    SCENARIO_PRESETS,
    calendar_label,
    resolve_preset_date,
    scenario_timestamps,
)
from services.data_service import engineer_assigned_stations, init_db
from services.nb_metrics import effective_economie_kwh, harmonize_nb3_economies
from services.nb_replay import load_replay_source, replay_batch, replay_timestamps
from services.simulation_events import (
    classify_tick_rows,
    events_to_dataframe,
    filter_events,
    merge_event_log,
    persist_alert_ack,
)
from services.synthetic_bts import (
    generate_period,
    hourly_snapshot,
    replay_historical_hour,
)
from ui.components import header, kpi_card
from ui.formatting import display_text, resolve_row_action
from ui.page_helpers import get_station_map_data, load_dashboard_df, mode_explanation
from ui.utils import active_filter_label, download_df_button

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None


def _num(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def _station_options(role: str) -> list[str]:
    df = load_dashboard_df(["station_id"])
    if df.empty or "station_id" not in df.columns:
        if role == "admin":
            from services.data_service import available_stations
            return available_stations()
        return engineer_assigned_stations()
    stations = sorted(df["station_id"].dropna().astype(str).unique().tolist())
    if role != "admin":
        assigned = {str(s) for s in engineer_assigned_stations()}
        stations = [s for s in stations if s in assigned]
    return stations


def _replay_window(source_df, sim_mode, sim_base_date, start_hour):
    on_date = None
    start_dt = None
    if sim_mode == "Une journee":
        on_date = datetime.combine(sim_base_date, datetime.min.time())
        start_dt = on_date.replace(hour=start_hour)
    elif isinstance(source_df, pd.DataFrame) and "timestamp" in source_df.columns:
        ts = pd.to_datetime(source_df["timestamp"], errors="coerce").dropna()
        if not ts.empty:
            start_dt = ts.min().to_pydatetime()
    return on_date, start_dt


def _total_ticks(data_source, source_df, selected_stations, sim_mode, sim_base_date, start_hour, num_days):
    if data_source == "Scenario":
        return len(scenario_timestamps(sim_base_date, start_hour, num_days))
    on_date, start_dt = _replay_window(source_df, sim_mode, sim_base_date, start_hour)
    return len(replay_timestamps(
        source_df, selected_stations, start_dt,
        on_date=on_date if sim_mode == "Une journee" else None,
    ))


def _sensitivity() -> float:
    return float(st.session_state.get("sim_anomaly_sensitivity", 1.0))


def _record_events(processed: pd.DataFrame) -> None:
    alerts, decisions = classify_tick_rows(processed, anomaly_sensitivity=_sensitivity())
    st.session_state["sim_alerts"] = merge_event_log(st.session_state.get("sim_alerts", []), alerts)
    st.session_state["sim_decisions"] = merge_event_log(st.session_state.get("sim_decisions", []), decisions)


def _append_sim_data(processed: pd.DataFrame, max_rows: int) -> None:
    processed = harmonize_nb3_economies(processed)
    existing = st.session_state.get("sim_data", pd.DataFrame())
    if isinstance(existing, pd.DataFrame) and not existing.empty:
        st.session_state["sim_data"] = pd.concat([existing, processed], ignore_index=True).tail(max_rows)
    else:
        st.session_state["sim_data"] = processed


def _advance_scenario(selected_stations, sim_base_date, start_hour, tick, steps, num_days):
    frames = []
    for step in range(max(1, steps)):
        stamps = scenario_timestamps(sim_base_date, start_hour, num_days)
        idx = tick + step
        if idx >= len(stamps):
            break
        ts = stamps[idx]
        batch = hourly_snapshot(
            ts.date(), ts.hour, selected_stations,
            anomaly_sensitivity=_sensitivity(),
        )
        if not batch.empty:
            frames.append(batch)
    if not frames:
        return pd.DataFrame(), 0
    return pd.concat(frames, ignore_index=True), len(frames)


def _advance_replay(source_df, selected_stations, sim_mode, sim_base_date, start_hour, tick, steps):
    on_date, start_dt = _replay_window(source_df, sim_mode, sim_base_date, start_hour)
    on_date_arg = on_date if sim_mode == "Une journee" else None
    frames = []
    current_tick = tick
    for _ in range(max(1, steps)):
        processed, _ = replay_batch(
            source_df, selected_stations, current_tick,
            start_dt=start_dt, on_date=on_date_arg,
        )
        if processed.empty:
            break
        frames.append(processed)
        current_tick += 1
    if not frames:
        return pd.DataFrame(), 0
    return pd.concat(frames, ignore_index=True), len(frames)


def _advance_simulation(data_source, source_df, selected_stations, sim_mode, sim_base_date, start_hour, steps, num_days):
    tick = int(st.session_state.get("sim_tick", 0))
    max_rows = max(72, 24 * num_days) * len(selected_stations)

    if data_source == "Scenario":
        stamps = scenario_timestamps(sim_base_date, start_hour, num_days)
        if tick >= len(stamps):
            st.session_state["sim_running"] = False
            return False
        processed, n = _advance_scenario(selected_stations, sim_base_date, start_hour, tick, steps, num_days)
        if processed.empty:
            st.session_state["sim_running"] = False
            return False
        _append_sim_data(processed, max_rows)
        _record_events(processed)
        st.session_state["sim_tick"] = tick + max(1, n)
        return True

    on_date, start_dt = _replay_window(source_df, sim_mode, sim_base_date, start_hour)
    on_date_arg = on_date if sim_mode == "Une journee" else None
    stamps = replay_timestamps(source_df, selected_stations, start_dt, on_date=on_date_arg)
    if tick >= len(stamps):
        st.session_state["sim_running"] = False
        return False
    processed, n = _advance_replay(source_df, selected_stations, sim_mode, sim_base_date, start_hour, tick, steps)
    if processed.empty:
        st.session_state["sim_running"] = False
        return False
    _append_sim_data(processed, max_rows)
    _record_events(processed)
    st.session_state["sim_tick"] = tick + max(1, n)
    return True


def _run_full_period(data_source, source_df, selected_stations, sim_mode, sim_base_date, start_hour, num_days):
    if data_source == "Scenario":
        processed = generate_period(
            sim_base_date, start_hour, num_days, selected_stations,
            anomaly_sensitivity=_sensitivity(),
        )
    else:
        frames = []
        on_date, start_dt = _replay_window(source_df, sim_mode, sim_base_date, start_hour)
        stamps = replay_timestamps(
            source_df, selected_stations, start_dt,
            on_date=on_date if sim_mode == "Une journee" else None,
        )
        for i in range(len(stamps)):
            batch, _ = replay_batch(
                source_df, selected_stations, i,
                start_dt=start_dt, on_date=on_date if sim_mode == "Une journee" else None,
            )
            if not batch.empty:
                frames.append(batch)
        processed = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    if processed.empty:
        return
    max_rows = max(72, 24 * num_days) * len(selected_stations)
    st.session_state["sim_data"] = harmonize_nb3_economies(processed).tail(max_rows)
    st.session_state["sim_tick"] = len(processed["timestamp"].drop_duplicates()) if "timestamp" in processed.columns else 0
    st.session_state["sim_running"] = False
    _record_events(processed)


def _replay_source_df() -> pd.DataFrame:
    cached = st.session_state.get("sim_source_df")
    if isinstance(cached, pd.DataFrame):
        return cached
    source_df = load_replay_source()
    st.session_state["sim_source_df"] = source_df
    return source_df


def _row_by_station(latest_all: pd.DataFrame, station_id: str) -> pd.Series:
    if latest_all.empty:
        return pd.Series(dtype=object)
    hit = latest_all[latest_all["station_id"].astype(str) == str(station_id)]
    if hit.empty:
        return _primary_row(latest_all)
    return hit.iloc[0]


def _primary_row(latest_all: pd.DataFrame) -> pd.Series:
    if latest_all.empty:
        return pd.Series(dtype=object)
    if len(latest_all) == 1:
        return latest_all.iloc[0]
    prio = {"CRITIQUE": 0, "ATTENTION": 1, "NORMAL": 2, "ECO": 3}
    work = latest_all.copy()
    if "mode_operation" in work.columns:
        work["_p"] = work["mode_operation"].astype(str).map(lambda m: prio.get(m, 9))
        work = work.sort_values("_p")
    return work.iloc[0]


def _status_banner(latest_ts, sim_base_date: date, n_alerts: int, n_decisions: int) -> None:
    hour = pd.Timestamp(latest_ts).hour if latest_ts is not None else 0
    st.markdown(
        f"**{pd.Timestamp(latest_ts).strftime('%Y-%m-%d %H:%M') if latest_ts is not None else '—'}** "
        f"| {calendar_label(sim_base_date)} "
        f"| Alertes: **{n_alerts}** | Decisions: **{n_decisions}**"
    )


def _render_station_table(latest_all: pd.DataFrame) -> None:
    if latest_all.empty:
        return
    work = latest_all.copy()
    work["Mode"] = work.get("mode_operation", "NORMAL").astype(str)
    work["Action"] = work.apply(lambda r: resolve_row_action(r, prefer_rl=True), axis=1)
    work["Conso"] = _num(work, "consommation_kwh", 0).round(2)
    work["QoS"] = _num(work, "score_qos", 0).round(2)
    work["Anomalie"] = _num(work, "anomalie_score_ensemble", 0).round(2)
    cols = ["station_id", "Mode", "Conso", "QoS", "Anomalie", "Action"]
    show = work[[c for c in cols if c in work.columns]]
    st.dataframe(show, width="stretch", hide_index=True, height=min(42 + 35 * len(show), 280))


def _render_alerts_panel(current_ts) -> None:
    st.subheader("Alertes")
    raw = st.session_state.get("sim_alerts", [])
    f1, f2, f3 = st.columns(3)
    stations = ["Toutes"] + sorted({str(e.get("station_id")) for e in raw if e.get("station_id")})
    severities = ["Toutes", "ATTENTION", "CRITIQUE"]
    types = ["Toutes", "anomalie_sans_action", "qos_risque"]
    with f1:
        st_sel = st.selectbox("Station", stations, key="sim_alert_station")
    with f2:
        sev_sel = st.selectbox("Severite", severities, key="sim_alert_sev")
    with f3:
        hour_only = st.checkbox("Heure courante", key="sim_alert_hour_only")

    type_sel = st.selectbox("Type", types, key="sim_alert_type")
    filtered = filter_events(
        raw,
        station=st_sel,
        severity=sev_sel,
        event_type=type_sel,
        current_hour_only=hour_only,
        current_ts=pd.Timestamp(current_ts) if current_ts is not None else None,
    )

    acked = st.session_state.get("sim_ack_refs", set())
    pending = [e for e in filtered if e.get("alert_ref") not in acked][:8]
    for item in pending:
        sev = str(item.get("severity", ""))
        color = "#dc2626" if sev == "CRITIQUE" else "#ca8a04"
        st.markdown(
            f'<div style="border-left:4px solid {color};padding:6px 8px;margin-bottom:6px;">'
            f'<small>{html.escape(str(item.get("station_id","")))} — {html.escape(str(item.get("timestamp",""))[:19])}</small><br>'
            f'{html.escape(str(item.get("message","")))}</div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        ref = item.get("alert_ref", "")
        with c1:
            if st.button("Acquitter", key=f"ack_ok_{ref}", use_container_width=True):
                user = st.session_state.get("username") or st.session_state.get("user", "engineer")
                init_db()
                persist_alert_ack(user, str(item.get("station_id")), ref, "acquitte")
                acked.add(ref)
                st.session_state["sim_ack_refs"] = acked
                st.rerun()
        with c2:
            if st.button("Faux positif", key=f"ack_fp_{ref}", use_container_width=True):
                user = st.session_state.get("username") or st.session_state.get("user", "engineer")
                init_db()
                persist_alert_ack(user, str(item.get("station_id")), ref, "faux_positif")
                acked.add(ref)
                st.session_state["sim_ack_refs"] = acked
                st.rerun()

    df = events_to_dataframe(filtered)
    if df.empty:
        st.caption("Aucune alerte.")
        return
    show = df[["timestamp", "station_id", "severity", "type", "message"]].copy()
    show["timestamp"] = show["timestamp"].astype(str).str[:19]
    st.dataframe(show, width="stretch", hide_index=True, height=180)
    download_df_button(show, "alertes_simulation.csv", "Exporter alertes")


def _render_decisions_panel(current_ts) -> None:
    st.subheader("Decisions")
    raw = st.session_state.get("sim_decisions", [])
    f1, f2 = st.columns(2)
    stations = ["Toutes"] + sorted({str(e.get("station_id")) for e in raw if e.get("station_id")})
    with f1:
        st_sel = st.selectbox("Station", stations, key="sim_dec_station")
    with f2:
        hour_only = st.checkbox("Heure courante", key="sim_dec_hour_only")

    filtered = filter_events(
        raw,
        station=st_sel,
        current_hour_only=hour_only,
        current_ts=pd.Timestamp(current_ts) if current_ts is not None else None,
    )
    df = events_to_dataframe(filtered)
    if df.empty:
        st.caption("Aucune decision.")
        return
    show = df[["timestamp", "station_id", "mode", "action", "economie_kwh", "message"]].copy()
    show["timestamp"] = show["timestamp"].astype(str).str[:19]
    if "economie_kwh" in show.columns:
        show["economie_kwh"] = pd.to_numeric(show["economie_kwh"], errors="coerce").round(3)
    st.dataframe(show, width="stretch", hide_index=True, height=200)
    download_df_button(show, "decisions_simulation.csv", "Exporter decisions")


def _build_chart(
    sim_data: pd.DataFrame,
    template: str,
    focus_station: str | None,
    compare_hist: bool,
    source_df: pd.DataFrame,
    sim_base_date: date,
) -> None:
    hist = sim_data.copy()
    hist["conso"] = _num(hist, "consommation_kwh", 0)
    hist["eco"] = effective_economie_kwh(hist)
    hist["pred"] = _num(hist, "conso_predite", hist["conso"])

    if focus_station and focus_station != "Toutes":
        hist = hist[hist["station_id"].astype(str) == str(focus_station)]

    agg_map = {"conso": ("conso", "sum"), "eco": ("eco", "sum"), "pred": ("pred", "mean")}
    if "pred_q10" in hist.columns:
        agg_map["q10"] = ("pred_q10", "mean")
        agg_map["q90"] = ("pred_q90", "mean")
    agg = hist.groupby("timestamp", as_index=False).agg(**agg_map).tail(48)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["conso"], name="Mesuree", line=dict(color="#94a3b8")))
    if "q10" in agg.columns and "q90" in agg.columns:
        fig.add_trace(go.Scatter(
            x=pd.concat([agg["timestamp"], agg["timestamp"][::-1]]),
            y=pd.concat([agg["q90"], agg["q10"][::-1]]),
            fill="toself",
            fillcolor="rgba(30,58,138,0.12)",
            line=dict(width=0),
            name="Bande Q10-Q90",
            showlegend=True,
        ))
    fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["conso"] - agg["eco"], name="Optimisee", line=dict(color="#059669")))
    if "pred" in agg.columns:
        fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["pred"], name="Predite", line=dict(dash="dot", color="#1e40af")))

    alert_ts = [
        pd.Timestamp(e.get("timestamp"))
        for e in st.session_state.get("sim_alerts", [])
        if e.get("timestamp") is not None
    ]
    for ts in sorted(set(alert_ts))[-12:]:
        fig.add_vline(x=ts, line_width=1, line_dash="dash", line_color="#dc2626", opacity=0.35)

    if compare_hist and not source_df.empty and "timestamp" in hist.columns:
        last = hist["timestamp"].max()
        h = pd.Timestamp(last).hour
        hist_rows = replay_historical_hour(source_df, sim_base_date, h, hist["station_id"].astype(str).unique().tolist())
        if not hist_rows.empty:
            hv = float(_num(hist_rows, "consommation_kwh", 0).sum())
            fig.add_trace(go.Scatter(
                x=[last],
                y=[hv],
                mode="markers",
                name="Historique meme heure",
                marker=dict(color="#f59e0b", size=10),
            ))

    fig.update_layout(template=template, height=300, margin=dict(l=0, r=0, t=8, b=0))
    st.plotly_chart(fig, width="stretch")


def _render_mini_map(latest_all: pd.DataFrame, template: str) -> None:
    if latest_all.empty:
        return
    map_df = get_station_map_data(latest_all)
    if map_df.empty or not {"latitude", "longitude"}.issubset(map_df.columns):
        return
    plot = map_df.copy()
    if "mode_operation" in latest_all.columns:
        modes = latest_all.set_index("station_id")["mode_operation"]
        plot["mode_actuel"] = plot["station_id"].map(modes).fillna("NORMAL")
    else:
        plot["mode_actuel"] = "NORMAL"
    plot["mode_actuel"] = plot["mode_actuel"].map(lambda m: normalize_mode_key(m) or "NORMAL")
    plot["latitude"] = pd.to_numeric(plot["latitude"], errors="coerce")
    plot["longitude"] = pd.to_numeric(plot["longitude"], errors="coerce")
    plot = plot.dropna(subset=["latitude", "longitude"])
    if plot.empty:
        return
    fig = px.scatter_mapbox(
        plot,
        lat="latitude",
        lon="longitude",
        color="mode_actuel",
        hover_name="station_id",
        zoom=5.5,
        center={"lat": plot["latitude"].mean(), "lon": plot["longitude"].mean()},
        color_discrete_map=mode_color_discrete_map(plot["mode_actuel"]),
        height=280,
    )
    fig.update_layout(mapbox_style="carto-positron", margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch")


def page_simulation():
    security_middleware.enforce()
    header("Simulation", "Scenario, replay, alertes acquittables et journal des decisions")
    st.caption(active_filter_label())

    if st.session_state.get("sim_auto") and st.session_state.get("sim_running") and st_autorefresh:
        interval = int(st.session_state.get("sim_auto_interval", 3)) * 1000
        st_autorefresh(interval=interval, key="sim_autorefresh")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    role = st.session_state.get("role", "")
    stations = _station_options(role)
    if not stations:
        st.warning("Aucune station assignee.")
        return

    col_ctrl, col_main, col_events = st.columns([1, 2.2, 1.35])

    with col_ctrl:
        default_pick = [s for s in (st.session_state.get("sim_stations") or stations[:1]) if s in stations] or stations[:1]
        selected_stations = st.multiselect("Stations", stations, default=default_pick, key="sim_stations")
        data_source = st.radio("Source", ["Scenario", "Historique"], key="sim_data_source", horizontal=True)
        sim_mode = "Une journee"
        if data_source == "Historique":
            sim_mode = st.radio("Periode", ["Filtre actif", "Une journee"], key="sim_mode", horizontal=True)

        preset = st.selectbox("Preset scenario", ["—"] + list(SCENARIO_PRESETS.keys()), key="sim_preset")
        sim_base_date = datetime.now().date()
        if preset and preset != "—":
            sim_base_date = resolve_preset_date(preset)

        start_hour = 0
        num_days = 1
        if data_source == "Scenario" or sim_mode == "Une journee":
            sim_base_date = st.date_input("Jour", value=sim_base_date, key="sim_date")
            start_hour = st.slider("Heure debut", 0, 23, 0, key="sim_start_hour")
            if data_source == "Scenario":
                num_days = st.slider("Nombre de jours", 1, 7, 1, key="sim_num_days")
                st.caption(calendar_label(sim_base_date))

        st.slider(
            "Sensibilite anomalies",
            0.5, 2.0, float(st.session_state.get("sim_anomaly_sensitivity", 1.0)),
            0.1, key="sim_anomaly_sensitivity",
        )
        st.select_slider("Pas (heures)", options=[1, 2, 5], value=2, key="sim_speed")
        st.checkbox("Lecture auto", key="sim_auto")
        if st.session_state.get("sim_auto"):
            st.slider("Intervalle (s)", 1, 10, int(st.session_state.get("sim_auto_interval", 3)), key="sim_auto_interval")
        compare_hist = st.checkbox("Comparer historique", key="sim_compare_hist", value=False)

        c1, c2, c3 = st.columns(3)
        if c1.button("Lancer", type="primary", use_container_width=True):
            source_df = load_replay_source() if data_source == "Historique" else pd.DataFrame()
            st.session_state.update({
                "sim_running": True,
                "sim_tick": 0,
                "sim_data": pd.DataFrame(),
                "sim_alerts": [],
                "sim_decisions": [],
                "sim_ack_refs": set(),
                "sim_source_df": source_df,
                "sim_advance": True,
            })
            st.session_state["sim_total_ticks"] = _total_ticks(
                data_source, source_df, selected_stations, sim_mode, sim_base_date, start_hour, num_days,
            )
        if c2.button("Avancer", use_container_width=True) and st.session_state.get("sim_running"):
            st.session_state["sim_advance"] = True
        if c3.button("Reset", use_container_width=True):
            for key in (
                "sim_data", "sim_running", "sim_tick", "sim_source_df", "sim_total_ticks",
                "sim_alerts", "sim_decisions", "sim_ack_refs",
            ):
                st.session_state.pop(key, None)
            st.rerun()

        if st.button("Periode complete", use_container_width=True):
            source_df = _replay_source_df() if data_source == "Historique" else pd.DataFrame()
            _run_full_period(data_source, source_df, selected_stations, sim_mode, sim_base_date, start_hour, num_days)
            st.rerun()

        total = int(st.session_state.get("sim_total_ticks") or 0)
        tick = int(st.session_state.get("sim_tick", 0))
        if total > 0:
            st.progress(min(1.0, tick / max(total, 1)), text=f"{tick}/{total}")
        sim_export = st.session_state.get("sim_data")
        if isinstance(sim_export, pd.DataFrame) and not sim_export.empty:
            download_df_button(sim_export, "simulation.csv", "Exporter donnees")

    with col_events:
        latest_ts = None
        sim_data_ev = st.session_state.get("sim_data")
        if isinstance(sim_data_ev, pd.DataFrame) and not sim_data_ev.empty:
            latest_ts = sim_data_ev["timestamp"].max()
        _render_alerts_panel(latest_ts)
        st.divider()
        _render_decisions_panel(latest_ts)

    with col_main:
        if not selected_stations:
            st.info("Selectionnez au moins une station.")
            return

        auto_advance = (
            st.session_state.get("sim_auto")
            and st.session_state.get("sim_running")
        )
        if st.session_state.pop("sim_advance", False) or auto_advance:
            source_df = _replay_source_df() if data_source == "Historique" else pd.DataFrame()
            _advance_simulation(
                data_source, source_df, selected_stations, sim_mode,
                sim_base_date, start_hour, int(st.session_state.get("sim_speed", 1)), num_days,
            )
        if auto_advance and st.session_state.get("sim_running"):
            st.rerun()

        sim_data = st.session_state.get("sim_data")
        if not isinstance(sim_data, pd.DataFrame) or sim_data.empty:
            st.info("Lancez la simulation.")
            return

        sim_data = harmonize_nb3_economies(sim_data)
        latest_ts = sim_data["timestamp"].max()
        latest_all = sim_data[sim_data["timestamp"] == latest_ts]
        n_alerts = len(st.session_state.get("sim_alerts", []))
        n_decisions = len(st.session_state.get("sim_decisions", []))
        _status_banner(latest_ts, sim_base_date, n_alerts, n_decisions)

        station_choices = ["Toutes"] + sorted(latest_all["station_id"].astype(str).unique().tolist())
        focus = st.selectbox("Station focus", station_choices, key="sim_focus_station")
        focus_id = None if focus == "Toutes" else focus
        row = _row_by_station(latest_all, focus_id) if focus_id else _primary_row(latest_all)

        eco = float(effective_economie_kwh(latest_all).sum())
        conso = float(_num(latest_all, "consommation_kwh", 0).sum())
        mode = display_text(row.get("mode_operation"), "NORMAL")
        action = resolve_row_action(row, prefer_rl=False)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi_card("Conso", f"{conso:.2f} kWh", "", "blue")
        with c2:
            kpi_card("Economie", f"{eco * settings.PRIX_KWH_TN:.2f} DT", f"{eco:.2f} kWh", "green" if eco > 0 else "gray")
        with c3:
            kpi_card("Mode", mode, "", mode_kpi_class(mode))
        with c4:
            kpi_card("Alertes", str(n_alerts), "", "red" if n_alerts else "gray")

        color = mode_color(mode)
        st.markdown(
            f"""
<div class="decision-card" style="border-left-color:{color};">
  <div class="dc-mode" style="color:{color};">{html.escape(str(row.get('station_id', '—')))}</div>
  <div class="dc-action">{html.escape(action)}</div>
  <div class="dc-reason">{html.escape(mode_explanation(row))}</div>
</div>""",
            unsafe_allow_html=True,
        )

        _render_station_table(latest_all)
        source_df = _replay_source_df() if data_source == "Historique" or st.session_state.get("sim_compare_hist") else pd.DataFrame()
        _build_chart(
            sim_data, template, focus_id,
            st.session_state.get("sim_compare_hist", False),
            source_df if not source_df.empty else load_replay_source(),
            sim_base_date,
        )
        _render_mini_map(latest_all, template)
