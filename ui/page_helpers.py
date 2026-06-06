from __future__ import annotations

import html

import plotly.express as px

import pandas as pd

import streamlit as st

from config.settings import settings

from config.theme import MODE_COLORS, MODE_ORDER, mode_color, normalize_mode_key

from services.data_service import (
    compute_filtered_kpis,
    dataset_cache_key,
    load_filtered_main_data,
    load_station_map_data,
)

from services.nb_metrics import nb3_export_economie_kwh

from ui.formatting import display_text, resolve_row_action, row_has_no_named_action

from ui.utils import apply_current_admin_filters, filters_cache_key

DEFAULT_COLS = [
    "timestamp",
    "station_id",
    "gouvernorat",
    "technologie",
    "type_zone",
    "consommation_kwh",
    "conso_predite",
    "pred_q10",
    "pred_q90",
    "anomalie_score_ensemble",
    "nb_votes_anomalie",
    "score_qos",
    "mode_operation",
    "action_proposee",
    "action_principale",
    "economie_estimee_kwh",
    "economie_rl_kwh",
    "economie_kwh",
    "ecart_pct",
    "heure",
    "jour_semaine",
    "mois",
    "charge_cpu_pct",
    "latitude",
    "longitude",
    "meilleur_agent_rl",
]


def get_station_map_data(df: pd.DataFrame) -> pd.DataFrame:

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
    extra_cols: list[str] | None = None, *, columns: list[str] | None = None
) -> pd.DataFrame:

    if columns is not None:

        use = list(dict.fromkeys(list(columns) + settings.TEMPORAL_COLUMNS))

        cols = tuple(use)

    else:

        cols = tuple(dict.fromkeys(DEFAULT_COLS + (extra_cols or [])))

    session_key = f"{dataset_cache_key()}|{filters_cache_key()}|{cols}"

    cached = st.session_state.get("_df_session_val")

    if st.session_state.get("_df_session_key") == session_key and isinstance(
        cached, pd.DataFrame
    ):

        if all((c in cached.columns for c in cols)):

            return cached

    df = apply_current_admin_filters(load_filtered_main_data(list(cols)))

    st.session_state["_df_session_key"] = session_key

    st.session_state["_df_session_val"] = df

    return df


def render_conso_gouvernorat_par_periode(
    df: pd.DataFrame, template: str, *, show_page_filters: bool = False
) -> None:

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

            top_n = st.number_input(
                "Max. gouvernorats",
                min_value=3,
                max_value=24,
                value=10,
                key="cmp_chart_top_n",
            )

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

        by_gov = by_gov.rename(
            columns={"consommation_kwh": "conso_moy_kwh"}
        ).sort_values("conso_moy_kwh", ascending=True)

        fig = px.bar(
            by_gov,
            x="conso_moy_kwh",
            y="gouvernorat",
            orientation="h",
            template=template,
        )

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

        period_label = (
            f"Periodes : {chart_df['periode'].min()} → {chart_df['periode'].max()}"
        )

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


def _prepare_actions_work(latest: pd.DataFrame) -> pd.DataFrame:

    work = latest.copy()

    sid = work["station_id"].astype(str).str.strip()

    work = work[
        sid.notna()
        & sid.ne("")
        & sid.str.lower().ne("none")
        & sid.str.lower().ne("nan")
    ]

    if work.empty:

        return work

    work["_mode_key"] = work.get(
        "mode_operation", pd.Series("NORMAL", index=work.index)
    ).map(lambda m: normalize_mode_key(m) or "NORMAL")

    prio = {"CRITIQUE": 0, "ATTENTION": 1, "NORMAL": 2, "ECO": 3}

    work["_prio"] = work["_mode_key"].map(lambda m: prio.get(m, 9))

    return work.sort_values(["_prio", "station_id"])


def _row_economie_kwh(row: pd.Series) -> float:

    row_df = row.to_frame().T

    if row_df.empty:

        return 0.0

    eco_series = nb3_export_economie_kwh(row_df)

    eco = float(eco_series.iloc[0]) if not eco_series.empty else 0.0

    if eco > 1e-09:

        return eco

    for col in ("economie_estimee_kwh", "economie_rl_kwh", "economie_kwh"):

        if col not in row.index:

            continue

        val = pd.to_numeric(row.get(col), errors="coerce")

        if pd.notna(val) and float(val) > 1e-09:

            return float(val)

    if "conso_optimisee_kwh" in row.index and "consommation_kwh" in row.index:

        conso = pd.to_numeric(row.get("consommation_kwh"), errors="coerce")

        optim = pd.to_numeric(row.get("conso_optimisee_kwh"), errors="coerce")

        if pd.notna(conso) and pd.notna(optim) and (float(conso) > 0):

            return max(float(conso) - float(optim), 0.0)

    if (
        normalize_mode_key(row.get("mode_operation")) == "ECO"
        and "consommation_kwh" in row.index
    ):

        conso = pd.to_numeric(row.get("consommation_kwh"), errors="coerce")

        if pd.notna(conso) and float(conso) > 0:

            pct = pd.to_numeric(row.get("eco_potentiel_pct"), errors="coerce")

            pct_val = 20.0 if pd.isna(pct) or float(pct) <= 0 else float(pct)

            return float(conso) * pct_val / 100.0

    return 0.0


def _row_saving_label(row: pd.Series, eco_kwh: float) -> str:

    if eco_kwh <= 1e-09:

        return "Potentiel"

    if row_has_no_named_action(row):

        return "Potentiel"

    for col in ("economie_estimee_kwh", "economie_rl_kwh"):

        val = pd.to_numeric(row.get(col), errors="coerce") if col in row.index else None

        if pd.notna(val) and float(val) > 1e-09:

            return "Gain"

    return "Potentiel"


def _build_mode_group_html(
    mode: str,
    subset: pd.DataFrame,
    total: int,
    *,
    show_savings: bool,
    pagination_footer: str = "",
) -> str:

    mode_slug = mode.lower()

    color = MODE_COLORS.get(mode, "#64748b")

    count_label = f"{len(subset)} / {total} station(s)"

    rows_html: list[str] = []

    for _, row in subset.iterrows():

        station = html.escape(str(row.get("station_id", "")))

        action = html.escape(resolve_row_action(row, prefer_rl=show_savings))

        gov = row.get("gouvernorat")

        gov_html = (
            f'<div class="sap-gov">{html.escape(display_text(gov))}</div>'
            if gov is not None and display_text(gov) != "—"
            else ""
        )

        saving_html = ""

        if show_savings:

            eco_kwh = _row_economie_kwh(row)

            if eco_kwh > 1e-09:

                eco_dt = eco_kwh * settings.PRIX_KWH_TN

                label = _row_saving_label(row, eco_kwh)

                saving_html = f'<div class="sap-saving" style="color:{color};">{label} : {eco_dt:.2f} DT · {eco_kwh:.2f} kWh</div>'

        rows_html.append(
            f'<div class="sap-row"><div class="sap-station">{station}</div><div class="sap-action">{action}</div>{saving_html}{gov_html}</div>'
        )

    return f"""<div class="sap-group sap-group--{mode_slug}"><div class="sap-group-title">{html.escape(mode)}<span class="sap-group-count">{html.escape(count_label)}</span></div>{''.join(rows_html)}{pagination_footer}</div>"""


def render_actions_par_station(
    latest: pd.DataFrame,
    *,
    show_savings: bool = True,
    per_mode: int = 3,
    page_size: int = 10,
) -> None:

    if latest.empty or "station_id" not in latest.columns:

        st.info("Aucune station à afficher.")

        return

    work = _prepare_actions_work(latest)

    if work.empty:

        st.info("Aucune station à afficher.")

        return

    show_all = st.session_state.get("sap_show_all", False)

    btn_col, _ = st.columns([1, 3])

    with btn_col:

        btn_label = "Résumé (3 par mode)" if show_all else "Voir toutes les stations"

        if st.button(btn_label, key="sap_toggle_all", width="stretch"):

            st.session_state["sap_show_all"] = not show_all

            if not show_all:

                for mode in MODE_ORDER:

                    st.session_state[f"sap_page_{mode}"] = 1

            st.rerun()

    any_group = False

    if show_all:

        st.markdown('<div class="station-actions-panel">', unsafe_allow_html=True)

        for mode in MODE_ORDER:

            mode_df = work[work["_mode_key"] == mode]

            if mode_df.empty:

                continue

            any_group = True

            total = len(mode_df)

            total_pages = max(1, (total + page_size - 1) // page_size)

            page_key = f"sap_page_{mode}"

            if page_key not in st.session_state:

                st.session_state[page_key] = 1

            page = max(1, min(int(st.session_state[page_key]), total_pages))

            st.session_state[page_key] = page

            start = (page - 1) * page_size

            subset = mode_df.iloc[start : start + page_size]

            page_footer = f'<div class="sap-pagination"><strong>{html.escape(mode)}</strong> — page {page} / {total_pages} ({total} stations)</div>'

            st.markdown(
                _build_mode_group_html(
                    mode,
                    subset,
                    total,
                    show_savings=show_savings,
                    pagination_footer=page_footer,
                ),
                unsafe_allow_html=True,
            )

            st.markdown(
                '<div class="sap-pagination-buttons-gap"></div>', unsafe_allow_html=True
            )

            st.markdown('<div class="sap-pagination-nav-wrap">', unsafe_allow_html=True)

            _, nav_mid, _ = st.columns([1, 2, 1])

            with nav_mid:

                btn_prev, btn_next = st.columns(2)

                with btn_prev:

                    if page > 1 and st.button(
                        "← Préc.", key=f"sap_prev_{mode}", width="stretch"
                    ):

                        st.session_state[page_key] = page - 1

                        st.rerun()

                with btn_next:

                    if page < total_pages and st.button(
                        "Suiv. →", key=f"sap_next_{mode}", width="stretch"
                    ):

                        st.session_state[page_key] = page + 1

                        st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    else:

        groups_html: list[str] = ['<div class="station-actions-panel">']

        for mode in MODE_ORDER:

            mode_df = work[work["_mode_key"] == mode]

            if mode_df.empty:

                continue

            any_group = True

            subset = mode_df.head(per_mode)

            groups_html.append(
                _build_mode_group_html(
                    mode, subset, len(mode_df), show_savings=show_savings
                )
            )

        groups_html.append("</div>")

        st.markdown("".join(groups_html), unsafe_allow_html=True)

    if not any_group:

        st.info("Aucune station à afficher.")


def render_nb3_decision_cards(
    latest: pd.DataFrame, limit: int = 12, *, show_savings: bool = True
) -> None:

    prio = {"CRITIQUE": 0, "ATTENTION": 1, "NORMAL": 2, "ECO": 3}

    work = latest.copy()

    if "station_id" in work.columns:

        sid = work["station_id"].astype(str).str.strip()

        work = work[
            sid.notna()
            & sid.ne("")
            & sid.str.lower().ne("none")
            & sid.str.lower().ne("nan")
        ]

    work["_prio"] = work["mode_operation"].astype(str).map(lambda m: prio.get(m, 9))

    for _, row in work.sort_values("_prio").head(limit).iterrows():

        mode = display_text(row.get("mode_operation"), "NORMAL")

        color = mode_color(mode)

        action = resolve_row_action(row, prefer_rl=show_savings)

        saving_html = ""

        if show_savings:

            eco_series = nb3_export_economie_kwh(pd.DataFrame([row]))

            eco_kwh = float(eco_series.iloc[0]) if not eco_series.empty else 0.0

            if eco_kwh > 0:

                eco_dt = eco_kwh * settings.PRIX_KWH_TN

                if row_has_no_named_action(row):

                    saving_html = f'<div class="dc-saving">Potentiel mode : {eco_dt:.2f} DT · {eco_kwh:.2f} kWh</div>'

                else:

                    saving_html = f'<div class="dc-saving">{eco_dt:.2f} DT · {eco_kwh:.2f} kWh</div>'

        sid = str(row.get("station_id", ""))

        st.markdown(
            f'\n<div class="decision-card" style="border-left-color:{color};">\n  <div class="dc-mode" style="color:{color};">{html.escape(sid)} · {html.escape(mode)}</div>\n  <div class="dc-action">{html.escape(action)}</div>\n  {saving_html}\n</div>',
            unsafe_allow_html=True,
        )


def render_nb3_rl_agents(nb3: dict, template: str, *, show_chart: bool = False) -> None:

    import html as html_mod

    from services.data_service import load_nb3_network_kpi

    rl_data = nb3.get("rl_resultats_tous_agents") or {}

    if not rl_data:

        kpi = load_nb3_network_kpi() or {}

        comp = kpi.get("rl_agents_comparaison") or nb3.get("rl_agents_comparaison") or {}

        if isinstance(comp, dict) and comp:

            rl_data = {
                str(agent): {
                    "economie_pct": stats.get("economie_pct", stats.get("eco_pct")),
                    "n_violations": stats.get("n_violations", stats.get("n_viols")),
                }
                for agent, stats in comp.items()
                if isinstance(stats, dict)
            }

    if not rl_data:

        st.info(
            "Comparaison agents indisponible — export `rapport_optimisation.json` (NB3) requis."
        )

        return

    df_rl = pd.DataFrame.from_dict(rl_data, orient="index").reset_index(names="Agent")

    if "economie_pct" in df_rl.columns:

        df_rl["economie_pct"] = pd.to_numeric(df_rl["economie_pct"], errors="coerce")

        df_rl = df_rl.sort_values("economie_pct", ascending=False)

    best_name = str(nb3.get("meilleur_agent") or "").strip()

    if not best_name and (not df_rl.empty) and ("economie_pct" in df_rl.columns):

        best_name = str(df_rl.iloc[0]["Agent"])

    if best_name:

        best_row = df_rl[df_rl["Agent"].astype(str) == best_name]

        best_pct = (
            float(best_row["economie_pct"].iloc[0])
            if not best_row.empty and "economie_pct" in best_row
            else None
        )

        pct_txt = (
            f" · {best_pct:.1f} % d'économie"
            if best_pct is not None and pd.notna(best_pct)
            else ""
        )

        st.markdown(
            f'<div class="rl-best-banner">Meilleur agent RL retenu : <strong>{html_mod.escape(best_name)}</strong>{html_mod.escape(pct_txt)}</div>',
            unsafe_allow_html=True,
        )

    rename = {
        "economie_pct": "Économie %",
        "economie_kwh": "Économie kWh",
        "n_violations": "Violations QoS",
        "pct_violations": "Violations %",
        "class_name": "Classe",
        "reference": "Référence",
        "is_best": "Retenu",
    }

    show = df_rl.rename(columns={k: v for k, v in rename.items() if k in df_rl.columns})

    if "Retenu" in show.columns:

        show["Retenu"] = show["Retenu"].map({True: "Oui", False: ""})

    if "Économie %" in show.columns:

        show["Économie %"] = pd.to_numeric(show["Économie %"], errors="coerce").round(2)

    if "Économie kWh" in show.columns:

        show["Économie kWh"] = pd.to_numeric(
            show["Économie kWh"], errors="coerce"
        ).round(0)

    st.dataframe(show, width="stretch", hide_index=True)

    if show_chart and "Économie %" in show.columns and (len(show) > 1):

        fig = px.bar(
            show,
            x="Agent",
            y="Économie %",
            color="Économie %",
            color_continuous_scale=["#93c5fd", "#1e3a8a", "#059669"],
        )

        fig.update_layout(
            template=template,
            height=280,
            margin=dict(l=0, r=0, t=8, b=0),
            coloraxis_showscale=False,
        )

        st.plotly_chart(fig, width="stretch")


def mode_explanation(row: pd.Series) -> str:

    from ui.formatting import format_action_label

    mode = str(row.get("mode_operation", "NORMAL"))

    score = float(row.get("anomalie_score_ensemble", 0) or 0)

    ecart = float(row.get("ecart_pct", 0) or 0)

    action = format_action_label(
        row.get("action_rl")
        or row.get("action_proposee")
        or row.get("action_principale"),
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

    if mode == "NORMAL" and not row_has_no_named_action(row):

        action_label = resolve_row_action(row, prefer_rl=False, default="")

        if action_label and action_label not in ("Aucune action", "Maintien", "—"):

            return f"Fonctionnement nominal — optimisation possible : {action_label} (ecart {ecart:+.1f} %)."

    return "Fonctionnement nominal."


def render_executive_report_export(kpis: dict, df: pd.DataFrame | None = None) -> None:

    from datetime import datetime

    import streamlit as st

    from services.data_service import load_nb2_network_stats, top_criticite_stations

    from ui.components import section

    from utils.pdf_export import generate_report_pdf

    from ui.data_validation import (
        MSG_ANOM_COL,
        column_has_values,
        format_nb2_seuil_alert,
        nb2_seuil_or_warn,
    )

    with section("Rapport PDF"):

        source = df if isinstance(df, pd.DataFrame) and not df.empty else load_dashboard_df()

        top = top_criticite_stations(source, limit=5)

        nb2_stats = load_nb2_network_stats()

        seuil = nb2_seuil_or_warn(nb2_stats)

        anomaly_items = []

        pdf_ready = not top.empty and "station_id" in top.columns

        if seuil is not None and not column_has_values(source, "anomalie_score_ensemble"):

            st.warning(MSG_ANOM_COL)

        if pdf_ready:

            for _, nb_row in top.iterrows():

                station_id = str(nb_row.get("station_id", ""))

                categorie = str(nb_row.get("categorie", "")).upper()

                score_moy = nb_row.get("score_moy_ensemble")

                pct_anom = nb_row.get("pct_anomalie_ensemble")

                crit = nb_row.get("score_criticite")

                detail_parts = []

                if pd.notna(crit):

                    detail_parts.append(f"criticite {float(crit):.3f}")

                if pd.notna(score_moy):

                    detail_parts.append(f"score moy {float(score_moy):.3f}")

                if pd.notna(pct_anom):

                    detail_parts.append(f"pct anom {float(pct_anom):.1%}")

                detail = " — ".join(detail_parts) if detail_parts else categorie or "NB"

                if categorie == "CRITIQUE":

                    severity = "CRITIQUE"

                elif categorie == "ATTENTION":

                    severity = "ATTENTION"

                else:

                    severity = "FAIBLE"

                anomaly_items.append(
                    {
                        "station_id": station_id,
                        "detail": detail,
                        "severity": severity,
                    }
                )

        elif seuil is None:

            st.warning(format_nb2_seuil_alert())

        if st.button(
            "Générer le rapport PDF",
            type="primary",
            key="exec_report_pdf",
            disabled=not pdf_ready,
        ):

            pdf_bytes = generate_report_pdf(kpis, anomaly_items)

            st.download_button(
                "Télécharger le rapport PDF",
                data=pdf_bytes,
                file_name=f"rapport_bts_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="exec_report_download",
            )
