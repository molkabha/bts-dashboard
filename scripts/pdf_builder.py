"""Shared PDF builder for BTS EMS documentation."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF


def safe(text: object) -> str:
    raw = str(text) if text is not None else ""
    repl = {
        "—": "-",
        "–": "-",
        "'": "'",
        """: '"',
        """: '"',
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "à": "a",
        "â": "a",
        "ä": "a",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ô": "o",
        "ö": "o",
        "î": "i",
        "ï": "i",
        "ç": "c",
        "É": "E",
        "È": "E",
        "À": "A",
        "Ç": "C",
        "₂": "2",
        "≈": "~",
        "≥": ">=",
        "≤": "<=",
        "λ": "lambda",
        "→": "->",
    }
    for a, b in repl.items():
        raw = raw.replace(a, b)
    return raw.encode("latin-1", errors="replace").decode("latin-1")


class DocPDF(FPDF):
    def __init__(self, doc_title: str = "BTS EMS"):
        super().__init__()
        self.doc_title = doc_title

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, safe(self.doc_title), align="L")
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, safe(f"Page {self.page_no()} - Tunisie Telecom PFE"), align="C")

    def cover(self, title: str, subtitle: str = ""):
        self.h1(title)
        if subtitle:
            self.p(subtitle)
        self.p(f"Document genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')}")
        self.ln(2)

    def h1(self, t: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(30, 58, 138)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 9, safe(t))
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def h2(self, t: str):
        self._break(18)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(200, 16, 46)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 7, safe(t))
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def h3(self, t: str):
        self._break(12)
        self.set_font("Helvetica", "B", 10)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 6, safe(t))
        self.ln(1)

    def p(self, t: str):
        self.set_font("Helvetica", "", 9)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 5, safe(t))
        self.ln(2)

    def qa(self, num: int, question: str, answer: str):
        self._break(22)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(30, 58, 138)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 5, safe(f"Q{num}. {question}"))
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 9)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 4.5, safe(f"R: {answer}"))
        self.ln(2)

    def bullet(self, items: list[str]):
        self.set_font("Helvetica", "", 9)
        for it in items:
            self._break(7)
            self.set_x(self.l_margin)
            self.multi_cell(self.epw, 5, safe(f"- {it}"))
        self.ln(2)

    def table(
        self,
        headers: list[str],
        rows: list[list[str]],
        col_widths: list[int] | None = None,
    ):
        self._break(10 + 6 * (len(rows) + 1))
        if not col_widths:
            col_widths = [int(self.epw / len(headers))] * len(headers)
        total = sum(col_widths)
        if total > self.epw:
            scale = self.epw / total
            col_widths = [int(w * scale) for w in col_widths]
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(30, 58, 138)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, safe(h), border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 8)
        self.set_text_color(0, 0, 0)
        fill = False
        for row in rows:
            self.set_fill_color(245, 247, 250) if fill else self.set_fill_color(255, 255, 255)
            fill = not fill
            self.set_x(self.l_margin)
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 6, safe(str(cell)[:40]), border=1, fill=True)
            self.ln()
        self.ln(2)

    def _break(self, need: float):
        if self.get_y() + need > 275:
            self.add_page()

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.output(str(path))
