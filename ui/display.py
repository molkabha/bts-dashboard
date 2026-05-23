"""Libelles d'affichage communs (menu = titre de page)."""

from __future__ import annotations

# Pages notebooks (admin)
PAGE_PREDICTION = "Prediction"
PAGE_ANOMALIES = "Anomalies"
PAGE_DECISIONS = "Decisions"

NB_PAGE_LABELS = [PAGE_PREDICTION, PAGE_ANOMALIES, PAGE_DECISIONS]

ADMIN_PAGE_LABELS = [
    "Accueil",
    "Carte",
    *NB_PAGE_LABELS,
    "Comparaison",
    "Import",
    "Stations",
    "Utilisateurs",
]

ENGINEER_PAGE_LABELS = ["Simulation"]

ADMIN_PAGE_INDEX = {
    "Accueil": 0,
    "Carte": 1,
    PAGE_PREDICTION: 2,
    PAGE_ANOMALIES: 3,
    PAGE_DECISIONS: 14,
    "Comparaison": 10,
    "Import": 11,
    "Stations": 12,
    "Utilisateurs": 13,
}

ENGINEER_PAGE_INDEX = {
    "Simulation": 6,
}
