"""PDF report generation for one-click export."""

from __future__ import annotations

import io
from datetime import date, datetime
from pathlib import Path

from fpdf import FPDF
import pandas as pd


def _pdf_safe(text: object) -> str:
    """Helvetica FPDF : ASCII + accents courants remplaces."""
    raw = str(text) if text is not None else ""
    replacements = {
        "—": "-", "–": "-", "’": "'", "“": '"', "”": '"',
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "ä": "a",
        "ù": "u", "û": "u", "ü": "u",
        "ô": "o", "ö": "o",
        "î": "i", "ï": "i",
        "ç": "c",
        "É": "E", "È": "E", "À": "A", "Ç": "C",
        "₂": "2",
    }
    for src, dst in replacements.items():
        raw = raw.replace(src, dst)
    return raw.encode("latin-1", errors="replace").decode("latin-1")


class RapportPDF(FPDF):
    def header(self):
        logo_path = Path(__file__).resolve().parents[1] / "static" / "logo.png"
        if logo_path.exists():
            self.image(str(logo_path), 10, 6, 30)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Tunisie Telecom - BTS Energy Management", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(100, 100, 100)
        date_str = datetime.now().strftime('%d/%m/%Y a %H:%M')
        self.cell(
            0, 5,
            f"Rapport généré le {date_str}",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(4)
        self.set_draw_color(200, 16, 46)
        self.set_line_width(0.6)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} - Confidentiel Tunisie Telecom", align="C")

    def section_title(self, title: str):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(30, 58, 138)
        self.cell(0, 8, _pdf_safe(title), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def kpi_row(self, items: list[tuple[str, str]]):
        self.set_font("Helvetica", "", 10)
        col_w = 190 / max(len(items), 1)
        y = self.get_y()
        for label, value in items:
            x = self.get_x()
            self.set_font("Helvetica", "", 8)
            self.set_text_color(100, 100, 100)
            self.cell(col_w, 5, _pdf_safe(label), new_x="LMARGIN", new_y="NEXT")
            self.set_x(x)
            self.set_font("Helvetica", "B", 14)
            self.set_text_color(0, 0, 0)
            self.cell(col_w, 8, _pdf_safe(value), new_x="LMARGIN", new_y="NEXT")
            self.set_xy(x + col_w, y)
        self.set_y(y + 16)
        self.ln(4)

    def text_block(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5, _pdf_safe(text))
        self.ln(3)

    def table_rows(self, headers: tuple[str, ...], rows: list[tuple[str, ...]], col_widths: tuple[float, ...]):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(240, 240, 245)
        for header, width in zip(headers, col_widths):
            self.cell(width, 7, _pdf_safe(header), border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 9)
        fill = False
        for row in rows:
            if self.get_y() > 270:
                self.add_page()
            for value, width in zip(row, col_widths):
                self.cell(width, 6, _pdf_safe(str(value)[:48]), border=1, fill=fill)
            self.ln()
            fill = not fill

    def anomaly_item(self, station: str, detail: str, severity: str):
        color_map = {"CRITIQUE": (220, 38, 38), "ATTENTION": (234, 179, 8), "FAIBLE": (100, 116, 139)}
        r, g, b = color_map.get(severity, (100, 100, 100))
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(r, g, b)
        self.cell(30, 6, severity)
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "B", 10)
        self.cell(50, 6, station)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(80, 80, 80)
        self.cell(0, 6, detail, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)


def generate_report_pdf(kpis: dict, top_anomalies: list[dict] | None = None) -> bytes:
    """Generate a one-page PDF summary report and return bytes."""
    pdf = RapportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.section_title("Indicateurs Cles de Performance")
    nb_stations = str(kpis.get("nb_stations", "0"))
    conso = f"{kpis.get('conso_totale_kwh', 0):,.0f} kWh" if pd.notna(kpis.get("conso_totale_kwh")) else "0 kWh"
    eco_pct = f"{kpis.get('economie_rl_pct', 0):.1f}%" if pd.notna(kpis.get("economie_rl_pct")) else "0.0%"
    eco_dt = f"{kpis.get('economie_dt', 0):,.0f} DT" if pd.notna(kpis.get("economie_dt")) else "0 DT"
    co2 = f"{kpis.get('co2_evite_t', 0):.1f} t" if pd.notna(kpis.get("co2_evite_t")) else "0.0 t"
    qos = f"{kpis.get('score_qos_moyen', 0):.3f}" if pd.notna(kpis.get("score_qos_moyen")) else "0.000"
    pct_anom = kpis.get("pct_anomalies")
    anomalies = f"{float(pct_anom):.1f}%" if pct_anom is not None and pd.notna(pct_anom) else "N/D"

    pdf.kpi_row([("Stations", nb_stations), ("Consommation", conso),
                ("Économies", eco_pct), ("Économies (DT)", eco_dt)])
    pdf.kpi_row([("CO₂ évité", co2), ("QoS moyen", qos), ("Anomalies", anomalies)])

    if top_anomalies:
        pdf.section_title("Top Anomalies Detectees")
        for item in top_anomalies[:5]:
            pdf.anomaly_item(
                str(item.get("station_id", "")),
                str(item.get("detail", "")),
                str(item.get("severity", "FAIBLE")),
            )
        pdf.ln(4)

    pdf.section_title("Recommandations")
    pdf.text_block(
        "1. Activer le sleep mode nocturne sur les stations a faible trafic pour maximiser les economies.\n"
        "2. Surveiller les stations en mode CRITIQUE et planifier les interventions NOC.\n"
        "3. Exploiter le free cooling pendant les periodes hivernales pour reduire la climatisation.\n"
        "4. Maintenir le score QoS au-dessus de 0.70 avant toute optimisation energetique."
    )

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def generate_simulation_sommaire_pdf(
    report: pd.DataFrame,
    *,
    sim_date: date | None = None,
    selected_stations: list[str] | None = None,
    alerts: list[dict] | None = None,
) -> bytes:
    """Rapport sommaire simulation (PDF) : total, par station, alertes."""
    pdf = RapportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.section_title("Rapport sommaire - Simulation BTS")
    date_label = str(sim_date) if sim_date else "-"
    stations_label = ", ".join(selected_stations or []) or "-"
    pdf.text_block(f"Date du scenario : {date_label}\nStations : {stations_label}")

    if report.empty:
        pdf.text_block("Aucune donnee de simulation disponible.")
    elif "Section" in report.columns:
        work = report.copy()

        total_rows = work[work["Section"].astype(str) == "Total"]
        if total_rows.empty:
            total_rows = work[work["Section"].astype(str) == "Sommaire global"]
        if not total_rows.empty:
            pdf.section_title("Total reseau")
            pdf.table_rows(
                ("Indicateur", "Valeur", "Unite"),
                [
                    (str(r["Libelle"]), str(r["Valeur"]), str(r.get("Unite", "") or ""))
                    for _, r in total_rows.iterrows()
                ],
                (95, 55, 30),
            )
            pdf.ln(4)

        station_sections = sorted(
            {s for s in work["Section"].astype(str).unique() if str(s).startswith("Station ")},
        )
        if station_sections:
            pdf.section_title("Par station")
            station_table: list[tuple[str, ...]] = []
            for section in station_sections[:40]:
                sid = section.replace("Station ", "")
                sub = {str(r["Libelle"]): r["Valeur"] for _, r in work[work["Section"] == section].iterrows()}
                station_table.append((
                    sid,
                    str(sub.get("Consommation reelle", "-")),
                    str(sub.get("Consommation predite", "-")),
                    str(sub.get("Ecart moyen", "-")),
                    str(sub.get("Gain (DT)", "-")),
                ))
            pdf.table_rows(
                ("Station", "Reel (kWh)", "Predit (kWh)", "Ecart %", "Gain (DT)"),
                station_table,
                (38, 32, 32, 28, 28),
            )
            pdf.ln(4)

    pdf.section_title("Alertes")
    alert_items = list(alerts or [])
    if not alert_items:
        pdf.text_block("Aucune alerte generee pendant la simulation.")
    else:
        alert_rows: list[tuple[str, ...]] = []
        for item in alert_items[-40:]:
            ts = item.get("timestamp")
            heure = pd.Timestamp(ts).strftime("%d/%m %H:%M") if ts is not None else "-"
            alert_rows.append((
                heure,
                str(item.get("station_id", "")),
                str(item.get("severity", "")),
                str(item.get("message", ""))[:70],
            ))
        pdf.table_rows(
            ("Heure", "Station", "Gravite", "Message"),
            alert_rows,
            (28, 38, 28, 96),
        )

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
