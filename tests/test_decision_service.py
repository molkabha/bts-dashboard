from __future__ import annotations

import pandas as pd

from services.decision_service import MoteurDecisionEnergie


def test_decider_mode_eco_night_window():

    moteur = MoteurDecisionEnergie()

    row = pd.Series(
        {
            "anomalie_score_ensemble": 0.1,
            "ecart_pct": 5.0,
            "charge_cpu_pct": 30.0,
            "heure": 3,
            "nb_votes_anomalie": 0,
            "score_qos": 0.85,
        }
    )

    out = moteur.decider_mode(row)

    assert out["mode_operation"] == "ECO"

    assert out["eco_potentiel_pct"] == 20


def test_decider_mode_critique_high_score():

    moteur = MoteurDecisionEnergie()

    row = pd.Series(
        {
            "anomalie_score_ensemble": 0.75,
            "ecart_pct": 5.0,
            "charge_cpu_pct": 40.0,
            "heure": 14,
            "nb_votes_anomalie": 1,
            "score_qos": 0.9,
        }
    )

    assert moteur.decider_mode(row)["mode_operation"] == "CRITIQUE"


def test_decider_mode_attention_high_ecart():

    moteur = MoteurDecisionEnergie()

    row = pd.Series(
        {
            "anomalie_score_ensemble": 0.2,
            "ecart_pct": 35.0,
            "charge_cpu_pct": 40.0,
            "heure": 14,
            "nb_votes_anomalie": 0,
            "score_qos": 0.9,
        }
    )

    assert moteur.decider_mode(row)["mode_operation"] == "ATTENTION"
