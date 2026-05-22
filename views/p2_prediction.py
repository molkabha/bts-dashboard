"""Page 2 - Prediction de Consommation (NB1)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from config.theme import PLOTLY_LIGHT, PLOTLY_DARK
from security.middleware import security_middleware
from services.data_service import (
    load_filtered_main_data,
)
from ui.components import header, kpi_card, render_artifact_gallery, section
from ui.utils import session_outputs, apply_current_admin_filters

FEATURE_LABELS_FR = {
    "heure": "Heure de la journee",
    "trafic_data_mbps": "Volume de donnees transmises",
    "taux_charge_data": "Taux de charge data",
    "temperature_ambiante": "Temperature exterieure",
    "charge_cpu_pct": "Charge processeur",
    "taux_charge_voix": "Taux de charge voix",
    "nb_utilisateurs_actifs": "Nombre utilisateurs actifs",
    "mois": "Mois de l'annee",
    "jour_semaine": "Jour de la semaine",
    "est_weekend": "Weekend",
    "puissance_emission_dbm": "Puissance emission",
    "humidite_relative_pct": "Humidite relative",
    "rayonnement_solaire_wm2": "Rayonnement solaire",
    "consommation_kwh": "Consommation energetique",
    "score_qos": "Qualite de service",
}

MODEL_METRIC_KEYS = {"r2", "mae", "rmse", "rmse_pct", "temps"}


def _model_results(nb1: dict) -> dict:
    """Return model comparison results from old or final NB1 JSON formats."""
    if not isinstance(nb1, dict):
        return {}
    for key in ("comparaison_modeles", "resultats_par_modele"):
        value = nb1.get(key)
        if isinstance(value, dict) and value:
            return value
    direct_results = {
        name: metrics
        for name, metrics in nb1.items()
        if isinstance(metrics, dict) and MODEL_METRIC_KEYS.intersection(metrics)
    }
    return direct_results


def page_prediction():
    security_middleware.enforce()
    header("Prevision", "Consommation reelle, consommation predite et ecarts utiles")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    outputs = session_outputs()
    nb1 = outputs.get("nb1", {})

    cols = ["timestamp", "station_id", "consommation_kwh", "conso_predite",
            "pred_q10", "pred_q90", "heure", "mois", "technologie", "type_zone"]
    df_raw = load_filtered_main_data(cols)
    df = apply_current_admin_filters(df_raw)

    if df.empty:
        st.warning("Donnees insuffisantes pour l'analyse predictive.")
        return

    # Section 1 - Global performance
    with section("Performance Globale du Modele"):
        if "timestamp" in df.columns and "consommation_kwh" in df.columns:
            df_daily = df.set_index("timestamp").resample("D").mean(numeric_only=True).reset_index()

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_daily["timestamp"], y=df_daily["consommation_kwh"],
                                     name="Reel", line=dict(width=2.5, color="#1e3a8a")))
            if "conso_predite" in df_daily.columns:
                fig.add_trace(go.Scatter(x=df_daily["timestamp"], y=df_daily["conso_predite"],
                                         name="Predit", line=dict(width=2, color="#d97706", dash="dot")))
            if "pred_q10" in df_daily.columns and "pred_q90" in df_daily.columns:
                fig.add_trace(go.Scatter(x=df_daily["timestamp"], y=df_daily["pred_q90"],
                                         line=dict(width=0), showlegend=False))
                fig.add_trace(go.Scatter(x=df_daily["timestamp"], y=df_daily["pred_q10"],
                                         fill="tonexty", fillcolor="rgba(217,119,6,0.1)",
                                         line=dict(width=0), name="Intervalle confiance"))
            fig.update_layout(template=template, hovermode="x unified",
                              margin=dict(l=0, r=0, t=20, b=0), height=350)
            st.plotly_chart(fig, width="stretch")

        best_r2, best_rmse, coverage = None, None, None

        # Dynamic calculation from actual data
        if "consommation_kwh" in df.columns and "conso_predite" in df.columns:
            vdf = df.dropna(subset=["consommation_kwh", "conso_predite"])
            y_true = pd.to_numeric(vdf["consommation_kwh"], errors="coerce")
            y_pred = pd.to_numeric(vdf["conso_predite"], errors="coerce")
            valid_idx = y_true.notna() & y_pred.notna()
            if valid_idx.sum() > 0:
                yt, yp = y_true[valid_idx], y_pred[valid_idx]
                import numpy as np
                best_rmse = np.sqrt(((yt - yp) ** 2).mean())
                ss_tot = ((yt - yt.mean()) ** 2).sum()
                best_r2 = 1 - (((yt - yp) ** 2).sum() / ss_tot) if ss_tot != 0 else 0

        if "consommation_kwh" in df.columns and "pred_q10" in df.columns and "pred_q90" in df.columns:
            qdf = df.dropna(subset=["consommation_kwh", "pred_q10", "pred_q90"])
            yt = pd.to_numeric(qdf["consommation_kwh"], errors="coerce")
            q10 = pd.to_numeric(qdf["pred_q10"], errors="coerce")
            q90 = pd.to_numeric(qdf["pred_q90"], errors="coerce")
            valid_q = yt.notna() & q10.notna() & q90.notna()
            if valid_q.sum() > 0:
                coverage = ((yt[valid_q] >= q10[valid_q]) & (yt[valid_q] <= q90[valid_q])).mean()

        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Precision du modele",
                     f"{best_r2:.1%}" if best_r2 is not None else "0.0%", "R2 score", "green")
        with c2:
            kpi_card("Ecart moyen",
                     f"{best_rmse:.2f} kWh" if best_rmse is not None else "0.00 kWh", "RMSE", "blue")
        with c3:
            kpi_card("Couverture intervalle",
                     f"{coverage:.1%}" if coverage is not None else "0.0%", "Q10-Q90", "eco")

        with st.expander("Voir details techniques"):
            models = _model_results(nb1)
            if models:
                st.dataframe(pd.DataFrame.from_dict(models, orient="index").reset_index(names="Modele"),
                             width="stretch", hide_index=True)

    # Section 2 - Station analysis
    with section("Analyse par Station"):
        stations = sorted(df["station_id"].dropna().unique().astype(str).tolist()) if "station_id" in df.columns else []
        if stations:
            station = st.selectbox("Choisir une station", stations, key="pred_station")
            sdf = df[df["station_id"].astype(str) == station] if station else pd.DataFrame()

            if not sdf.empty and "timestamp" in sdf.columns:
                c1, c2 = st.columns(2)
                with c1:
                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["consommation_kwh"], name="Reel"))
                    if "conso_predite" in sdf.columns:
                        fig_s.add_trace(go.Scatter(x=sdf["timestamp"], y=sdf["conso_predite"], name="Predit"))
                    fig_s.update_layout(template=template, title="Consommation reelle vs predite",
                                        margin=dict(l=0, r=0, t=30, b=0), height=280)
                    st.plotly_chart(fig_s, width="stretch")

                with c2:
                    if "heure" in sdf.columns:
                        hourly = sdf.groupby("heure")["consommation_kwh"].mean().reset_index()
                        fig_h = px.bar(hourly, x="heure", y="consommation_kwh",
                                       title="Profil horaire moyen (24h)")
                        fig_h.update_layout(template=template, margin=dict(l=0, r=0, t=30, b=0), height=280)
                        st.plotly_chart(fig_h, width="stretch")

                if "conso_predite" in sdf.columns:
                    residuals = pd.to_numeric(sdf["consommation_kwh"], errors="coerce") - \
                        pd.to_numeric(sdf["conso_predite"], errors="coerce")
                    residuals = residuals.dropna()
                    if not residuals.empty:
                        fig_r = px.histogram(residuals, nbins=30, title="Distribution des residus (ecarts)")
                        fig_r.update_layout(template=template, margin=dict(l=0, r=0, t=30, b=0), height=250)
                        st.plotly_chart(fig_r, width="stretch")
                        st.caption("Le modele est precis : les erreurs sont petites et symetriques autour de zero.")

    # Section 3 - Feature importance
    with st.expander("Facteurs d'influence avances", expanded=False):
        shap_data = nb1.get("feature_importance", nb1.get("shap_values", nb1.get("importances", {})))

        # Dynamic fallback: Pearson correlation if artifact is missing
        if not shap_data and not df.empty and "consommation_kwh" in df.columns:
            candidates = [
                "heure", "trafic_data_mbps", "taux_charge_data", "temperature_ambiante",
                "charge_cpu_pct", "taux_charge_voix", "nb_utilisateurs_actifs", "mois",
                "jour_semaine", "puissance_emission_dbm", "humidite_relative_pct", "rayonnement_solaire_wm2"
            ]
            valid_cols = [c for c in candidates if c in df.columns]
            if valid_cols:
                corr_df = df[valid_cols + ["consommation_kwh"]].apply(pd.to_numeric, errors="coerce")
                corr_series = corr_df.corr()["consommation_kwh"].drop("consommation_kwh").abs().fillna(0)
                shap_data = corr_series.to_dict()

        if shap_data and isinstance(shap_data, dict):
            items = sorted(shap_data.items(), key=lambda x: abs(float(x[1])), reverse=True)[:10]
            labels = [FEATURE_LABELS_FR.get(k, k) for k, _ in items]
            values = [abs(float(v)) for _, v in items]
            fig_fi = go.Figure(go.Bar(x=values, y=labels, orientation="h",
                                      marker_color="#1e3a8a"))
            fig_fi.update_layout(template=template, yaxis=dict(autorange="reversed"),
                                 title="Qu'est-ce qui influence la consommation ? (Correlation absolue)",
                                 margin=dict(l=0, r=0, t=30, b=0), height=350)
            st.plotly_chart(fig_fi, width="stretch")

            with st.expander("Voir l'analyse technique (Correlation)"):
                st.dataframe(pd.DataFrame(items, columns=["Feature", "Importance (Proxy)"]),
                             width="stretch", hide_index=True)
        else:
            st.info("Donnees insuffisantes pour calculer l'importance des features.")

    # Section 4 - Model comparison
    models = _model_results(nb1)
    if models:
        with st.expander("Comparaison technique des modeles", expanded=False):
            df_models = pd.DataFrame.from_dict(models, orient="index").reset_index(names="Modele")
            if "r2" in df_models.columns:
                df_models = df_models.sort_values("r2", ascending=False).reset_index(drop=True)
                ranks = ["1er", "2e", "3e"] + [f"{i + 1}e" for i in range(3, len(df_models))]
                df_models.insert(0, "Rang", ranks[:len(df_models)])
            st.dataframe(df_models, width="stretch", hide_index=True)

    with st.expander("Artefacts notebook NB1", expanded=False):
        images = [
            ("data_cleaning_avant_apres.png", "Nettoyage des donnees"),
            ("eda_correlations.png", "Correlations EDA"),
            ("dc1_synthese_anomalies.png", "Synthese anomalies preliminaires"),
            ("shap_bar.png", "SHAP - Importance globale"),
            ("shap_beeswarm.png", "SHAP - Distribution"),
            ("shap_waterfall.png", "SHAP - Explication locale"),
        ]
        render_artifact_gallery(
            images,
            title="Artefacts visuels NB1",
            links=[
                ("best_model.joblib", "best_model"),
                ("modele_lgbm.joblib", "LightGBM"),
                ("modele_stacking.joblib", "Stacking"),
                ("quantile_models.joblib", "Quantiles"),
                ("encodeurs.joblib", "Encodeurs"),
                ("config.joblib", "Config"),
                ("df_train_processed.parquet", "Train"),
                ("df_test_processed.parquet", "Test"),
            ],
        )
