"""Page 0 - Accueil : orientation rapide et KPIs cles."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from security.middleware import security_middleware
from services.data_service import compute_filtered_kpis, load_filtered_main_data, load_top_anomalies
from ui.components import alert_banner, header, kpi_card, render_artifact_gallery, section
from ui.utils import apply_current_admin_filters
from utils.pdf_export import generate_report_pdf


def page_accueil():
    security_middleware.enforce()
    header("Accueil", "Vue synthetique de l'etat du reseau")

    cols = ["timestamp", "station_id", "consommation_kwh", "score_qos",
            "anomalie_score_ensemble", "economie_rl_kwh", "mode_operation"]
    df_raw = load_filtered_main_data(cols)
    df = apply_current_admin_filters(df_raw)
    kpis = compute_filtered_kpis(df) if not df.empty else {}

    nb_stations = kpis.get("nb_stations", 0)
    nb_critiques = 0
    if not df.empty and "mode_operation" in df.columns:
        nb_critiques = int(df[df["mode_operation"].astype(str).eq("CRITIQUE")]["station_id"].nunique())
    eco_dt = kpis.get("economie_dt", 0) or 0

    # Dynamic summary phrase
    with section("Synthese"):
        phrase = (
            f"Le systeme surveille {nb_stations} stations. "
            f"{nb_critiques} necessitent une intervention. "
            f"Les optimisations actives ont economise {eco_dt:,.0f} DT sur la periode."
        )
        st.markdown(f'<div class="summary-strip">{phrase}</div>', unsafe_allow_html=True)

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            kpi_card("Stations", f"{nb_stations}", "Perimetre filtre", "blue")
        with c2:
            conso = kpis.get("conso_totale_kwh")
            kpi_card("Consommation", f"{conso:,.0f} kWh" if conso is not None else "0 kWh", "Total periode", "gray")
        with c3:
            qos = kpis.get("score_qos_moyen")
            kpi_card("QoS moyenne", f"{qos:.2f}" if qos is not None else "0.00", "Qualite service", "eco")
        with c4:
            anom = kpis.get("pct_anomalies")
            kpi_card("Anomalies", f"{anom:.1f}%" if anom is not None else "0.0%", "Score > seuil", "orange")
        with c5:
            kpi_card("Economies", f"{eco_dt:,.0f} DT", "Potentiel RL", "green")

    # Navigation cards
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
<div class="nav-card">
  <div class="nc-title">Carte du reseau</div>
  <div class="nc-value">Vue Globale</div>
  <div class="nc-desc">Visualiser toutes les stations sur la carte interactive</div>
</div>""", unsafe_allow_html=True)
        if st.button("Ouvrir la carte", key="nav_map", width="stretch"):
            st.session_state["_nav_override"] = 1
            st.rerun()

    with c2:
        st.markdown(f"""
<div class="nav-card">
  <div class="nc-title">Stations critiques</div>
  <div class="nc-value">{nb_critiques}</div>
  <div class="nc-desc">Stations necessitant une intervention immediate</div>
</div>""", unsafe_allow_html=True)
        if st.button("Voir les anomalies", key="nav_anom", width="stretch"):
            st.session_state["_nav_override"] = 3
            st.rerun()

    with c3:
        st.markdown(f"""
<div class="nav-card">
  <div class="nc-title">Economies du mois</div>
  <div class="nc-value">{eco_dt:,.0f} DT</div>
  <div class="nc-desc">Grace aux optimisations energetiques RL</div>
</div>""", unsafe_allow_html=True)
        if st.button("Voir les optimisations", key="nav_opt", width="stretch"):
            st.session_state["_nav_override"] = 4
            st.rerun()

    # Recent alerts
    with section("Dernieres Alertes"):
        top_raw = load_top_anomalies(limit=300)
        top = apply_current_admin_filters(top_raw).head(3)
        if not top.empty:
            for _, row in top.iterrows():
                score = float(row.get("anomalie_score_ensemble", 0) or 0)
                sev = "danger" if score > 0.6 else "warning" if score > 0.3 else "info"
                station = str(row.get("station_id", ""))
                ts_str = str(row.get("timestamp", ""))[:16]
                alert_banner(
                    f"Anomalie detectee - Station {station}",
                    f"Score anomalie : {score:.2f}",
                    sev,
                    ts_str,
                )
        else:
            st.info("Aucune anomalie recente detectee.")

    # PDF export
    with section("Rapport"):
        with st.expander("Apercu notebook avance", expanded=False):
            render_artifact_gallery(
                [("tableau_de_bord_complet.png", "Tableau de bord complet genere par NB3")],
                title="Apercu notebook",
                columns=1,
            )
        if st.button("Generer rapport PDF", type="primary", width="stretch"):
            anomaly_items = []
            if not top.empty:
                for _, row in top.head(5).iterrows():
                    score = float(row.get("anomalie_score_ensemble", 0) or 0)
                    anomaly_items.append({
                        "station_id": str(row.get("station_id", "")),
                        "detail": f"Score {score:.2f}",
                        "severity": "CRITIQUE" if score > 0.6 else "ATTENTION" if score > 0.3 else "FAIBLE",
                    })
            pdf_bytes = generate_report_pdf(kpis, anomaly_items)
            st.download_button(
                "Telecharger le rapport PDF",
                data=pdf_bytes,
                file_name=f"rapport_bts_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                width="stretch",
            )
