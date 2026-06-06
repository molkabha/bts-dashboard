"""Generate ultra-hard jury Q&A PDF for Simulation page."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.jury_simulation_qa_data import SECTIONS  # noqa: E402
from scripts.pdf_builder import DocPDF  # noqa: E402


def build_pdf() -> DocPDF:
    pdf = DocPDF(doc_title="Jury Simulation - Q&R ultra-hard")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    total_q = sum(len(items) for _, items in SECTIONS)

    pdf.cover(
        "Questions-Reponses Jury - Page Simulation",
        f"{total_q} questions ultra-hard avec reponses techniques argumentees",
    )

    pdf.h2("Mode d'emploi pour le soutenance")
    pdf.bullet(
        [
            "Lire la question jusqu'au bout avant de repondre (beaucoup sont des pieges)",
            "Commencer par la reponse courte (Oui/Non/Chiffre), puis justification code",
            "Citer un fichier module si le jury pousse (ex: simulation_events.py)",
            "Assumer les limites PFE (pas temps reel) puis proposer evolution production",
            "En demo live: montrer CSV export ou progression tick/total comme preuve",
        ]
    )

    pdf.h2("Index des themes")
    for i, (title, items) in enumerate(SECTIONS, 1):
        pdf.p(f"{i}. {title} ({len(items)} questions)")

    qnum = 0
    for title, items in SECTIONS:
        pdf.add_page()
        pdf.h2(title)
        for question, answer in items:
            qnum += 1
            pdf.qa(qnum, question, answer)

    pdf.add_page()
    pdf.h2("Cheat sheet - chiffres a memoriser")
    pdf.table(
        ["Parametre", "Valeur", "Source"],
        [
            ["Prix kWh", "0.40 DT", "settings.PRIX_KWH_TN"],
            ["Plafond eco", "48% conso", "settings.NB3_MAX_ECO_FRAC"],
            ["Seuil QoS defaut", "0.6", "settings.QOS_SEUIL_DEFAULT"],
            ["Intervalle auto defaut", "30 s", "SIM_AUTO_INTERVAL_DEFAULT_S"],
            ["Seuil ecart alerte", "30% / 50%", "simulation_events"],
            ["Score mode CRITIQUE", ">0.6 ou 5 votes", "decision_service"],
            ["Creneau ECO", "0h-6h", "decision_service eco_heure_*"],
            ["Free cooling gain", "15% conso", "optimization_service"],
            ["Schema sim", "v3", "SIM_SCHEMA_VERSION"],
            ["Chunk pipeline batch", "360 lignes", "synthetic_bts _enrich_period_rows"],
        ],
        [55, 45, 90],
    )

    pdf.h2("Phrases de conclusion recommandees")
    pdf.bullet(
        [
            "La Simulation prouve l'orchestration NB1-NB2-NB3, pas le remplacement de l'EMS TT.",
            "Chaque KPI simulation est tracable jusqu'a une formule et un fichier source.",
            "Les garde-fous QoS et plafond 48% evitent des recommandations dangereuses.",
            "Le passage production = connecteurs temps reel + gouvernance MLOps + PostgreSQL.",
        ]
    )

    return pdf


def main() -> None:
    out = ROOT / "docs" / "100_Questions_Jury_Simulation_BTS_EMS.pdf"
    build_pdf().save(out)
    print(f"PDF genere : {out}")


if __name__ == "__main__":
    main()
