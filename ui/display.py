from __future__ import annotations

PAGE_PREDICTION = "Prédiction"

PAGE_ANOMALIES = "Anomalies"

PAGE_OPTIMISATION = "Optimisation"

CORE_PAGE_LABELS = [
    "Accueil",
    "Carte",
    PAGE_PREDICTION,
    PAGE_ANOMALIES,
    PAGE_OPTIMISATION,
    "Simulation",
]

ADMIN_PAGE_LABELS = [*CORE_PAGE_LABELS, "Configuration"]

ENGINEER_PAGE_LABELS = list(CORE_PAGE_LABELS)

_PAGE_INDEX = {
    "Accueil": 0,
    "Carte": 1,
    PAGE_PREDICTION: 2,
    PAGE_ANOMALIES: 3,
    PAGE_OPTIMISATION: 14,
    "Simulation": 6,
    "Configuration": 12,
}

ADMIN_PAGE_INDEX = dict(_PAGE_INDEX)

ENGINEER_PAGE_INDEX = {k: v for k, v in _PAGE_INDEX.items() if k != "Configuration"}

ADMIN_ONLY_PAGE_INDICES = {12}
