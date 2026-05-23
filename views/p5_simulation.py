"""Page 6 - Simulation replay NB3 (donnees notebooks)."""

from __future__ import annotations

import html
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from config.settings import settings
from config.theme import MODE_COLORS, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import engineer_assigned_stations, load_nb2_network_stats
from services.nb_metrics import economie_rl_kwh_series, effective_economie_kwh, harmonize_nb3_economies
from services.nb_replay import load_replay_source, replay_batch, replay_timestamps
from ui.components import header, kpi_card, section
from ui.page_helpers import load_dashboard_df, mode_explanation
from ui.utils import active_filter_label, download_df_button


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


def _replay_window(source_df, selected_stations, sim_mode, sim_base_date, start_hour):
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


def _advance_replay(source_df, selected_stations, sim_mode, sim_base_date, start_hour, steps) -> bool:
    on_date, start_dt = _replay_window(source_df, selected_stations, sim_mode, sim_base_date, start_hour)
    on_date_arg = on_date if sim_mode == "Une journee" else None
    max_rows = 72 * len(selected_stations)
    injection = st.session_state.get("sim_injection")
    replay_ok = False

    for _ in range(max(1, steps)):
        tick = int(st.session_state.get("sim_tick", 0))
        processed, _ = replay_batch(
            source_df, selected_stations, tick,
            start_dt=start_dt, on_date=on_date_arg,
        )
        if processed.empty:
            st.session_state["sim_running"] = False
            break

        processed = harmonize_nb3_economies(processed)
        if injection == "heat":
            if "temperature_ambiante" in processed.columns:
                processed["temperature_ambiante"] = _num(processed, "temperature_ambiante", 25) + 15
            processed["consommation_kwh"] = _num(processed, "consommation_kwh", 0) * 1.3
        elif injection == "traffic" and "charge_cpu_pct" in processed.columns:
            processed["charge_cpu_pct"] = (_num(processed, "charge_cpu_pct", 0) * 2).clip(0, 99)

        existing = st.session_state.get("sim_data", pd.DataFrame())
        if isinstance(existing, pd.DataFrame) and not existing.empty:
            st.session_state["sim_data"] = pd.concat([existing, processed], ignore_index=True).tail(max_rows)
        else:
            st.session_state["sim_data"] = processed
        st.session_state["sim_tick"] = tick + 1
        replay_ok = True

    if injection:
        st.session_state.pop("sim_injection", None)
    return replay_ok


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


def page_simulation():
    security_middleware.enforce()
    role = st.session_state.get("role", "")
    header("Simulation", "Replay horaire — artefacts NB1 / NB2 / NB3")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    st.caption(active_filter_label())

    stations = _station_options(role)
    if not stations:
        st.warning("Aucune station disponible pour les filtres actifs.")
        return

    col_ctrl, col_main = st.columns([1, 2.8])

    with col_ctrl:
        section("Replay")
        default_pick = [s for s in (st.session_state.get("sim_stations") or stations[:1]) if s in stations] or stations[:1]
        selected_stations = st.multiselect("Stations", stations, default=default_pick, key="sim_stations")

        sim_mode = st.radio("Periode", ["Periode filtree", "Une journee"], key="sim_mode", horizontal=True)
        sim_base_date = datetime.now().date()
        start_hour = 0
        if sim_mode == "Une journee":
            bounds = load_dashboard_df(["timestamp"])
            if not bounds.empty and "timestamp" in bounds.columns:
                ts = pd.to_datetime(bounds["timestamp"], errors="coerce").dropna()
                if not ts.empty:
                    sim_base_date = st.date_input(
                        "Jour", value=ts.min().date(),
                        min_value=ts.min().date(), max_value=ts.max().date(), key="sim_date",
                    )
            else:
                sim_base_date = st.date_input("Jour", value=datetime.now().date(), key="sim_date")
            start_hour = st.slider("Heure de depart", 0, 23, 0, key="sim_start_hour")

        st.select_slider("Pas par clic", options=[1, 2, 5, 10], value=2, key="sim_speed")
        st.checkbox("Auto", value=False, key="sim_auto")

        b1, b2, b3 = st.columns(3)
        with b1:
            btn_start = st.button("Demarrer", type="primary", use_container_width=True)
        with b2:
            btn_step = st.button("Suivant", use_container_width=True)
        with b3:
            btn_reset = st.button("Reset", use_container_width=True)

        if btn_reset:
            for key in ("sim_data", "sim_running", "sim_tick", "sim_source_df", "sim_injection", "sim_total_ticks"):
                st.session_state.pop(key, None)
            st.rerun()

        if btn_start:
            source_df = load_replay_source()
            st.session_state.update({
                "sim_running": True, "sim_tick": 0, "sim_data": pd.DataFrame(),
                "sim_source_df": source_df, "sim_advance": True,
            })
            on_date, start_dt = _replay_window(source_df, selected_stations, sim_mode, sim_base_date, start_hour)
            st.session_state["sim_total_ticks"] = len(replay_timestamps(
                source_df, selected_stations, start_dt,
                on_date=on_date if sim_mode == "Une journee" else None,
            ))

        if btn_step and st.session_state.get("sim_running"):
            st.session_state["sim_advance"] = True

        total = int(st.session_state.get("sim_total_ticks") or 0)
        tick = int(st.session_state.get("sim_tick", 0))
        if total > 0:
            st.progress(min(1.0, tick / total))
            st.caption(f"{tick} / {total} pas")

        sim_export = st.session_state.get("sim_data")
        if isinstance(sim_export, pd.DataFrame) and not sim_export.empty:
            download_df_button(sim_export, "simulation_session.csv", "CSV")

    with col_main:
        if not selected_stations:
            st.info("Selectionnez au moins une station.")
            return

        advance_manual = st.session_state.pop("sim_advance", False)
        advance_auto = False
        if st.session_state.get("sim_auto") and st.session_state.get("sim_running"):
            interval_ms = max(800, 350 * int(st.session_state.get("sim_speed", 2)))
            advance_auto = st_autorefresh(interval=interval_ms, key="sim_autorefresh") > 0

        if (advance_manual or advance_auto) and st.session_state.get("sim_running"):
            source_df = st.session_state.get("sim_source_df")
            if not isinstance(source_df, pd.DataFrame) or source_df.empty:
                source_df = load_replay_source()
                st.session_state["sim_source_df"] = source_df
            ok = _advance_replay(
                source_df, selected_stations, sim_mode, sim_base_date, start_hour,
                int(st.session_state.get("sim_speed", 1)),
            )
            if not ok and not st.session_state.get("sim_running"):
                st.warning("Fin du replay — elargissez les filtres sidebar ou changez la date.")

        sim_data = st.session_state.get("sim_data")
        if not isinstance(sim_data, pd.DataFrame) or sim_data.empty:
            st.info("Demarrer le replay pour afficher les mesures horaires NB3.")
            return

        sim_data = harmonize_nb3_economies(sim_data)
        latest_ts = sim_data["timestamp"].max()
        latest_all = sim_data[sim_data["timestamp"] == latest_ts]
        row = _primary_row(latest_all)

        eco_rl = float(economie_rl_kwh_series(latest_all).sum())
        eco_comb = float(effective_economie_kwh(latest_all).sum())
        conso = float(_num(latest_all, "consommation_kwh", 0).sum())
        qos = float(_num(latest_all, "score_qos", 0.75).mean())
        mode = str(row.get("mode_operation", "—"))
        action = str(row.get("action_proposee", row.get("action_rl", "—")))

        st.caption(f"Pas horaire : **{str(latest_ts)[:19]}**")

        k1, k2, k3 = st.columns(3)
        with k1:
            kpi_card("Consommation", f"{conso:.2f} kWh", "Ce pas", "blue")
        with k2:
            kpi_card(
                "Economie NB3",
                f"{eco_comb:.3f} kWh",
                f"{eco_comb * settings.PRIX_KWH_TN:.2f} DT · RL {eco_rl:.3f} kWh",
                "green" if eco_comb > 0 else "gray",
            )
        with k3:
            kpi_card("QoS", f"{qos:.2f}", mode, "eco" if qos >= 0.75 else "danger")

        if eco_rl <= 0 and eco_comb <= 0:
            st.caption(
                "Pas sans gain energetique (souvent mode NORMAL). Les economies apparaissent sur les pas ECO / optimisation NB3."
            )

        color = MODE_COLORS.get(mode, "#64748b")
        eco_dt = eco_rl * settings.PRIX_KWH_TN
        st.markdown(
            f"""
<div class="decision-card" style="border-left-color:{color};">
  <div class="dc-mode" style="color:{color};">{html.escape(str(row.get('station_id', 'Flotte')))} — {html.escape(mode)}</div>
  <div class="dc-action">{html.escape(action)}</div>
  <div class="dc-reason">{html.escape(mode_explanation(row))}</div>
  <div class="dc-saving">RL : {eco_rl:.3f} kWh ({eco_dt:.2f} DT) | Combinee : {eco_comb:.3f} kWh</div>
</div>""",
            unsafe_allow_html=True,
        )

        section("Consommation — session")
        hist = sim_data.copy()
        hist["conso"] = _num(hist, "consommation_kwh", 0)
        hist["eco"] = effective_economie_kwh(hist)
        agg = hist.groupby("timestamp", as_index=False).agg(conso=("conso", "sum"), eco=("eco", "sum")).tail(48)
        agg["optimise"] = agg["conso"] - agg["eco"]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=agg["timestamp"], y=agg["conso"], name="Mesuree", line=dict(color="#94a3b8")))
        fig.add_trace(go.Scatter(
            x=agg["timestamp"], y=agg["optimise"], name="Apres NB3",
            line=dict(color="#059669", width=2), fill="tonexty", fillcolor="rgba(5,150,105,0.1)",
        ))
        fig.update_layout(template=template, height=300, margin=dict(l=0, r=0, t=8, b=0), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        eco_sess = float(effective_economie_kwh(sim_data).sum())
        conso_sess = float(_num(sim_data, "consommation_kwh", 0).sum())
        nb_h = int(sim_data["timestamp"].nunique())
        s1, s2, s3 = st.columns(3)
        with s1:
            kpi_card("Session — conso", f"{conso_sess:.1f} kWh", f"{nb_h} pas", "gray")
        with s2:
            kpi_card("Session — economie", f"{eco_sess:.1f} kWh", f"{eco_sess * settings.PRIX_KWH_TN:.1f} DT", "green")
        with s3:
            seuil = float(load_nb2_network_stats().get("seuil_ensemble") or 0.25)
            alertes = int((_num(sim_data, "anomalie_score_ensemble", 0) > seuil).sum())
            kpi_card("Alertes NB2", str(alertes), f"seuil {seuil:.2f}", "orange" if alertes else "eco")
