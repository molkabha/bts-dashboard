"""Shared data-loading and NB UI helpers for dashboard pages."""

from __future__ import annotations

import html

import plotly.express as px
import pandas as pd
import streamlit as st

from config.settings import settings
from config.theme import mode_color

from services.data_service import (
    compute_filtered_kpis,
    dataset_cache_key,
    load_filtered_main_data,
    load_station_map_data,
)
from services.nb_metrics import effective_economie_kwh
from ui.formatting import display_text, resolve_row_action, row_has_no_named_action
from ui.utils import apply_current_admin_filters, filters_cache_key

DEFAULT_COLS = [
    "timestamp", "station_id", "gouvernorat", "technologie", "type_zone",
    "consommation_kwh", "conso_predite", "pred_q10", "pred_q90",
    "anomalie_score_ensemble", "nb_votes_anomalie", "score_qos",
    "mode_operation", "action_proposee", "action_principale",
    "economie_estimee_kwh", "economie_rl_kwh", "economie_kwh", "ecart_pct",
    "heure", "jour_semaine", "mois", "charge_cpu_pct",
    "latitude", "longitude", "meilleur_agent_rl",
]


def get_station_map_data(df: pd.DataFrame) -> pd.DataFrame:
    """Session-cached station map positions for the current filter context."""
    station_token = ""
    if not df.empty and "station_id" in df.columns:
        station_token = str(hash(tuple(sorted(df["station_id"].astype(str).unique()))))
    cache_id = f"{dataset_cache_key()}|{filters_cache_key()}|{station_token}"
    if st.session_state.get("_map_data_key") == cache_id:
        cached = st.session_state.get("_map_data_val")
        if isinstance(cached, pd.DataFrame):
            return cached
    result = load_station_map_data(df)
    st.session_state["_map_data_key"] = cache_id
    st.session_state["_map_data_val"] = result
    return result


def load_dashboard_df(
    extra_cols: list[str] | None = None,
    *,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Load filtered dashboard data with per-rerun session cache."""
    if columns is not None:
        use = list(dict.fromkeys(list(columns) + settings.TEMPORAL_COLUMNS))
        cols = tuple(use)
    else:
        cols = tuple(dict.fromkeys(DEFAULT_COLS + (extra_cols or [])))
    session_key = f"{dataset_cache_key()}|{filters_cache_key()}|{cols}"
    cached = st.session_state.get("_df_session_val")
    if st.session_state.get("_df_session_key") == session_key and isinstance(cached, pd.DataFrame):
        if all(c in cached.columns for c in cols):
            return cached
    df = apply_current_admin_filters(load_filtered_main_data(list(cols)))
    st.session_state["_df_session_key"] = session_key
    st.session_state["_df_session_val"] = df
    return df


def render_conso_gouvernorat_par_periode(
    df: pd.DataFrame,
    template: str,
    *,
    show_page_filters: bool = False,
) -> None:
    """Bar charts: mean kWh by governorate and month (respects sidebar filters on df)."""
    from ui.utils import active_filter_label, merged_active_filters

    if df.empty:
        st.warning("Aucune donnée pour les filtres actifs.")
        return

    st.caption(active_filter_label())

    top_govs: list[str] | None = None
    if show_page_filters and "gouvernorat" in df.columns:
        avail = sorted(df["gouvernorat"].dropna().astype(str).unique().tolist())
        c1, c2 = st.columns([2, 1])
        with c1:
            picked = st.multiselect(
                "Gouvernorats à comparer",
                avail,
                key="cmp_chart_govs",
                placeholder="Tous (top par consommation)",
            )
        with c2:
            top_n = st.number_input("Max. gouvernorats", min_value=3, max_value=24, value=10, key="cmp_chart_top_n")
        top_govs = picked if picked else None
        if not top_govs:
            top_govs = (
                df.groupby("gouvernorat")["consommation_kwh"]
                .sum()
                .sort_values(ascending=False)
                .head(int(top_n))
                .index.astype(str)
                .tolist()
            )

    if "gouvernorat" not in df.columns or "consommation_kwh" not in df.columns:
        st.info("Colonnes gouvernorat / consommation indisponibles.")
        return

    if "timestamp" not in df.columns:
        work = df
        if top_govs:
            work = work[work["gouvernorat"].astype(str).isin(top_govs)]
        by_gov = work.groupby("gouvernorat", as_index=False)["consommation_kwh"].mean()
        by_gov = by_gov.rename(columns={"consommation_kwh": "conso_moy_kwh"}).sort_values("conso_moy_kwh", ascending=True)
        fig = px.bar(by_gov, x="conso_moy_kwh", y="gouvernorat", orientation="h", template=template)
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, width="stretch")
        return

    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work = work.dropna(subset=["timestamp", "gouvernorat"])
    if top_govs:
        work = work[work["gouvernorat"].astype(str).isin(top_govs)]
    if work.empty:
        st.warning("Aucune ligne après filtrage gouvernorat.")
        return

    work["periode"] = work["timestamp"].dt.to_period("M").astype(str)
    by_period = (
        work.groupby(["periode", "gouvernorat"], as_index=False)["consommation_kwh"]
        .mean()
        .rename(columns={"consommation_kwh": "conso_moy_kwh"})
        .sort_values("periode")
    )
    if top_govs is None:
        top_govs = (
            work.groupby("gouvernorat")["consommation_kwh"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .index.astype(str)
            .tolist()
        )
    chart_df = by_period[by_period["gouvernorat"].astype(str).isin(top_govs)]

    fig_period = px.bar(
        chart_df,
        x="periode",
        y="conso_moy_kwh",
        color="gouvernorat",
        barmode="group",
        template=template,
        labels={
            "periode": "Période (mois)",
            "conso_moy_kwh": "Consommation moyenne (kWh)",
            "gouvernorat": "Gouvernorat",
        },
        title="Moyenne par mois et par gouvernorat",
    )
    fig_period.update_layout(height=340, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_period, width="stretch")

    gf = merged_active_filters()
    if gf.get("date_range"):
        start, end = gf["date_range"]
        period_label = f"Période filtrée : {start} → {end}"
    elif not chart_df.empty:
        period_label = f"Periodes : {chart_df['periode'].min()} → {chart_df['periode'].max()}"
    else:
        period_label = ""
    st.caption(f"{period_label} · {len(top_govs)} gouvernorat(s)".strip(" · "))

    by_gov = (
        work.groupby("gouvernorat", as_index=False)["consommation_kwh"]
        .mean()
        .rename(columns={"consommation_kwh": "conso_moy_kwh"})
        .sort_values("conso_moy_kwh", ascending=True)
    )
    fig_gov = px.bar(
        by_gov,
        x="conso_moy_kwh",
        y="gouvernorat",
        orientation="h",
        template=template,
        labels={"conso_moy_kwh": "Conso. moyenne (kWh)", "gouvernorat": "Gouvernorat"},
        title="Moyenne sur la période sélectionnée",
    )
    fig_gov.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_gov, width="stretch")


def latest_per_station(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "station_id" not in df.columns:
        return df
    if "timestamp" in df.columns:
        return df.sort_values("timestamp").groupby("station_id", as_index=False).last()
    return df.groupby("station_id", as_index=False).last()


def render_nb3_decision_cards(latest: pd.DataFrame, limit: int = 12, *, show_savings: bool = True) -> None:
    prio = {"CRITIQUE": 0, "ATTENTION": 1, "NORMAL": 2, "ECO": 3}
    work = latest.copy()
    if "station_id" in work.columns:
        sid = work["station_id"].astype(str).str.strip()
        work = work[sid.notna() & sid.ne("") & sid.str.lower().ne("none") & sid.str.lower().ne("nan")]
    work["_prio"] = work["mode_operation"].astype(str).map(lambda m: prio.get(m, 9))
    for _, row in work.sort_values("_prio").head(limit).iterrows():
        mode = display_text(row.get("mode_operation"), "NORMAL")
        color = mode_color(mode)
        action = resolve_row_action(row, prefer_rl=show_savings)
        saving_html = ""
        if show_savings:
            eco_series = effective_economie_kwh(pd.DataFrame([row]))
            eco_kwh = float(eco_series.iloc[0]) if not eco_series.empty else 0.0
            if eco_kwh > 0:
                eco_dt = eco_kwh * settings.PRIX_KWH_TN
                if row_has_no_named_action(row):
                    saving_html = (
                        f'<div class="dc-saving">Potentiel mode : {eco_dt:.2f} DT · {eco_kwh:.2f} kWh</div>'
                    )
                else:
                    saving_html = f'<div class="dc-saving">{eco_dt:.2f} DT · {eco_kwh:.2f} kWh</div>'
        sid = str(row.get("station_id", ""))
        st.markdown(f"""
<div class="decision-card" style="border-left-color:{color};">
  <div class="dc-mode" style="color:{color};">{html.escape(sid)} · {html.escape(mode)}</div>
  <div class="dc-action">{html.escape(action)}</div>
  {saving_html}
</div>""", unsafe_allow_html=True)


def render_nb3_rl_agents(nb3: dict, template: str) -> None:
    rl_data = nb3.get("rl_resultats_tous_agents", {})
    if not rl_data:
        st.caption("Données agents non disponibles.")
        return
    df_rl = pd.DataFrame.from_dict(rl_data, orient="index").reset_index(names="Agent")
    if "economie_pct" in df_rl.columns:
        df_rl["economie_pct"] = pd.to_numeric(df_rl["economie_pct"], errors="coerce")
        df_rl = df_rl.sort_values("economie_pct", ascending=False)
    st.dataframe(df_rl, width="stretch", hide_index=True)


def mode_explanation(row: pd.Series) -> str:
    from ui.formatting import format_action_label

    mode = str(row.get("mode_operation", "NORMAL"))
    score = float(row.get("anomalie_score_ensemble", 0) or 0)
    ecart = float(row.get("ecart_pct", 0) or 0)
    action = format_action_label(
        row.get("action_rl") or row.get("action_proposee") or row.get("action_principale"),
        default="",
    )
    if mode == "CRITIQUE":
        return f"Situation critique (score {score:.2f}) — {action or 'intervention'}."
    if mode == "ATTENTION":
        return f"Surveillance renforcee (score {score:.2f}, ecart {ecart:+.1f} %)."
    if mode == "ECO" and action:
        return f"Optimisation active : {action} (ecart {ecart:+.1f} % vs predit)."
    if mode == "ECO":
        return "Optimisation energie selon creneau ou contexte calendaire."
    return "Fonctionnement nominal — aucune action requise."


def render_executive_report_export(kpis: dict) -> None:
    """PDF export block (filtres sidebar appliques)."""
    from datetime import datetime

    import streamlit as st

    from services.data_service import load_nb2_network_stats, load_top_anomalies
    from ui.components import section
    from ui.utils import apply_current_admin_filters
    from utils.pdf_export import generate_report_pdf

    with section("Rapport PDF"):
        top = apply_current_admin_filters(load_top_anomalies(limit=300)).head(5)
        seuil = float(load_nb2_network_stats().get("seuil_ensemble") or 0.25)
        anomaly_items = []
        if not top.empty:
            for _, row in top.iterrows():
                score = float(row.get("anomalie_score_ensemble", 0) or 0)
                anomaly_items.append({
                    "station_id": str(row.get("station_id", "")),
                    "detail": f"Score {score:.2f}",
                    "severity": (
                        "CRITIQUE" if score > seuil * 2.4
                        else "ATTENTION" if score > seuil
                        else "FAIBLE"
                    ),
                })
        if st.button("Générer le rapport PDF", type="primary", key="exec_report_pdf"):
            pdf_bytes = generate_report_pdf(kpis, anomaly_items)
            st.download_button(
                "Télécharger le rapport PDF",
                data=pdf_bytes,
                file_name=f"rapport_bts_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="exec_report_download",
            )
