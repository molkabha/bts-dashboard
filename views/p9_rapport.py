"""Page 9 - Rapport executif (admin)."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from security.middleware import security_middleware
from services.data_service import compute_filtered_kpis, load_top_anomalies
from ui.components import header, section
from ui.page_helpers import load_dashboard_df
from ui.utils import apply_current_admin_filters
from utils.pdf_export import generate_report_pdf


def page_rapport():
    security_middleware.enforce()
    header("Rapport", "Export PDF et synthese executive")

    df = load_dashboard_df()
    kpis = compute_filtered_kpis(df) if not df.empty else {}

    with section("Generer le rapport"):
        top = apply_current_admin_filters(load_top_anomalies(limit=300)).head(5)
        anomaly_items = []
        if not top.empty:
            for _, row in top.iterrows():
                score = float(row.get("anomalie_score_ensemble", 0) or 0)
                anomaly_items.append({
                    "station_id": str(row.get("station_id", "")),
                    "detail": f"Score {score:.2f}",
                    "severity": "CRITIQUE" if score > 0.6 else "ATTENTION" if score > 0.3 else "FAIBLE",
                })
        if st.button("Generer rapport PDF", type="primary", width="stretch"):
            pdf_bytes = generate_report_pdf(kpis, anomaly_items)
            st.download_button(
                "Telecharger le rapport PDF",
                data=pdf_bytes,
                file_name=f"rapport_bts_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                width="stretch",
            )
