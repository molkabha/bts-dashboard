"""Page NB1 — Prediction."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from services.data_service import load_nb1_models_comparison, load_nb1_production_metrics
from ui.components import header, kpi_card, section
from ui.display import PAGE_PREDICTION
from ui.formatting import display_text
from ui.page_helpers import load_dashboard_df
from ui.utils import active_filter_label, is_admin, merged_active_filters, session_outputs

FEATURE_LABELS_FR = {
    "heure": "Heure",
    "trafic_data_mbps": "Trafic data",
    "temperature_ambiante": "Temperature",
    "charge_cpu_pct": "CPU",
    "taux_charge_voix": "Voix",
    "mois": "Mois",
    "jour_semaine": "Jour semaine",
}


def _default_station(stations: list[str]) -> str | None:
    if not stations:
        return None
    gf = merged_active_filters()
    gf_stations = [str(s) for s in (gf.get("stations") or []) if str(s) in stations]
    if len(gf_stations) == 1:
        return gf_stations[0]
    current = st.session_state.get("pred_station")
    if current in stations:
        return str(current)
    return stations[0]


def _series_for_chart(df: pd.DataFrame, station: str, horizon: str) -> pd.DataFrame:
    """Build chart series from globally filtered df, scoped to station and horizon."""
    if "timestamp" not in df.columns or "station_id" not in df.columns:
        return pd.DataFrame()
    sdf = df[df["station_id"].astype(str) == str(station)].copy()
    if sdf.empty:
        return sdf
    sdf["timestamp"] = pd.to_datetime(sdf["timestamp"], errors="coerce")
    sdf = sdf.dropna(subset=["timestamp"]).sort_values("timestamp")
    if sdf.empty or horizon == "Période filtrée":
        return sdf
    hours = {"6h": 6, "12h": 12, "24h": 24}.get(horizon)
    if hours is None:
        return sdf
    end = sdf["timestamp"].max()
    return sdf[sdf["timestamp"] >= (end - pd.Timedelta(hours=hours))]


def _render_reel_vs_predit(sdf: pd.DataFrame, template: str):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=sdf["timestamp"],
            y=sdf["consommation_kwh"],
            name="Réel",
            line=dict(color="#1e3a8a"),
        )
    )
    if is_admin():
        if "conso_predite" in sdf.columns:
            fig.add_trace(
                go.Scatter(
                    x=sdf["timestamp"],
                    y=sdf["conso_predite"],
                    name="Prédit",
                    line=dict(dash="dot", color="#c8102e"),
                )
            )
        if "pred_q90" in sdf.columns and "pred_q10" in sdf.columns:
            fig.add_trace(
                go.Scatter(
                    x=sdf["timestamp"],
                    y=pd.to_numeric(sdf["pred_q90"], errors="coerce"),
                    name="Q90",
                    line=dict(width=0),
                    showlegend=False,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=sdf["timestamp"],
                    y=pd.to_numeric(sdf["pred_q10"], errors="coerce"),
                    name="Bande Q10–Q90",
                    fill="tonexty",
                    fillcolor="rgba(30,58,138,0.15)",
                    line=dict(width=0),
                )
            )
    fig.update_layout(template=template, height=320, margin=dict(l=0, r=0, t=8, b=0))
    st.plotly_chart(fig, width="stretch")


def _render_models_comparison(models_df: pd.DataFrame, template: str, prod_name: str) -> None:
    with section("Comparaison des modèles"):
        if models_df.empty:
            st.info("Artefact resultats_modeles.json manquant.")
            return

        tab_table, tab_r2, tab_errors = st.tabs(["Tableau", "Graphique R²", "Erreurs"])

        display = models_df.copy()
        for col in ("R2", "RMSE", "MAE"):
            if col in display.columns:
                display[col] = pd.to_numeric(display[col], errors="coerce")

        with tab_table:
            if prod_name:
                st.caption(f"Modèle retenu en production : {prod_name}")
            show = display.copy()
            if "Production" in show.columns:
                show["Retenu"] = show["Production"].map({True: "Oui", False: ""})
                show = show.drop(columns=["Production"])
            st.dataframe(
                show,
                width="stretch",
                hide_index=True,
                column_config={
                    "R2": st.column_config.NumberColumn("R²", format="%.4f"),
                    "RMSE": st.column_config.NumberColumn("RMSE (kWh)", format="%.3f"),
                    "MAE": st.column_config.NumberColumn("MAE (kWh)", format="%.3f"),
                },
            )

        with tab_r2:
            chart_df = display.sort_values("R2", ascending=True)
            colors = ["#059669" if str(m) == prod_name else "#1e3a8a" for m in chart_df["Modèle"]]
            fig = go.Figure(
                go.Bar(
                    x=chart_df["R2"],
                    y=chart_df["Modèle"],
                    orientation="h",
                    marker_color=colors,
                    text=[f"{v:.3f}" for v in chart_df["R2"]],
                    textposition="outside",
                )
            )
            fig.update_layout(
                template=template,
                height=max(220, 44 * len(chart_df)),
                margin=dict(l=0, r=40, t=8, b=0),
                xaxis_title="R² (jeu test)",
                showlegend=False,
            )
            st.plotly_chart(fig, width="stretch")

        with tab_errors:
            err_cols = [c for c in ("RMSE", "MAE") if c in display.columns and display[c].notna().any()]
            if not err_cols:
                st.info("RMSE / MAE non disponibles dans l'artefact NB1.")
            else:
                melt = display.melt(
                    id_vars=["Modèle"],
                    value_vars=err_cols,
                    var_name="Métrique",
                    value_name="Valeur",
                )
                fig = px.bar(
                    melt,
                    x="Valeur",
                    y="Modèle",
                    color="Metrique",
                    orientation="h",
                    barmode="group",
                    color_discrete_map={"RMSE": "#1e3a8a", "MAE": "#64748b"},
                )
                fig.update_layout(
                    template=template,
                    height=max(220, 44 * len(display)),
                    margin=dict(l=0, r=0, t=8, b=0),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig, width="stretch")


def page_prediction():
    security_middleware.enforce()

    subtitle = "Réel vs prédit, bande Q10/Q90 et métriques R²"
    if not is_admin():
        subtitle = "Consommation réelle de vos stations (sans modèle ML)"
    header(PAGE_PREDICTION, subtitle)
    st.caption(active_filter_label())

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    if is_admin():
        prod = load_nb1_production_metrics()
        prod_name = display_text(prod.get("model"))
        r2 = prod.get("r2")
        rmse = prod.get("rmse")
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Modèle", prod_name, "", "green")
        with c2:
            kpi_card("R²", f"{float(r2):.3f}" if r2 is not None else "—", "Jeu test", "blue")
        with c3:
            kpi_card("RMSE", f"{float(rmse):.3f} kWh" if rmse is not None else "—", "", "gray")

    df = load_dashboard_df()
    if df.empty:
        st.warning("Aucune donnée pour les filtres actifs.")
        return

    stations = sorted(df["station_id"].dropna().unique().astype(str).tolist()) if "station_id" in df.columns else []
    if not stations:
        st.warning("Aucune station dans la sélection des filtres globaux.")
        return

    default_station = _default_station(stations)
    horizon_options = ["Période filtrée", "6h", "12h", "24h"]
    c1, c2 = st.columns([2, 1])
    with c1:
        station = st.selectbox(
            "Station",
            stations,
            index=stations.index(default_station) if default_station in stations else 0,
            key="pred_station",
        )
    with c2:
        horizon = st.selectbox(
            "Fenetre",
            horizon_options,
            index=0,
            key="pred_horizon",
            help="Période filtrée = toutes les mesures dans la plage Début/Fin de la barre latérale.",
        )

    with section("Courbe consommation"):
        sdf = _series_for_chart(df, station, horizon)
        if sdf.empty:
            st.info("Aucune mesure pour cette station sur la période filtrée.")
        else:
            n_pts = len(sdf)
            t0 = sdf["timestamp"].min()
            t1 = sdf["timestamp"].max()
            st.caption(f"{n_pts} points · {t0:%Y-%m-%d %H:%M} → {t1:%Y-%m-%d %H:%M}")
            _render_reel_vs_predit(sdf, template)

    if is_admin():
        models_df = load_nb1_models_comparison()
        _render_models_comparison(models_df, template, prod_name)

        nb1 = session_outputs().get("nb1", {})
        shap_data = nb1.get("feature_importance", nb1.get("shap_values", {}))
        if shap_data:
            with section("Variables cles (SHAP)"):
                items = sorted(shap_data.items(), key=lambda x: abs(float(x[1])), reverse=True)[:5]
                labels = [FEATURE_LABELS_FR.get(k, k) for k, _ in items]
                values = [abs(float(v)) for _, v in items]
                fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker_color="#1e3a8a"))
                fig.update_layout(
                    template=template,
                    yaxis=dict(autorange="reversed"),
                    height=200,
                    margin=dict(l=0, r=0, t=0, b=0),
                )
                st.plotly_chart(fig, width="stretch")
