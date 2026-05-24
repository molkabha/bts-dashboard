from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import (
    PLOTLY_DARK,
    PLOTLY_LIGHT,
    action_color_discrete_map,
    mode_color,
    mode_kpi_class,
    normalize_mode_key,
)
from services.calendar_tn import calendar_label, scenario_timestamps
from services.data_service import engineer_assigned_stations, init_db
from services.nb_metrics import (
    conso_optimisee_kwh_series,
    effective_economie_kwh,
    harmonize_nb3_economies,
)
from services.simulation_events import (
    classify_tick_rows,
    events_to_dataframe,
    filter_events,
    merge_event_log,
    persist_alert_ack,
)
from services.synthetic_bts import clear_sim_engine_cache, generate_period, hourly_snapshot, sim_engine
from ui.formatting import display_text, resolve_row_action
from ui.page_helpers import get_station_map_data, load_dashboard_df, mode_explanation
from ui.utils import download_df_button

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

_INVALID_STATION = frozenset({"", "none", "nan", "<na>", "null"})
SIM_RESET_KEYS = (
    "sim_data", "sim_running", "sim_paused", "sim_tick", "sim_total_ticks",
    "sim_alerts", "sim_decisions", "sim_ack_refs",
    "sim_data_source", "sim_mode", "sim_compare_hist", "sim_source_df",
)


def plot_template() -> str:
    return PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT


SIM_AUTO_INTERVAL_DEFAULT_S = 30


def ensure_sim_engine() -> None:
    """Precharge les profils Hub (une fois) pour accelerer Demarrer et les ticks."""
    try:
        sim_engine()
    except Exception:
        pass


def maybe_autorefresh() -> None:
    if not st_autorefresh:
        return
    if not st.session_state.get("sim_running") or st.session_state.get("sim_paused"):
        return
    interval = int(st.session_state.get("sim_auto_interval", SIM_AUTO_INTERVAL_DEFAULT_S)) * 1000
    count = st_autorefresh(interval=interval, key="sim_autorefresh")
    last = st.session_state.get("_sim_ar_count")
    if last is None:
        st.session_state["_sim_ar_count"] = count
        return
    if count != last:
        st.session_state["_sim_ar_count"] = count
        st.session_state["sim_advance"] = True


def _num(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def kwh_to_dt(kwh: float) -> float:
    return float(kwh) * float(settings.PRIX_KWH_TN)


def ecart_pct_series(df: pd.DataFrame) -> pd.Series:
    conso = _num(df, "consommation_kwh", 0)
    if "conso_predite" not in df.columns:
        return pd.Series(0.0, index=df.index)
    pred = pd.to_numeric(df["conso_predite"], errors="coerce")
    return ((conso - pred) / pred.replace(0, pd.NA) * 100).fillna(0)


def total_gain_kwh(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float(effective_economie_kwh(df).sum())


def inference_label(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    from services.data_service import load_nb1_production_metrics

    prod = load_nb1_production_metrics()
    model_name = str(prod.get("model") or "LightGBM")
    has_pred = (
        "conso_predite" in df.columns
        and pd.to_numeric(df["conso_predite"], errors="coerce").notna().any()
    )
    modes: list[str] = []
    if "inference_pipeline" in df.columns:
        modes = df["inference_pipeline"].dropna().astype(str).unique().tolist()

    if has_pred or any(
        token in m
        for m in modes
        for token in ("nb1_nb2_nb3", "dashboard", "lgbm", "nb1")
    ):
        r2 = prod.get("r2")
        extra = f" · R²={float(r2):.3f}" if r2 is not None else ""
        return (
            f"Pipeline : {model_name} (NB1) + detecteurs NB2 + moteur NB3 "
            f"(artefacts Hub{extra})"
        )
    if any("profil" in m for m in modes):
        return (
            f"Prediction : profils horaires — relancez avec Stop puis Demarrer "
            f"(attendu : {model_name} via dataset enrichi)"
        )
    return (
        f"Prediction : en attente — cliquez Demarrer "
        f"(source : {model_name} / Hub molkab/dashboard)"
    )


def valid_station_id(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if text.lower() in _INVALID_STATION:
        return None
    return text


def clean_station_list(ids) -> list[str]:
    out: list[str] = []
    for raw in ids:
        sid = valid_station_id(raw)
        if sid and sid not in out:
            out.append(sid)
    return sorted(out)


def station_options(role: str) -> list[str]:
    from services.data_service import dataset_cache_key, load_filter_dimension_options

    cache_key = f"sim_stations_{dataset_cache_key()}|{role}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, list) and cached:
        return cached
    opts = load_filter_dimension_options(dataset_cache_key())
    stations = clean_station_list(opts.get("stations") or [])
    if not stations:
        df = load_dashboard_df(["station_id"])
        if not df.empty and "station_id" in df.columns:
            stations = clean_station_list(df["station_id"].unique())
    if role != "admin":
        assigned = {str(s) for s in engineer_assigned_stations()}
        stations = [s for s in stations if s in assigned]
    st.session_state[cache_key] = stations
    return stations


def init_sim_stations(stations: list[str]) -> None:
    default_pick = [s for s in clean_station_list(stations[:1]) if s in stations]
    if "sim_stations" not in st.session_state:
        st.session_state["sim_stations"] = default_pick
        return
    cleaned = [s for s in clean_station_list(st.session_state["sim_stations"]) if s in stations]
    if not cleaned:
        st.session_state["sim_stations"] = default_pick


def station_picker_summary(selected: list[str], all_stations: list[str]) -> str:
    n = len(selected)
    total = len(all_stations)
    if n == 0:
        return "Stations"
    if n == 1:
        return str(selected[0])
    if total and n >= total:
        return f"Toutes ({n})"
    return f"{n} stations"


def render_sim_station_picker(stations: list[str]) -> None:
    """Selecteur compact (une ligne) : resume + panneau avec liste scrollable."""
    init_sim_stations(stations)
    selected = [
        s for s in clean_station_list(st.session_state.get("sim_stations") or [])
        if s in stations
    ]
    summary = station_picker_summary(selected, stations)
    with st.popover(
        summary,
        use_container_width=True,
        help="Selectionner les stations a inclure dans la simulation",
    ):
        quick1, quick2 = st.columns(2)
        with quick1:
            if st.button("Tout", key="sim_pick_all", use_container_width=True):
                st.session_state["sim_stations"] = list(stations)
                st.rerun()
        with quick2:
            if st.button("Reinit.", key="sim_pick_reset", use_container_width=True):
                st.session_state["sim_stations"] = [
                    s for s in clean_station_list(stations[:1]) if s in stations
                ]
                st.rerun()
        st.multiselect(
            "Stations",
            stations,
            key="sim_stations",
            label_visibility="collapsed",
            placeholder="Rechercher une station…",
        )


def resolve_selected_stations(stations: list[str]) -> list[str]:
    default_pick = [s for s in clean_station_list(stations[:1]) if s in stations]
    selected = clean_station_list(st.session_state.get("sim_stations") or [])
    selected = [s for s in selected if s in stations]
    return selected or default_pick


def default_sim_date() -> date:
    from ui.utils import merged_active_filters

    gf = merged_active_filters()
    dr = gf.get("date_range")
    if dr and len(dr) >= 1:
        return dr[0] if isinstance(dr[0], date) else pd.Timestamp(dr[0]).date()
    sb_from = st.session_state.get("sb_date_from")
    if sb_from is not None:
        return sb_from if isinstance(sb_from, date) else pd.Timestamp(sb_from).date()
    return datetime.now().date()


def purge_stale_sim_session() -> None:
    """Ne pas effacer une simulation en cours (y compris repli profil / pipeline actuel)."""
    if st.session_state.get("sim_running"):
        return
    sim_data = st.session_state.get("sim_data")
    if not isinstance(sim_data, pd.DataFrame) or sim_data.empty:
        return
    if "inference_pipeline" not in sim_data.columns:
        return
    legacy = sim_data["inference_pipeline"].astype(str).str.fullmatch(
        r"profil_historique|scenario_rules|dashboard_lgbm_hf",
        case=False,
        na=False,
    )
    if legacy.any():
        reset_simulation()


def sim_params() -> tuple[date, int, int]:
    sim_base_date = st.session_state.get("sim_date")
    if sim_base_date is None:
        sim_base_date = default_sim_date()
    start_hour = int(st.session_state.get("sim_start_hour", 0))
    num_days = int(st.session_state.get("sim_num_days", 1))
    return sim_base_date, start_hour, num_days


def total_ticks(sim_base_date: date, start_hour: int, num_days: int) -> int:
    return len(scenario_timestamps(sim_base_date, start_hour, num_days))


def record_events(processed: pd.DataFrame) -> None:
    alerts, decisions = classify_tick_rows(processed)
    st.session_state["sim_alerts"] = merge_event_log(st.session_state.get("sim_alerts", []), alerts)
    st.session_state["sim_decisions"] = merge_event_log(st.session_state.get("sim_decisions", []), decisions)


def append_sim_data(processed: pd.DataFrame, max_rows: int) -> None:
    processed = harmonize_nb3_economies(processed)
    existing = st.session_state.get("sim_data", pd.DataFrame())
    if isinstance(existing, pd.DataFrame) and not existing.empty:
        st.session_state["sim_data"] = pd.concat([existing, processed], ignore_index=True).tail(max_rows)
    else:
        st.session_state["sim_data"] = processed


def advance_scenario(
    selected_stations: list[str],
    sim_base_date: date,
    start_hour: int,
    tick: int,
    steps: int,
    num_days: int,
    *,
    engine: tuple | None = None,
) -> tuple[pd.DataFrame, int]:
    frames = []
    stamps = scenario_timestamps(sim_base_date, start_hour, num_days)
    eng = engine if engine is not None else sim_engine()
    for step in range(max(1, steps)):
        idx = tick + step
        if idx >= len(stamps):
            break
        ts = stamps[idx]
        batch = hourly_snapshot(
            ts.date(), ts.hour, selected_stations, engine=eng,
        )
        if not batch.empty:
            frames.append(batch)
    if not frames:
        return pd.DataFrame(), 0
    return pd.concat(frames, ignore_index=True), len(frames)


def advance_simulation(
    selected_stations: list[str],
    sim_base_date: date,
    start_hour: int,
    steps: int,
    num_days: int,
) -> bool:
    tick = int(st.session_state.get("sim_tick", 0))
    max_rows = max(72, 24 * num_days) * len(selected_stations)
    stamps = scenario_timestamps(sim_base_date, start_hour, num_days)
    if tick >= len(stamps):
        st.session_state["sim_running"] = False
        return False
    processed, n = advance_scenario(
        selected_stations, sim_base_date, start_hour, tick, steps, num_days,
        engine=sim_engine(),
    )
    if processed.empty:
        st.session_state["sim_running"] = False
        return False
    append_sim_data(processed, max_rows)
    record_events(processed)
    st.session_state["sim_tick"] = tick + max(1, n)
    return True


def run_full_period(
    selected_stations: list[str],
    sim_base_date: date,
    start_hour: int,
    num_days: int,
) -> None:
    processed = generate_period(sim_base_date, start_hour, num_days, selected_stations)
    if processed.empty:
        return
    max_rows = max(72, 24 * num_days) * len(selected_stations)
    st.session_state["sim_data"] = harmonize_nb3_economies(processed).tail(max_rows)
    st.session_state["sim_tick"] = (
        len(processed["timestamp"].drop_duplicates()) if "timestamp" in processed.columns else 0
    )
    st.session_state["sim_running"] = False
    record_events(processed)


def reset_simulation() -> None:
    for key in SIM_RESET_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop("_sim_ar_count", None)


def bootstrap_simulation(selected_stations: list[str]) -> bool:
    """Premier tick immediat au clic Demarrer (affichage sans attendre l auto-refresh)."""
    if not selected_stations:
        st.session_state["sim_bootstrap_error"] = "Selectionnez au moins une station."
        return False
    sim_base_date, start_hour, num_days = sim_params()
    max_rows = max(72, 24 * num_days) * len(selected_stations)
    engine = sim_engine()
    processed, n = advance_scenario(
        selected_stations, sim_base_date, start_hour, 0, 1, num_days, engine=engine,
    )
    if processed.empty:
        st.session_state["sim_bootstrap_error"] = (
            "Impossible de generer la premiere heure. Verifiez la connexion Hub "
            "ou relancez avec Stop puis Demarrer."
        )
        return False
    append_sim_data(processed, max_rows)
    record_events(processed)
    st.session_state["sim_tick"] = max(1, n)
    st.session_state.pop("sim_advance", None)
    st.session_state.pop("sim_bootstrap_error", None)
    return True


def process_tick(selected_stations: list[str]) -> None:
    if st.session_state.get("sim_paused") or not st.session_state.get("sim_running"):
        return
    if not st.session_state.pop("sim_advance", False):
        return
    sim_base_date, start_hour, num_days = sim_params()
    advance_simulation(
        selected_stations, sim_base_date, start_hour,
        int(st.session_state.get("sim_speed", 1)), num_days,
    )


def latest_snapshot() -> tuple[pd.DataFrame, pd.DataFrame, object, date]:
    sim_base_date, _, _ = sim_params()
    sim_data = st.session_state.get("sim_data")
    if not isinstance(sim_data, pd.DataFrame) or sim_data.empty:
        return pd.DataFrame(), pd.DataFrame(), None, sim_base_date
    sim_data = harmonize_nb3_economies(sim_data)
    latest_ts = sim_data["timestamp"].max()
    latest_all = sim_data[sim_data["timestamp"] == latest_ts]
    latest_all = latest_all[latest_all["station_id"].map(valid_station_id).notna()]
    return sim_data, latest_all, latest_ts, sim_base_date


def row_by_station(latest_all: pd.DataFrame, station_id: str) -> pd.Series:
    if latest_all.empty:
        return pd.Series(dtype=object)
    hit = latest_all[latest_all["station_id"].astype(str) == str(station_id)]
    if hit.empty:
        return latest_all.iloc[0]
    return hit.iloc[0]


def render_station_table(latest_all: pd.DataFrame) -> None:
    if latest_all.empty:
        return
    work = latest_all.copy()
    work["station_id"] = work["station_id"].map(valid_station_id)
    work = work.dropna(subset=["station_id"])
    work["Mode"] = work.get("mode_operation", "NORMAL").astype(str)
    work["Action"] = work.apply(lambda r: resolve_row_action(r, prefer_rl=True), axis=1)
    work["Conso"] = _num(work, "consommation_kwh", 0).round(2)
    work["QoS"] = _num(work, "score_qos", 0).round(2)
    work["Anomalie"] = _num(work, "anomalie_score_ensemble", 0).round(2)
    cols = ["station_id", "Mode", "Conso", "QoS", "Anomalie", "Action"]
    show = work[[c for c in cols if c in work.columns]]
    st.dataframe(show, width="stretch", hide_index=True, height=min(42 + 35 * len(show), 320))


def event_station_filter_options(selected_stations: list[str], events: list[dict]) -> list[str]:
    from_events = {valid_station_id(e.get("station_id")) for e in events}
    from_events.discard(None)
    return sorted(set(selected_stations) | from_events)


def render_alerts_panel(current_ts, selected_stations: list[str]) -> None:
    from views import simulation_ui as ui

    raw = st.session_state.get("sim_alerts", [])
    station_opts = event_station_filter_options(selected_stations, raw)
    if not station_opts and not raw:
        ui.empty_state("Aucune alerte", "Les alertes apparaitront lorsque le scenario detectera une anomalie.")
        return

    f1, f2, f3, f4 = st.columns(4)
    severities = ["Toutes", "ATTENTION", "CRITIQUE"]
    types = ["Toutes", "anomalie_sans_action", "qos_risque"]
    with f1:
        st_sel = station_opts[0] if len(station_opts) == 1 else st.selectbox(
            "Station", station_opts, key="sim_alert_station",
        )
    with f2:
        sev_sel = st.selectbox("Severite", severities, key="sim_alert_sev")
    with f3:
        type_sel = st.selectbox("Type", types, key="sim_alert_type")
    with f4:
        hour_only = st.checkbox("Heure courante", key="sim_alert_hour_only")

    filtered = filter_events(
        raw,
        station=st_sel,
        severity=sev_sel,
        event_type=type_sel,
        current_hour_only=hour_only,
        current_ts=pd.Timestamp(current_ts) if current_ts is not None else None,
    )
    acked = st.session_state.get("sim_ack_refs", set())
    pending = [e for e in filtered if e.get("alert_ref") not in acked][:12]

    from ui.components import section

    col_pending, col_journal = st.columns([1, 1.2])

    with col_pending:
        with section("A traiter"):
            if not pending:
                st.caption("Rien en attente.")
            for item in pending:
                ui.render_alert_card(item)
                ref = item.get("alert_ref", "")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("Traité", key=f"ack_ok_{ref}", use_container_width=True):
                        user = st.session_state.get("username") or st.session_state.get("user", "engineer")
                        init_db()
                        persist_alert_ack(user, str(item.get("station_id")), ref, "acquitte")
                        acked.add(ref)
                        st.session_state["sim_ack_refs"] = acked
                        st.rerun()
                with b2:
                    if st.button("Ignorer", key=f"ack_fp_{ref}", use_container_width=True):
                        user = st.session_state.get("username") or st.session_state.get("user", "engineer")
                        init_db()
                        persist_alert_ack(user, str(item.get("station_id")), ref, "faux_positif")
                        acked.add(ref)
                        st.session_state["sim_ack_refs"] = acked
                        st.rerun()

    df = events_to_dataframe(filtered)
    with col_journal:
        with section("Journal"):
            if df.empty:
                st.caption("Aucune entree.")
            else:
                show = df[["timestamp", "station_id", "severity", "type", "message"]].copy()
                show["timestamp"] = show["timestamp"].astype(str).str[:19]
                st.dataframe(show, width="stretch", hide_index=True, height=360)
                download_df_button(show, "alertes_simulation.csv", "Exporter")


def render_decisions_panel(current_ts, selected_stations: list[str]) -> None:
    from ui.components import section
    from views import simulation_ui as ui

    raw = st.session_state.get("sim_decisions", [])
    station_opts = event_station_filter_options(selected_stations, raw)
    if not station_opts and not raw:
        ui.empty_state("Aucune decision", "Les actions d optimisation s afficheront ici pendant le scenario.")
        return

    f1, f2 = st.columns(2)
    with f1:
        st_sel = station_opts[0] if len(station_opts) == 1 else st.selectbox(
            "Station", station_opts, key="sim_dec_station",
        )
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
        ui.empty_state("Aucun resultat", "Modifiez les filtres ou avancez la simulation.")
        return
    with section("Journal des decisions"):
        show = df[["timestamp", "station_id", "mode", "action", "economie_kwh", "message"]].copy()
        show["timestamp"] = show["timestamp"].astype(str).str[:19]
        if "economie_kwh" in show.columns:
            show["economie_kwh"] = pd.to_numeric(show["economie_kwh"], errors="coerce").round(3)
        st.dataframe(show, width="stretch", hide_index=True, height=280)
        download_df_button(show, "decisions_simulation.csv", "Exporter decisions")


def build_chart(sim_data: pd.DataFrame, template: str, focus_station: str | None) -> None:
    hist = sim_data.copy()
    if focus_station:
        hist = hist[hist["station_id"].astype(str) == str(focus_station)]
    if hist.empty:
        st.caption("Aucune donnee pour cette station.")
        return

    hist = harmonize_nb3_economies(hist)
    hist["conso"] = _num(hist, "consommation_kwh", 0)
    hist["eco"] = effective_economie_kwh(hist)
    hist["conso_opt"] = conso_optimisee_kwh_series(hist)
    hist["pred"] = (
        pd.to_numeric(hist["conso_predite"], errors="coerce")
        if "conso_predite" in hist.columns
        else pd.Series(float("nan"), index=hist.index)
    )
    hist["ecart_pct"] = ecart_pct_series(hist)

    multi = hist["station_id"].nunique() > 1
    # Meme regle d agregation pour toutes les courbes (evite sum reel vs mean predit).
    agg_spec: dict = {
        "conso": ("conso", "sum"),
        "eco": ("eco", "sum"),
        "conso_opt": ("conso_opt", "sum"),
        "pred": ("pred", "sum"),
    }
    if "pred_q10" in hist.columns:
        agg_spec["q10"] = ("pred_q10", "sum")
        agg_spec["q90"] = ("pred_q90", "sum")
    agg = hist.groupby("timestamp", as_index=False).agg(**agg_spec).tail(48)

    label_mesure = "Mesuree" if not multi else "Mesuree (total reseau)"
    label_pred = "Predite" if not multi else "Predite (total reseau)"
    label_opt = "Optimisee" if not multi else "Optimisee (total reseau)"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["conso"], name=label_mesure, line=dict(color="#94a3b8")))
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
    fig.add_trace(go.Scatter(
        x=agg["timestamp"], y=agg["conso_opt"], name=label_opt, line=dict(color="#059669"),
    ))
    fig.add_trace(go.Scatter(
        x=agg["timestamp"],
        y=agg["pred"],
        name=label_pred,
        line=dict(dash="dot", color="#1e40af", width=2),
    ))
    if len(agg) >= 1 and agg["conso"].notna().any() and agg["pred"].notna().any():
        last = agg.iloc[-1]
        if pd.notna(last["pred"]) and last["pred"] != 0:
            ecart_last = (float(last["conso"]) - float(last["pred"])) / float(last["pred"]) * 100
            fig.add_annotation(
                x=last["timestamp"],
                y=max(float(last["conso"]), float(last["pred"])),
                text=f"Écart {ecart_last:+.1f} %",
                showarrow=True,
                arrowhead=2,
                font=dict(size=11),
            )
    alert_ts = [
        pd.Timestamp(e.get("timestamp"))
        for e in st.session_state.get("sim_alerts", [])
        if e.get("timestamp") is not None
    ]
    for ts in sorted(set(alert_ts))[-12:]:
        fig.add_vline(x=ts, line_width=1, line_dash="dash", line_color="#dc2626", opacity=0.35)
    fig.update_layout(
        template=template,
        height=360,
        margin=dict(l=0, r=0, t=8, b=0),
        yaxis_title="kWh",
    )
    render_chart_kpis(hist, focus_station)

    if multi and not focus_station:
        st.caption("Plusieurs stations : les courbes affichent la somme horaire sur le parc selectionne.")

    pipe_hint = inference_label(hist)
    if pipe_hint:
        st.caption(pipe_hint)
    if len(agg) >= 1:
        last = agg.iloc[-1]
        if pd.notna(last.get("pred")) and pd.notna(last.get("conso")):
            same = abs(float(last["conso"]) - float(last["pred"])) < 0.02
            if same:
                st.warning(
                    "Courbes superposees : le predit est identique ou quasi identique au reel simule. "
                    "Verifiez que conso_predite est bien present dans le dataset enrichi (page Prediction)."
                )

    st.plotly_chart(fig, width="stretch", key=f"sim_chart_{focus_station or 'all'}")


def render_chart_kpis(hist: pd.DataFrame, focus_station: str | None) -> None:
    """KPIs sous la courbe : réel, prédit, écart, gain."""
    if hist.empty:
        return
    work = hist.copy()
    if focus_station:
        work = work[work["station_id"].astype(str) == str(focus_station)]
    if work.empty:
        return
    latest_ts = work["timestamp"].max()
    snap = work[work["timestamp"] == latest_ts]
    conso = float(_num(snap, "consommation_kwh", 0).sum())
    pred = float(pd.to_numeric(snap.get("conso_predite"), errors="coerce").sum())
    if pd.isna(pred):
        pred = 0.0
    ecart = ((conso - pred) / pred * 100) if pred else 0.0
    gain_kwh = total_gain_kwh(snap)
    gain_dt = kwh_to_dt(gain_kwh)
    c1, c2, c3, c4 = st.columns(4)
    lbl = inference_label(work)
    pred_title = "Prédit LightGBM (kWh)" if lbl and "LightGBM" in lbl else "Prédit (kWh)"
    c1.metric("Réel (kWh)", f"{conso:.2f}")
    c2.metric(pred_title, f"{pred:.2f}")
    c3.metric("Écart réel / prédit", f"{ecart:+.1f} %")
    c4.metric("Gain optimisation", f"{gain_dt:.2f} DT", f"{gain_kwh:.2f} kWh économisés")


def build_simulation_report(
    sim_data: pd.DataFrame,
    sim_date: date,
    selected_stations: list[str],
) -> pd.DataFrame:
    """Donnees du rapport sommaire (total reseau + par station) pour export PDF."""
    rows: list[dict] = []

    def _row(section: str, libelle: str, valeur, unite: str = "") -> None:
        rows.append({
            "Section": section,
            "Libelle": libelle,
            "Valeur": valeur,
            "Unite": unite,
        })

    if sim_data.empty:
        _row("Total", "Statut", "Aucune donnee", "")
        return pd.DataFrame(rows)

    work = harmonize_nb3_economies(sim_data.copy())
    conso = float(_num(work, "consommation_kwh", 0).sum())
    pred = float(_num(work, "conso_predite", 0).sum())
    gain_kwh = total_gain_kwh(work)
    gain_dt = kwh_to_dt(gain_kwh)
    ecart_moy = float(ecart_pct_series(work).mean()) if not work.empty else 0.0
    n_hours = int(work["timestamp"].nunique()) if "timestamp" in work.columns else 0
    n_stations = int(work["station_id"].nunique()) if "station_id" in work.columns else 0
    alerts_n = len(st.session_state.get("sim_alerts") or [])

    _row("Total", "Date scenario", str(sim_date), "")
    _row("Total", "Stations simulees", n_stations, "nombre")
    _row("Total", "Heures simulees", n_hours, "nombre")
    _row("Total", "Consommation reelle totale", round(conso, 3), "kWh")
    _row("Total", "Consommation predite totale", round(pred, 3), "kWh")
    _row("Total", "Ecart moyen reel/predit", round(ecart_moy, 2), "%")
    _row("Total", "Gain energie total", round(gain_kwh, 3), "kWh")
    _row("Total", "Gain financier total", round(gain_dt, 2), "DT")
    _row("Total", "Nombre d alertes", alerts_n, "nombre")

    if "station_id" in work.columns:
        for sid in sorted(work["station_id"].astype(str).unique()):
            sub = work[work["station_id"].astype(str) == sid]
            c = float(_num(sub, "consommation_kwh", 0).sum())
            p = float(_num(sub, "conso_predite", 0).sum())
            g = total_gain_kwh(sub)
            _row(f"Station {sid}", "Consommation reelle", round(c, 3), "kWh")
            _row(f"Station {sid}", "Consommation predite", round(p, 3), "kWh")
            _row(f"Station {sid}", "Ecart moyen", round(float(ecart_pct_series(sub).mean()), 2), "%")
            _row(f"Station {sid}", "Gain energie", round(g, 3), "kWh")
            _row(f"Station {sid}", "Gain (DT)", round(kwh_to_dt(g), 2), "DT")
            if "anomalie_score_ensemble" in sub.columns:
                _row(
                    f"Station {sid}",
                    "Score anomalie max",
                    round(float(sub["anomalie_score_ensemble"].max()), 3),
                    "",
                )

    return pd.DataFrame(rows)


def render_simulation_exports(
    sim_data: pd.DataFrame,
    sim_date: date,
    selected_stations: list[str],
) -> None:
    if sim_data.empty:
        return
    from datetime import datetime

    from utils.pdf_export import generate_simulation_sommaire_pdf

    report = build_simulation_report(sim_data, sim_date, selected_stations)
    pdf_bytes = generate_simulation_sommaire_pdf(
        report,
        sim_date=sim_date,
        selected_stations=selected_stations,
        alerts=st.session_state.get("sim_alerts") or [],
    )
    c1, c2 = st.columns(2)
    with c1:
        download_df_button(sim_data, "simulation_donnees.csv", "Donnees detaillees (CSV)")
    with c2:
        st.download_button(
            "Télécharger le sommaire (PDF)",
            data=pdf_bytes,
            file_name=f"simulation_sommaire_{sim_date}_{datetime.now().strftime('%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="sim_sommaire_pdf",
        )
        st.caption("Rapport sommaire : total reseau, detail par station, liste des alertes.")


def render_mini_map(latest_all: pd.DataFrame) -> None:
    if latest_all.empty:
        st.info("Aucune donnee cartographique.")
        return

    from ui.formatting import format_action_label

    map_df = get_station_map_data(latest_all)
    if map_df.empty or not {"latitude", "longitude"}.issubset(map_df.columns):
        st.info("Coordonnees GPS indisponibles.")
        return

    work = latest_all.copy()
    work["action_a_faire"] = work.apply(
        lambda r: format_action_label(resolve_row_action(r, prefer_rl=False), default="Maintien"),
        axis=1,
    )
    if "mode_operation" in work.columns:
        modes = work.set_index("station_id")["mode_operation"]
        map_df["mode"] = map_df["station_id"].map(modes).fillna("NORMAL")
    else:
        map_df["mode"] = "NORMAL"
    map_df["mode"] = map_df["mode"].map(lambda m: normalize_mode_key(m) or "NORMAL")
    actions = work.set_index("station_id")["action_a_faire"]
    map_df["action_a_faire"] = map_df["station_id"].map(actions).fillna("Maintien")
    if "anomalie_score_ensemble" in work.columns:
        map_df["score_anomalie"] = map_df["station_id"].map(
            work.set_index("station_id")["anomalie_score_ensemble"],
        )

    plot = map_df.copy()
    plot["latitude"] = pd.to_numeric(plot["latitude"], errors="coerce")
    plot["longitude"] = pd.to_numeric(plot["longitude"], errors="coerce")
    plot = plot.dropna(subset=["latitude", "longitude"])
    if plot.empty:
        st.info("Coordonnees GPS invalides.")
        return

    st.caption(
        f"{len(plot)} station(s) · couleur = action prevue a l'heure simulee"
    )

    hover_cols = [c for c in ("mode", "score_anomalie") if c in plot.columns]
    fig = px.scatter_mapbox(
        plot,
        lat="latitude",
        lon="longitude",
        color="action_a_faire",
        hover_name="station_id",
        hover_data=hover_cols,
        zoom=5.5,
        center={"lat": plot["latitude"].mean(), "lon": plot["longitude"].mean()},
        color_discrete_map=action_color_discrete_map(plot["action_a_faire"]),
        height=420,
    )
    fig.update_layout(
        mapbox_style="carto-positron",
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(title="Action a l'heure"),
    )
    fig.update_traces(marker=dict(opacity=0.9, size=12))
    st.plotly_chart(fig, width="stretch")
