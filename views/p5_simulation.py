"""Page 6 - Simulation temps reel (replay NB3)."""

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
from services.nb_metrics import effective_economie_kwh
from services.nb_replay import load_replay_source, replay_batch, replay_timestamps
from ui.components import context_badge, header, kpi_card, section
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


def _replay_window(
    source_df: pd.DataFrame,
    selected_stations: list[str],
    sim_mode: str,
    sim_base_date,
    start_hour: int,
) -> tuple[datetime | None, datetime | None]:
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


def _advance_replay(
    source_df: pd.DataFrame,
    selected_stations: list[str],
    sim_mode: str,
    sim_base_date,
    start_hour: int,
    steps: int,
) -> bool:
    on_date, start_dt = _replay_window(source_df, selected_stations, sim_mode, sim_base_date, start_hour)
    on_date_arg = on_date if sim_mode == "Une journee" else None
    max_rows = 72 * len(selected_stations)
    injection = st.session_state.get("sim_injection")
    replay_ok = False

    for _ in range(max(1, steps)):
        tick = int(st.session_state.get("sim_tick", 0))
        processed, _ = replay_batch(
            source_df,
            selected_stations,
            tick,
            start_dt=start_dt,
            on_date=on_date_arg,
        )
        if processed.empty:
            st.session_state["sim_running"] = False
            break

        if injection == "heat":
            if "temperature_ambiante" in processed.columns:
                processed["temperature_ambiante"] = _num(processed, "temperature_ambiante", 25) + 15
            processed["consommation_kwh"] = _num(processed, "consommation_kwh", 0) * 1.3
        elif injection == "traffic":
            if "charge_cpu_pct" in processed.columns:
                processed["charge_cpu_pct"] = (_num(processed, "charge_cpu_pct", 0) * 2).clip(0, 99)

        existing = st.session_state.get("sim_data", pd.DataFrame())
        if isinstance(existing, pd.DataFrame) and not existing.empty:
            st.session_state["sim_data"] = pd.concat(
                [existing, processed], ignore_index=True,
            ).tail(max_rows)
        else:
            st.session_state["sim_data"] = processed
        st.session_state["sim_tick"] = tick + 1
        replay_ok = True

    if injection:
        st.session_state.pop("sim_injection", None)
    return replay_ok


def _render_instant_kpis(latest_all: pd.DataFrame) -> None:
    conso = float(_num(latest_all, "consommation_kwh", 0).sum())
    cpu = float(_num(latest_all, "charge_cpu_pct", 0).mean())
    temp = float(_num(latest_all, "temperature_ambiante", 25).mean())
    eco = float(effective_economie_kwh(latest_all).sum())
    qos = float(_num(latest_all, "score_qos", 0.75).mean())
    eco_dt = eco * settings.PRIX_KWH_TN

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("Consommation", f"{conso:.2f} kWh", "Pas horaire actuel", "blue")
    with c2:
        kpi_card("Charge CPU", f"{cpu:.0f} %", "Moyenne stations", "gray")
    with c3:
        kpi_card("Temperature", f"{temp:.1f} °C", "Ambiante", "orange")
    with c4:
        kpi_card("Economie RL", f"{eco:.2f} kWh", f"{eco_dt:.2f} DT", "green")
    with c5:
        kpi_card("QoS", f"{qos:.2f}", "Qualite de service", "eco" if qos >= 0.75 else "danger")


def _render_decision_cards(latest_all: pd.DataFrame, multi: bool) -> None:
    prio = {"CRITIQUE": 0, "ATTENTION": 1, "NORMAL": 2, "ECO": 3}
    rows = latest_all.copy()
    rows["_prio"] = rows["mode_operation"].astype(str).map(lambda m: prio.get(m, 9)) if "mode_operation" in rows.columns else 9
    rows = rows.sort_values("_prio")

    for _, row in rows.iterrows():
        sid = str(row.get("station_id", ""))
        mode = str(row.get("mode_operation", "NORMAL"))
        color = MODE_COLORS.get(mode, "#64748b")
        action = str(row.get("action_proposee", row.get("action_rl", "Supervision")))
        eco_kwh = float(effective_economie_kwh(pd.DataFrame([row])).iloc[0])
        eco_dt = eco_kwh * settings.PRIX_KWH_TN
        expl = mode_explanation(row)
        title = f"{sid} — {mode}" if multi else mode
        st.markdown(
            f"""
<div class="decision-card" style="border-left-color:{color};">
  <div class="dc-mode" style="color:{color};">{html.escape(title)}</div>
  <div class="dc-action">{html.escape(action)}</div>
  <div class="dc-reason">{html.escape(expl)}</div>
  <div class="dc-saving">Economie : {eco_dt:.2f} DT | {eco_kwh:.3f} kWh</div>
</div>""",
            unsafe_allow_html=True,
        )


def _render_consumption_chart(sim_data: pd.DataFrame, template: dict) -> None:
    history = sim_data.copy()
    history["consommation_kwh"] = _num(history, "consommation_kwh", 0)
    history["economie_kwh"] = effective_economie_kwh(history)
    agg = history.groupby("timestamp").agg(
        baseline=("consommation_kwh", "sum"),
        eco=("economie_kwh", "sum"),
    ).reset_index().tail(48)
    agg["optimise"] = agg["baseline"] - agg["eco"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=agg["timestamp"], y=agg["baseline"], name="Baseline",
        line=dict(color="#94a3b8", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=agg["timestamp"], y=agg["optimise"], name="Avec optimisation NB3",
        line=dict(color="#059669", width=2.5), fill="tonexty", fillcolor="rgba(5,150,105,0.12)",
    ))
    fig.update_layout(
        template=template,
        height=340,
        margin=dict(l=0, r=0, t=24, b=0),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, width="stretch")


def _render_snapshot_table(latest_all: pd.DataFrame) -> None:
    tbl = latest_all.copy()
    tbl["economie_pas_kwh"] = effective_economie_kwh(tbl)
    cols = [
        c for c in [
            "station_id", "mode_operation", "action_proposee", "consommation_kwh",
            "charge_cpu_pct", "temperature_ambiante", "score_qos", "economie_pas_kwh",
            "anomalie_score_ensemble",
        ]
        if c in tbl.columns
    ]
    if cols:
        display = tbl[cols].copy()
        rename = {
            "station_id": "Station",
            "mode_operation": "Mode",
            "action_proposee": "Action",
            "consommation_kwh": "Conso (kWh)",
            "charge_cpu_pct": "CPU (%)",
            "temperature_ambiante": "Temp (°C)",
            "score_qos": "QoS",
            "economie_pas_kwh": "Economie (kWh)",
            "anomalie_score_ensemble": "Score anomalie",
        }
        display = display.rename(columns={k: v for k, v in rename.items() if k in display.columns})
        st.dataframe(display, width="stretch", hide_index=True)


def _session_summary(sim_data: pd.DataFrame) -> None:
    conso = _num(sim_data, "consommation_kwh", 0)
    eco_best = effective_economie_kwh(sim_data)
    total_conso = float(conso.sum())
    total_eco = float(eco_best.sum())
    total_dt = total_eco * settings.PRIX_KWH_TN
    co2_kg = total_eco * settings.FACTEUR_CO2_TN
    nb_heures = int(sim_data["timestamp"].nunique()) if "timestamp" in sim_data.columns else len(sim_data)
    seuil = float(load_nb2_network_stats().get("seuil_ensemble") or 0.25)
    nb_anomalies = int((_num(sim_data, "anomalie_score_ensemble", 0) > seuil).sum())
    qos_moy = float(_num(sim_data, "score_qos", 0.75).mean())

    with section("Bilan de la session"):
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            kpi_card("Consommation cumulee", f"{total_conso:.1f} kWh", f"{nb_heures} pas horaires", "gray")
        with k2:
            kpi_card("Economie RL cumulee", f"{total_eco:.1f} kWh", f"{total_dt:.2f} DT", "green")
        with k3:
            kpi_card("CO2 evite", f"{co2_kg:.2f} kg", "", "blue")
        with k4:
            kpi_card("QoS moyenne", f"{qos_moy:.2f}", f"{nb_anomalies} alertes", "eco" if qos_moy > 0.75 else "danger")


def page_simulation():
    security_middleware.enforce()
    role = st.session_state.get("role", "")
    header("Simulation", "Replay horaire NB1 / NB2 / NB3 — donnees reelles filtrees")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    st.caption(active_filter_label())

    stations = _station_options(role)
    if not stations:
        st.warning("Aucune station disponible pour les filtres actifs.")
        return

    col_ctrl, col_main = st.columns([1, 2.6])

    with col_ctrl:
        with section("Parametres replay"):
            default_pick = st.session_state.get("sim_stations") or stations[:1]
            default_pick = [s for s in default_pick if s in stations] or stations[:1]
            selected_stations = st.multiselect(
                "Station(s)",
                stations,
                default=default_pick,
                key="sim_stations",
            )

            sim_mode = st.radio(
                "Periode",
                ["Toutes les dates filtrees", "Une journee"],
                key="sim_mode",
                horizontal=True,
            )
            sim_base_date = datetime.now().date()
            start_hour = 0
            if sim_mode == "Une journee":
                bounds = load_dashboard_df(["timestamp"])
                if not bounds.empty and "timestamp" in bounds.columns:
                    ts = pd.to_datetime(bounds["timestamp"], errors="coerce").dropna()
                    if not ts.empty:
                        sim_base_date = st.date_input(
                            "Jour",
                            value=ts.min().date(),
                            min_value=ts.min().date(),
                            max_value=ts.max().date(),
                            key="sim_date",
                        )
                else:
                    sim_base_date = st.date_input("Jour", value=datetime.now().date(), key="sim_date")
                start_hour = st.slider("Heure de depart", 0, 23, 0, key="sim_start_hour")

            speed = st.select_slider(
                "Vitesse",
                options=[1, 2, 5, 10],
                value=2,
                format_func=lambda x: f"{x} pas / clic",
                key="sim_speed",
            )
            st.checkbox("Avancement automatique", value=False, key="sim_auto")

            bc1, bc2, bc3 = st.columns(3)
            with bc1:
                btn_start = st.button("Demarrer", type="primary", width="stretch")
            with bc2:
                btn_step = st.button("Pas suivant", width="stretch")
            with bc3:
                btn_reset = st.button("Reset", width="stretch")

            if btn_reset:
                for key in ("sim_data", "sim_running", "sim_tick", "sim_source_df", "sim_injection", "sim_total_ticks"):
                    st.session_state.pop(key, None)
                st.rerun()

            if btn_start:
                source_df = load_replay_source()
                st.session_state["sim_running"] = True
                st.session_state["sim_tick"] = 0
                st.session_state["sim_data"] = pd.DataFrame()
                st.session_state["sim_source_df"] = source_df
                on_date, start_dt = _replay_window(
                    source_df, selected_stations, sim_mode, sim_base_date, start_hour,
                )
                st.session_state["sim_total_ticks"] = len(replay_timestamps(
                    source_df, selected_stations, start_dt,
                    on_date=on_date if sim_mode == "Une journee" else None,
                ))
                st.session_state["sim_advance"] = True

            if btn_step and st.session_state.get("sim_running"):
                st.session_state["sim_advance"] = True

            if role == "admin":
                with st.expander("Injection scenario", expanded=False):
                    if st.button("Pic chaleur", key="inj_heat", width="stretch"):
                        st.session_state["sim_injection"] = "heat"
                    if st.button("Surcharge trafic", key="inj_traffic", width="stretch"):
                        st.session_state["sim_injection"] = "traffic"

            total_ticks = int(st.session_state.get("sim_total_ticks") or 0)
            current_tick = int(st.session_state.get("sim_tick", 0))
            if total_ticks > 0:
                st.progress(min(1.0, current_tick / total_ticks))
                st.caption(f"Progression : {current_tick} / {total_ticks} pas horaires")

            sim_data = st.session_state.get("sim_data")
            if isinstance(sim_data, pd.DataFrame) and not sim_data.empty:
                with st.expander("Export session", expanded=False):
                    download_df_button(sim_data, "session_simulation.csv", "Exporter CSV")

    with col_main:
        if not selected_stations:
            st.info("Selectionnez au moins une station dans le panneau de gauche.")
            return

        advance_manual = st.session_state.pop("sim_advance", False)
        advance_auto = False
        if st.session_state.get("sim_auto") and st.session_state.get("sim_running"):
            interval_ms = max(800, 350 * int(st.session_state.get("sim_speed", 2)))
            refresh_count = st_autorefresh(interval=interval_ms, key="sim_autorefresh")
            advance_auto = refresh_count > 0

        should_advance = (advance_manual or advance_auto) and st.session_state.get("sim_running")

        if should_advance:
            source_df = st.session_state.get("sim_source_df")
            if not isinstance(source_df, pd.DataFrame) or source_df.empty:
                source_df = load_replay_source()
                st.session_state["sim_source_df"] = source_df

            replay_ok = _advance_replay(
                source_df,
                selected_stations,
                sim_mode,
                sim_base_date,
                start_hour,
                int(st.session_state.get("sim_speed", 1)),
            )
            if not replay_ok and not st.session_state.get("sim_running"):
                st.warning(
                    "Fin du replay ou aucune mesure pour cette selection. "
                    "Elargissez les filtres sidebar (dates, gouvernorat) ou changez le jour."
                )

        sim_data = st.session_state.get("sim_data")
        if not isinstance(sim_data, pd.DataFrame) or sim_data.empty:
            st.markdown(
                """
<div class="alert info">
  <div style="flex:1">
    <div class="alert-title">Replay en attente</div>
    <div class="alert-body">Choisissez une ou plusieurs stations, puis cliquez sur <strong>Demarrer</strong>.
    Utilisez <strong>Pas suivant</strong> ou l'avancement automatique pour parcourir les mesures horaires NB.</div>
  </div>
</div>""",
                unsafe_allow_html=True,
            )
            return

        if "timestamp" not in sim_data.columns:
            st.warning("Donnees replay sans horodatage.")
            return

        latest_ts = sim_data["timestamp"].max()
        latest_all = sim_data[sim_data["timestamp"] == latest_ts]
        multi = len(selected_stations) > 1

        context_badge("Horodatage", str(latest_ts)[:19], "info")
        if st.session_state.get("sim_running"):
            context_badge("Etat", "En cours", "success")
        else:
            context_badge("Etat", "Pause / termine", "warning")

        _render_instant_kpis(latest_all)

        with section("Decision RL — pas actuel"):
            _render_decision_cards(latest_all, multi)

        with section("Evolution consommation (session)"):
            _render_consumption_chart(sim_data, template)

        with section("Instantane stations"):
            _render_snapshot_table(latest_all)

        _session_summary(sim_data)
