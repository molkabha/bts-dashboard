"""Page 3 - Detection d'Anomalies (NB2)."""

from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import PLOTLY_LIGHT, PLOTLY_DARK
from security.middleware import security_middleware
from services.data_service import artifact_table, load_filtered_main_data
from ui.components import header, kpi_card, render_artifact_gallery, section
from ui.utils import apply_current_admin_filters, filter_artifact_dataframe, session_outputs


def _severity_label(score: float) -> str:
    if score > 0.6:
        return "CRITIQUE"
    if score > 0.3:
        return "ATTENTION"
    return "FAIBLE"


def page_anomalies():
    security_middleware.enforce()
    header("Alertes", "Anomalies actives, criticite et traitement")

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT
    outputs = session_outputs()

    cols = ["timestamp", "station_id", "consommation_kwh", "conso_predite",
            "anomalie_score_ensemble", "nb_votes_anomalie", "score_qos",
            "mode_operation", "heure", "mois", "technologie", "gouvernorat"]
    df_raw = load_filtered_main_data(cols)
    df = apply_current_admin_filters(df_raw)

    if df.empty:
        st.warning("Aucune donnee disponible pour l'analyse des anomalies.")
        return

    # Init treated anomalies in session
    if "treated_anomalies" not in st.session_state:
        st.session_state["treated_anomalies"] = set()

    anom_col = "anomalie_score_ensemble"
    has_anom = anom_col in df.columns
    anom_df = df[pd.to_numeric(df[anom_col], errors="coerce").fillna(0) > 0.25] if has_anom else pd.DataFrame()

    # Section 1 - Summary
    with section("Resume"):
        total_anom = len(anom_df)
        nb_critique = len(anom_df[pd.to_numeric(anom_df[anom_col], errors="coerce") > 0.6]
                          ) if has_anom and not anom_df.empty else 0
        nb_qos = len(anom_df[pd.to_numeric(anom_df.get("score_qos", pd.Series(dtype=float)),
                     errors="coerce").fillna(1) < 0.7]) if not anom_df.empty else 0
        nb_treated = len(st.session_state["treated_anomalies"])

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi_card("Total anomalies", str(total_anom), "Detectees sur la periode", "orange")
        with c2:
            kpi_card("Energetiques pures", str(total_anom - nb_qos), "Surconsommation", "red")
        with c3:
            kpi_card("Liees QoS", str(nb_qos), "Degradation qualite", "blue")
        with c4:
            kpi_card("Traitees", str(nb_treated), f"sur {total_anom}", "green")

        if has_anom and "timestamp" in df.columns:
            ts = df.copy()
            ts["date"] = pd.to_datetime(ts["timestamp"], errors="coerce").dt.date
            ts["is_anom"] = pd.to_numeric(ts[anom_col], errors="coerce").fillna(0) > 0.25
            daily = ts.groupby("date")["is_anom"].sum().reset_index(name="nb_anomalies")
            fig = px.line(daily, x="date", y="nb_anomalies", title="Evolution des anomalies par jour")
            fig.update_layout(template=template, margin=dict(l=0, r=0, t=30, b=0), height=250)
            st.plotly_chart(fig, width="stretch")

    # Section 2 - Anomaly feed
    with section("Fil d'Actualite des Anomalies"):
        if not anom_df.empty:
            # Filters
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                sev_filter = st.multiselect("Criticite", ["CRITIQUE", "ATTENTION", "FAIBLE"],
                                            default=["CRITIQUE", "ATTENTION", "FAIBLE"], key="anom_sev_filter")
            with fc2:
                status_filter = st.selectbox("Statut", ["Tous", "Non traite", "Traite"], key="anom_status_filter")
            with fc3:
                sort_order = st.selectbox("Tri", ["Criticite decroissante", "Date recente"], key="anom_sort")

            display_df = anom_df.copy()
            display_df["_score"] = pd.to_numeric(display_df[anom_col], errors="coerce").fillna(0)
            display_df["_severity"] = display_df["_score"].apply(_severity_label)
            display_df = display_df[display_df["_severity"].isin(sev_filter)]

            if sort_order == "Criticite decroissante":
                display_df = display_df.sort_values("_score", ascending=False)
            else:
                display_df = display_df.sort_values("timestamp", ascending=False)

            treated = st.session_state["treated_anomalies"]
            for idx, row in display_df.head(20).iterrows():
                score = float(row["_score"])
                severity = row["_severity"]
                station = str(row.get("station_id", ""))
                ts_str = str(row.get("timestamp", ""))[:16]
                key = f"{station}_{ts_str}"
                is_treated = key in treated

                if status_filter == "Non traite" and is_treated:
                    continue
                if status_filter == "Traite" and not is_treated:
                    continue

                css_sev = severity.lower()
                treated_cls = " traite" if is_treated else ""
                conso = row.get("consommation_kwh", "")
                conso_str = f"{float(conso):.1f} kWh" if conso != "" and not pd.isna(conso) else ""
                votes = int(row.get("nb_votes_anomalie", 0) or 0)
                safe_station = html.escape(station)
                safe_ts = html.escape(ts_str)
                safe_conso = html.escape(conso_str)

                st.markdown(f"""
<div class="anomaly-card {css_sev}{treated_cls}">
  <div class="ac-header">
    <span class="ac-badge {css_sev}">{severity}</span>
    <span class="ac-station">{safe_station}</span>
  </div>
  <div class="ac-detail">{safe_ts} | Score : {score:.2f} | {safe_conso} | {votes} detecteurs</div>
  <div class="ac-meta">{"TRAITE" if is_treated else ""}</div>
</div>""", unsafe_allow_html=True)

                if not is_treated:
                    if st.button(f"Marquer comme traite", key=f"treat_{key}"):
                        st.session_state["treated_anomalies"].add(key)
                        st.rerun()

            # Resolution rate
            resolution = len(treated) / total_anom * 100 if total_anom > 0 else 0
            st.caption(f"Taux de resolution : {len(treated)}/{total_anom} anomalies traitees ({resolution:.0f}%)")
        else:
            st.info("Aucune anomalie significative detectee pour les filtres actuels.")

    # Section 3 - Heatmap
    with section("Heatmap Station x Heure"):
        if has_anom and "heure" in df.columns and "station_id" in df.columns:
            heat = df.copy()
            heat["_score"] = pd.to_numeric(heat[anom_col], errors="coerce").fillna(0)
            pivot = heat.pivot_table(values="_score", index="station_id", columns="heure", aggfunc="mean")
            if not pivot.empty:
                top_stations = pivot.max(axis=1).nlargest(20).index
                pivot = pivot.loc[pivot.index.isin(top_stations)]
                fig = px.imshow(pivot, aspect="auto", color_continuous_scale="YlOrRd",
                                title="Score anomalie moyen par station et heure")
                fig.update_layout(template=template, margin=dict(l=0, r=0, t=30, b=0), height=400)
                st.plotly_chart(fig, width="stretch")

    if st.session_state.get("role") == "admin":
        with st.expander("Diagnostic technique des detecteurs", expanded=False):
            nb2 = outputs.get("nb2", {})
            if nb2:
                st.dataframe(pd.DataFrame.from_dict(nb2, orient="index").reset_index(names="Detecteur"),
                             width="stretch", hide_index=True)
            if "nb_votes_anomalie" in df.columns and not anom_df.empty:
                st.caption("Plus les detecteurs sont d'accord, plus l'anomalie est certaine.")
                vote_dist = anom_df["nb_votes_anomalie"].value_counts().sort_index().reset_index()
                vote_dist.columns = ["Nb detecteurs", "Nb anomalies"]
                fig_v = px.bar(vote_dist, x="Nb detecteurs", y="Nb anomalies",
                               title="Distribution du consensus (votes)")
                fig_v.update_layout(template=template, margin=dict(l=0, r=0, t=30, b=0), height=250)
                st.plotly_chart(fig_v, width="stretch")

        with st.expander("Artefacts notebook NB2", expanded=False):
            render_artifact_gallery(
                [
                    ("precision_recall_modeles.png", "Precision / recall des detecteurs"),
                    ("tsne_anomalies.png", "Projection t-SNE des anomalies"),
                ],
                title="Artefacts visuels NB2",
                links=[
                    ("modeles_anomalie.joblib", "Modeles anomalie"),
                    ("autoencoder.keras", "Autoencoder"),
                ],
            )
            qualitative = filter_artifact_dataframe(artifact_table("performance_qualitative_modeles.csv"))
            if not qualitative.empty:
                st.dataframe(qualitative, width="stretch", hide_index=True)
