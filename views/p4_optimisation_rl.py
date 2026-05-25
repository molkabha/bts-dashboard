"""Page NB3 — Optimisation."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from config.theme import MODE_COLORS, MODE_ORDER, PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import (
    artifact_path,
    build_nb3_profil_horaire,
    compute_filtered_kpis,
    dashboard_data_coverage,
)
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

_CHART_HEIGHT = 300
_CHART_MARGIN = dict(l=0, r=0, t=12, b=0)


def _chart_layout(template: str, *, height: int = _CHART_HEIGHT) -> dict:
    return {"template": template, "height": height, "margin": _CHART_MARGIN}


def _render_summary_strip(kpis: dict, nb_stations: int, *, admin: bool) -> None:
    items: list[tuple[str, str, str]] = []
    if admin:
        items.extend([
            ("Économies", f"{float(kpis.get('economie_dt') or 0):,.0f} DT", "Période filtrée"),
            ("kWh économisés", f"{float(kpis.get('economie_kwh') or 0):,.0f}", f"{float(kpis.get('economie_combinee_pct') or 0):.1f} % de la conso"),
            ("CO₂ évité", f"{float(kpis.get('co2_evite_t') or 0):.2f} t", "Facteur TN"),
            ("Stations", str(nb_stations), f"Mode ECO : {float(kpis.get('pct_mode_eco') or 0):.1f} %"),
        ])
    else:
        items.extend([
            ("Stations", str(nb_stations), "Parc filtré"),
            ("Mode ECO", f"{float(kpis.get('pct_mode_eco') or 0):.1f} %", "Dernier état / station"),
            ("Conso moyenne", f"{float(kpis.get('conso_moyenne_kwh') or 0):.1f} kWh", "Période filtrée"),
        ])
    blocks = []
    for label, value, help_txt in items:
        blocks.append(
            f'<div class="opt-summary-item">'
            f'<div class="osi-label">{html.escape(label)}</div>'
            f'<div class="osi-value">{html.escape(value)}</div>'
            f'<div class="osi-help">{html.escape(help_txt)}</div>'
            f"</div>",
        )
    st.markdown(f'<div class="opt-summary">{"".join(blocks)}</div>', unsafe_allow_html=True)


def _render_admin_kpis(kpis: dict) -> None:
    eco_reg = float(kpis.get("economie_estimee_kwh") or 0)
    eco_rl = float(kpis.get("economie_rl_kwh") or 0)
    delta_rl = ""
    if eco_reg > 0 and eco_rl > 0:
        diff_pct = (eco_rl - eco_reg) / eco_reg * 100
        delta_rl = f"RL {diff_pct:+.0f} % vs règles"
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card(
            "Économies",
            f"{float(kpis.get('economie_dt') or 0):,.0f} DT",
            kpis.get("economie_periode_label", "Période filtrée"),
            "green",
        )
    with c2:
        kpi_card(
            "kWh combinés",
            f"{float(kpis.get('economie_kwh') or 0):,.0f}",
            f"{float(kpis.get('economie_combinee_pct') or 0):.1f} % conso",
            "eco",
            delta=delta_rl,
            delta_class="kpi-delta up" if eco_rl >= eco_reg else "kpi-delta down",
        )
    with c3:
        kpi_card("CO₂ évité", f"{float(kpis.get('co2_evite_t') or 0):.2f} t", "", "eco")
    with c4:
        kpi_card("Agent RL", display_text(kpis.get("meilleur_agent_rl")), "Meilleur sur la période", "blue")


def _render_engineer_kpis(kpis: dict, df: pd.DataFrame) -> None:
    n = int(df["station_id"].nunique()) if "station_id" in df.columns else 0
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Stations", str(n), "Parc filtré", "blue")
    with c2:
        kpi_card("Mode ECO", f"{float(kpis.get('pct_mode_eco') or 0):.1f} %", "Dernier état", "eco")
    with c3:
        kpi_card("Conso moyenne", f"{float(kpis.get('conso_moyenne_kwh') or 0):.1f} kWh", "Période filtrée", "gray")


def _render_mode_chips(latest: pd.DataFrame) -> None:
    if latest.empty or "mode_operation" not in latest.columns:
        return
    counts = latest["mode_operation"].astype(str).map(lambda m: m.strip().upper()).value_counts()
    chips = []
    for mode in MODE_ORDER:
        n = int(counts.get(mode, 0))
        if n <= 0:
            continue
        color = MODE_COLORS.get(mode, "#64748b")
        chips.append(
            f'<span class="opt-mode-chip">'
            f'<span class="omc-dot" style="background:{color};"></span>'
            f'{html.escape(mode)} <strong>{n}</strong></span>',
        )
    if chips:
        st.markdown(f'<div class="opt-mode-chips">{"".join(chips)}</div>', unsafe_allow_html=True)


def _chart_regles_vs_rl(kpis: dict, template: str) -> None:
    eco_reg = float(kpis.get("economie_estimee_kwh") or 0)
    eco_rl = float(kpis.get("economie_rl_kwh") or 0)
    conso = float(kpis.get("conso_totale_kwh") or 0)
    pct_reg = (eco_reg / conso * 100) if conso > 0 else 0.0
    pct_rl = (eco_rl / conso * 100) if conso > 0 else 0.0

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=["Règles expertes", "Reinforcement learning"],
            y=[eco_reg, eco_rl],
            marker_color=["#1e3a8a", "#059669"],
            text=[f"{eco_reg:,.0f} kWh<br>({pct_reg:.1f} %)", f"{eco_rl:,.0f} kWh<br>({pct_rl:.1f} %)"],
            textposition="outside",
        ),
    )
    fig.update_layout(
        **_chart_layout(template),
        yaxis_title="kWh économisés",
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")


def _chart_rl_learning(nb3: dict, template: str) -> None:
    candidates = [
        settings.NB3_OUTPUT / "rl_7agents_apprentissage.png",
        artifact_path("rl_7agents_apprentissage.png"),
    ]
    for img_path in candidates:
        if isinstance(img_path, Path) and img_path.exists():
            st.image(str(img_path), use_container_width=True)
            return

    rl_data = nb3.get("rl_resultats_tous_agents", {})
    if not rl_data:
        st.info("Courbe d'apprentissage indisponible — ajoutez `rl_7agents_apprentissage.png` ou `rapport_optimisation.json`.")
        return

    df_rl = pd.DataFrame.from_dict(rl_data, orient="index").reset_index(names="Agent")
    if "economie_pct" not in df_rl.columns:
        st.info("Résultats agents sans colonne `economie_pct`.")
        return
    df_rl["economie_pct"] = pd.to_numeric(df_rl["economie_pct"], errors="coerce")
    df_rl = df_rl.sort_values("economie_pct", ascending=True)
    best = str(nb3.get("meilleur_agent") or "")
    colors = ["#059669" if str(a) == best else "#1e3a8a" for a in df_rl["Agent"]]
    fig = go.Figure(go.Bar(x=df_rl["economie_pct"], y=df_rl["Agent"], orientation="h", marker_color=colors))
    fig.update_layout(**_chart_layout(template), xaxis_title="Économie %", yaxis_title="")
    st.plotly_chart(fig, width="stretch")


def _chart_hourly_profile(df: pd.DataFrame, template: str, *, admin: bool) -> None:
    hourly = build_nb3_profil_horaire(df)
    if hourly.empty:
        st.info("Profil horaire indisponible — colonnes `heure` et `consommation_kwh` requises.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hourly["heure"],
            y=hourly["conso_moy"],
            name="Référence",
            mode="lines+markers",
            line=dict(color="#64748b", width=2),
        ),
    )
    if admin and "conso_optimisee_moy" in hourly.columns:
        fig.add_trace(
            go.Scatter(
                x=hourly["heure"],
                y=hourly["conso_optimisee_moy"],
                name="Après règles",
                mode="lines+markers",
                line=dict(color="#1e3a8a", width=2, dash="dash"),
            ),
        )
    if admin and "conso_optimisee_rl_moy" in hourly.columns:
        fig.add_trace(
            go.Scatter(
                x=hourly["heure"],
                y=hourly["conso_optimisee_rl_moy"],
                name="Après RL",
                mode="lines+markers",
                line=dict(color="#059669", width=2),
            ),
        )
    fig.update_layout(
        **_chart_layout(template),
        xaxis_title="Heure",
        yaxis_title="kWh moyen",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(fig, width="stretch")


def _chart_top_station_economies(df: pd.DataFrame, template: str, *, admin: bool, limit: int = 12) -> None:
    """Top stations par kWh économisés sur la période (utile pour prioriser le parc)."""
    if df.empty or "station_id" not in df.columns:
        st.info("Économies par station indisponibles.")
        return

    work = harmonize_nb3_economies(df.copy())
    sid = work["station_id"].astype(str).str.strip()
    work = work[sid.notna() & sid.ne("") & sid.str.lower().ne("none")]

    has_expert = "economie_estimee_kwh" in work.columns
    has_rl = "economie_rl_kwh" in work.columns
    if not has_expert and not has_rl and "economie_kwh" not in work.columns:
        st.info("Colonnes d'économie NB3 absentes sur la période filtrée.")
        return

    expert = (
        pd.to_numeric(work["economie_estimee_kwh"], errors="coerce").fillna(0)
        if has_expert
        else pd.Series(0.0, index=work.index)
    )
    rl = (
        pd.to_numeric(work["economie_rl_kwh"], errors="coerce").fillna(0)
        if has_rl
        else pd.Series(0.0, index=work.index)
    )
    work = work.assign(_expert=expert, _rl=rl)
    agg = work.groupby("station_id", as_index=False).agg(
        expert_kwh=("_expert", "sum"),
        rl_kwh=("_rl", "sum"),
    )
    agg["combine_kwh"] = agg[["expert_kwh", "rl_kwh"]].max(axis=1)
    if float(agg["combine_kwh"].sum()) <= 0:
        st.info("Aucune économie enregistrée sur la période filtrée.")
        return

    top = agg.nlargest(limit, "combine_kwh").sort_values("combine_kwh", ascending=True)
    fig = go.Figure()
    if admin and has_expert and has_rl:
        fig.add_trace(
            go.Bar(
                y=top["station_id"],
                x=top["expert_kwh"],
                name="Règles expertes",
                orientation="h",
                marker_color="#1e3a8a",
            ),
        )
        fig.add_trace(
            go.Bar(
                y=top["station_id"],
                x=top["rl_kwh"],
                name="RL",
                orientation="h",
                marker_color="#059669",
            ),
        )
        fig.update_layout(barmode="group")
    else:
        fig.add_trace(
            go.Bar(
                y=top["station_id"],
                x=top["combine_kwh"],
                name="Économie",
                orientation="h",
                marker_color="#059669",
            ),
        )
    fig.update_layout(
        **_chart_layout(template),
        xaxis_title="kWh économisés (somme période)",
        yaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(fig, width="stretch")


def _render_data_provenance(df: pd.DataFrame, kpis: dict) -> None:
    with section("Couverture des colonnes NB3"):
        st.markdown(
            '<p class="opt-chart-note">Taux de remplissage sur la période filtrée — '
            "les KPI sont des sommes ligne à ligne, pas des pourcentages réseau extrapolés.</p>",
            unsafe_allow_html=True,
        )
        cov = dashboard_data_coverage(df)
        if not cov.empty:
            st.dataframe(cov, width="stretch", hide_index=True)

    if "action_proposee" in df.columns:
        actions = df["action_proposee"].astype(str).str.strip().str.lower()
        pct_aa = float((actions == "aucune_action").mean() * 100)
        st.caption(
            f"Lignes « Aucune action » (expert) : {pct_aa:.1f} % — fréquent en mode NORMAL/ECO."
        )
    if "source_decision_nb3" in df.columns:
        nb3_rows = int(df["source_decision_nb3"].astype(str).eq("NB3").sum())
        st.caption(f"Décisions NB3 fusionnées : {nb3_rows:,} / {len(df):,} lignes.")

    ref_pct = kpis.get("nb3_ref_economie_combinee_pct")
    if ref_pct is not None and float(kpis.get("economie_kwh") or 0) <= 0:
        st.warning(
            f"Économies à 0 sur la période. Référence réseau (kpi_reseau.json) : "
            f"{float(ref_pct):.1f} % — indicatif uniquement."
        )


def _render_synthesis(df: pd.DataFrame, kpis: dict, template: str, *, admin: bool) -> None:
    latest = latest_per_station(df)
    _render_mode_chips(latest)

    if "station_id" in df.columns:
        with section("Actions par station"):
            st.markdown(
                '<p class="opt-chart-note">Dernière décision par station — '
                f"jusqu'à 3 exemples par mode (CRITIQUE → ECO).</p>",
                unsafe_allow_html=True,
            )
            render_actions_par_station(latest, show_savings=admin, per_mode=3)

    c1, c2 = st.columns(2)
    with c1:
        with section("Profil horaire"):
            st.markdown(
                '<p class="opt-chart-note">Consommation moyenne par heure sur la période filtrée.</p>',
                unsafe_allow_html=True,
            )
            _chart_hourly_profile(df, template, admin=admin)
    with c2:
        with section("Top stations — économies"):
            st.markdown(
                '<p class="opt-chart-note">Stations où l\'optimisation génère le plus de kWh '
                "économisés sur la période filtrée (priorisation terrain).</p>",
                unsafe_allow_html=True,
            )
            _chart_top_station_economies(df, template, admin=admin)


def _render_performance_rl(kpis: dict, nb3: dict, template: str) -> None:
    c1, c2 = st.columns(2)
    with c1:
        with section("Règles expertes vs RL"):
            st.markdown(
                '<p class="opt-chart-note">Sommes `economie_estimee_kwh` et `economie_rl_kwh` '
                f"sur la période — combiné retenu : {float(kpis.get('economie_kwh') or 0):,.0f} kWh.</p>",
                unsafe_allow_html=True,
            )
            _chart_regles_vs_rl(kpis, template)
    with c2:
        with section("Agents RL"):
            st.markdown(
                '<p class="opt-chart-note">Comparaison des 7 agents (export NB3) — barre verte = agent retenu.</p>',
                unsafe_allow_html=True,
            )
            _chart_rl_learning(nb3, template)

    with section("Tableau comparatif des agents"):
        render_nb3_rl_agents(nb3, template)


def page_optimisation_rl():
    security_middleware.enforce()

    subtitle = "Économies, modes et actions sur le parc filtré"
    if is_admin():
        subtitle = "Synthèse NB3 — règles expertes, RL et profil horaire"
    header(PAGE_OPTIMISATION, subtitle)
    st.caption(active_filter_label())

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    nb3 = session_outputs().get("nb3", {})
    df = load_dashboard_df([
        "timestamp", "station_id", "gouvernorat", "consommation_kwh",
        "economie_estimee_kwh", "economie_rl_kwh", "action_rl", "action_proposee",
        "action_principale", "mode_operation", "heure",
    ])
    if df.empty:
        st.warning("Aucune donnée pour les filtres actifs.")
        return

    kpis = compute_filtered_kpis(df)
    nb_stations = int(df["station_id"].nunique()) if "station_id" in df.columns else 0

    if kpis.get("economies_suspectes"):
        st.warning(
            "Les économies dépassent la consommation filtrée (> 100 %). "
            "Vérifiez `streamlit_data.parquet` ou republiez le jeu de données."
        )

    _render_summary_strip(kpis, nb_stations, admin=is_admin())

    if is_admin():
        _render_admin_kpis(kpis)
        tab_syn, tab_perf, tab_data = st.tabs(["Synthèse opérationnelle", "Performance RL", "Source des données"])
        with tab_syn:
            _render_synthesis(df, kpis, template, admin=True)
        with tab_perf:
            _render_performance_rl(kpis, nb3, template)
        with tab_data:
            _render_data_provenance(df, kpis)
    else:
        _render_engineer_kpis(kpis, df)
        _render_synthesis(df, kpis, template, admin=False)
