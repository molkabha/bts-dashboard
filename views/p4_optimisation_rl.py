from __future__ import annotations

import pandas as pd

import plotly.graph_objects as go

import streamlit as st

from config.settings import settings

from config.theme import (
    OPT_ECONOMIE_EXPERT_COLOR,
    OPT_ECONOMIE_RL_COLOR,
    OPT_TOP_STATIONS_COLOR,
    PLOTLY_DARK,
    PLOTLY_LIGHT,
)

from security.middleware import security_middleware

from services.data_service import build_nb3_profil_horaire, compute_filtered_kpis

from services.nb_metrics import harmonize_nb3_economies

from ui.components import header, kpi_card, section

from ui.display import PAGE_OPTIMISATION

from ui.formatting import display_text

from ui.page_helpers import (
    latest_per_station,
    load_dashboard_df,
    render_actions_par_station,
    render_nb3_rl_agents,
)

from ui.utils import active_filter_label, is_admin, session_outputs

_CHART = dict(height=280, margin=dict(l=0, r=0, t=8, b=0))


def _layout(template: str) -> dict:

    return {"template": template, **_CHART}


def _kpi_admin(kpis: dict) -> None:

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        eco_help = kpis.get("economie_periode_label", "Export NB3")

        kpi_card(
            "Économies retenues",
            f"{float(kpis.get('economie_dt') or 0):,.0f} DT",
            eco_help,
            "green",
        )

    with c2:

        kpi_card(
            "kWh retenus",
            f"{float(kpis.get('economie_kwh') or 0):,.0f}",
            f"{float(kpis.get('economie_combinee_pct') or 0):.1f} % de la conso",
            "eco",
        )

    with c3:

        kpi_card("CO₂ évité", f"{float(kpis.get('co2_evite_t') or 0):.2f} t", "", "eco")

    with c4:

        kpi_card("Agent RL", display_text(kpis.get("meilleur_agent_rl")), "", "blue")


def _kpi_engineer(kpis: dict, df: pd.DataFrame) -> None:

    n = int(df["station_id"].nunique()) if "station_id" in df.columns else 0

    c1, c2, c3 = st.columns(3)

    with c1:

        kpi_card("Stations", str(n), "Parc filtré", "blue")

    with c2:

        kpi_card("Mode ECO", f"{float(kpis.get('pct_mode_eco') or 0):.1f} %", "", "eco")

    with c3:

        kpi_card(
            "Conso moyenne",
            f"{float(kpis.get('conso_moyenne_kwh') or 0):.1f} kWh",
            "",
            "gray",
        )


def _single_gain_bar(
    label: str, kwh: float, dt: float, color: str, template: str
) -> go.Figure:

    fig = go.Figure(
        go.Bar(
            x=[label],
            y=[kwh],
            marker_color=color,
            text=[f"{kwh:,.0f} kWh\n{dt:,.0f} DT"],
            textposition="outside",
        )
    )

    fig.update_layout(**_layout(template), yaxis_title="kWh", showlegend=False)

    return fig


def _chart_gains_expert_rl(kpis: dict, template: str) -> None:

    expert_kwh = float(kpis.get("economie_estimee_kwh") or 0)

    rl_kwh = float(kpis.get("economie_rl_kwh") or 0)

    prix = float(settings.PRIX_KWH_TN)

    expert_dt = expert_kwh * prix

    rl_dt = rl_kwh * prix

    c1, c2 = st.columns(2)

    with c1:

        st.plotly_chart(
            _single_gain_bar(
                "Expert (règles)",
                expert_kwh,
                expert_dt,
                OPT_ECONOMIE_EXPERT_COLOR,
                template,
            ),
            width="stretch",
        )

    with c2:

        st.plotly_chart(
            _single_gain_bar("RL", rl_kwh, rl_dt, OPT_ECONOMIE_RL_COLOR, template),
            width="stretch",
        )


def _chart_top_stations(
    df: pd.DataFrame, template: str, *, admin: bool, limit: int = 10
) -> None:

    if df.empty or "station_id" not in df.columns:

        st.info("Données indisponibles.")

        return

    work = harmonize_nb3_economies(df.copy())

    expert = pd.to_numeric(work.get("economie_estimee_kwh"), errors="coerce").fillna(0)

    rl = pd.to_numeric(work.get("economie_rl_kwh"), errors="coerce").fillna(0)

    agg = (
        work.assign(_e=expert, _r=rl)
        .groupby("station_id", as_index=False)
        .agg(expert=("_e", "sum"), rl=("_r", "sum"))
    )

    agg["kwh"] = agg[["expert", "rl"]].max(axis=1)

    if float(agg["kwh"].sum()) <= 0:

        st.info("Aucune économie sur la période.")

        return

    top = agg.nlargest(limit, "kwh").sort_values("kwh", ascending=True)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            y=top["station_id"],
            x=top["kwh"],
            name="Retenu (max/ligne)",
            orientation="h",
            marker_color=OPT_TOP_STATIONS_COLOR,
        )
    )

    fig.update_layout(**_layout(template), xaxis_title="kWh retenus", showlegend=False)

    st.plotly_chart(fig, width="stretch")


def _chart_hourly(df: pd.DataFrame, template: str) -> None:

    hourly = build_nb3_profil_horaire(df)

    if hourly.empty:

        st.info("Profil horaire indisponible.")

        return

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=hourly["heure"],
            y=hourly["conso_moy"],
            name="Référence",
            mode="lines+markers",
        )
    )

    if "conso_optimisee_rl_moy" in hourly.columns:

        fig.add_trace(
            go.Scatter(
                x=hourly["heure"],
                y=hourly["conso_optimisee_rl_moy"],
                name="Après RL",
                mode="lines+markers",
            )
        )

    fig.update_layout(**_layout(template), xaxis_title="Heure", yaxis_title="kWh moy.")

    st.plotly_chart(fig, width="stretch")


def page_optimisation_rl():

    security_middleware.enforce()

    admin = is_admin()

    header(
        PAGE_OPTIMISATION,
        (
            "Actions et économies sur le parc filtré"
            if not admin
            else "Décisions NB3 et gains énergétiques"
        ),
    )

    st.caption(active_filter_label())

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    df = load_dashboard_df(
        [
            "timestamp",
            "station_id",
            "gouvernorat",
            "consommation_kwh",
            "economie_estimee_kwh",
            "economie_rl_kwh",
            "economie_kwh",
            "conso_optimisee_kwh",
            "action_rl",
            "action_proposee",
            "action_principale",
            "mode_operation",
            "eco_potentiel_pct",
            "heure",
        ]
    )

    if df.empty:

        st.warning("Aucune donnée pour les filtres actifs.")

        return

    kpis = compute_filtered_kpis(df)

    if kpis.get("economies_suspectes"):

        st.warning("Économies > 100 % de la conso — vérifiez les exports NB3.")

    if admin:

        _kpi_admin(kpis)

    else:

        _kpi_engineer(kpis, df)

    with section("Actions par station"):

        render_actions_par_station(
            latest_per_station(df), show_savings=admin, per_mode=3
        )

    if admin:

        c1, c2 = st.columns(2)

        with c1:

            with section("Top stations — économies"):

                _chart_top_stations(df, template, admin=True)

        with c2:

            with section("Gains expert & RL"):

                _chart_gains_expert_rl(kpis, template)

        with st.expander("Agents RL et profil horaire"):

            render_nb3_rl_agents(session_outputs().get("nb3", {}), template)

            st.divider()

            _chart_hourly(df, template)

    else:

        with section("Top stations — économies"):

            _chart_top_stations(df, template, admin=False)
