"""Service-layer tests."""

from __future__ import annotations

import pandas as pd
import pytest

# Fix: both imports now use the same bare-module style (no "dashboard_app." prefix).
from services.optimization_service import StrategieOptimisation
from services.decision_service import MoteurDecisionEnergie


def test_decision_service_marks_low_load_night_as_eco():
    service = MoteurDecisionEnergie()
    row = pd.Series(
        {
            "anomalie_score_ensemble": 0.1,
            "ecart_pct": 5,
            "charge_cpu_pct": 25,
            "heure": 3,
            "nb_votes_anomalie": 0,
            "score_qos": 0.9,
            "optimisation_qos_autorisee": 1,
        }
    )

    assert service.decider_mode(row)["mode_operation"] == "ECO"


def test_optimization_service_adds_sleep_action_when_allowed():
    df = pd.DataFrame(
        [
            {
                "optimisation_qos_autorisee": 1,
                "heure": 3,
                "taux_charge_voix": 0.05,
                "taux_charge_data": 0.05,
                "score_qos": 0.9,
                "nb_secteurs_actifs": 3,
                "technologie": "4G",
                "consommation_kwh": 10,
            }
        ]
    )

    result = StrategieOptimisation().appliquer(df)

    assert result.loc[0, "action_proposee"] == "sleep_mode_secteur"
    assert result.loc[0, "economie_estimee_kwh"] > 0


def test_optimization_service_handles_missing_technologie():
    df = pd.DataFrame(
        [
            {
                "optimisation_qos_autorisee": 1,
                "heure": 3,
                "taux_charge_voix": 0.05,
                "taux_charge_data": 0.05,
                "score_qos": 0.9,
                "nb_secteurs_actifs": 3,
                "consommation_kwh": 10,
            }
        ]
    )

    result = StrategieOptimisation().appliquer(df)

    assert "action_proposee" in result.columns
    assert "economie_estimee_kwh" in result.columns


def test_decision_service_handles_missing_columns():
    """Verify that appliquer_sur_dataset handles missing columns safely."""
    service = MoteurDecisionEnergie()
    # Missing 'anomalie_score_ensemble', 'ecart_pct', etc.
    df = pd.DataFrame([
        {"station_id": "ST1", "heure": 12, "charge_cpu_pct": 40},
        {"station_id": "ST2", "heure": 3, "charge_cpu_pct": 20}
    ])
    
    result = service.appliquer_sur_dataset(df)
    
    assert "mode_operation" in result.columns
    assert len(result) == 2
    assert result.loc[1, "mode_operation"] == "ECO"  # Night (3), low CPU (20), default scores
    assert result.loc[0, "mode_operation"] == "NORMAL" # Day (12)


def test_full_optimization_pipeline():
    """Simulate a full run of the optimization pipeline."""
    from services.pipeline_service import simulate_nb_pipeline

    # Mock data for the pipeline
    mock_df = pd.DataFrame({
        "station_id": ["S1", "S2"],
        "timestamp": pd.to_datetime(["2024-01-01", "2024-01-01"]),
        "consommation_kwh": [10, 20],
        "score_qos": [0.9, 0.9],
        "optimisation_qos_autorisee": [1, 1],
        "heure": [3, 3],
        "taux_charge_voix": [0.05, 0.05],
        "taux_charge_data": [0.05, 0.05],
        "nb_secteurs_actifs": [3, 3],
        "technologie": ["4G", "4G"]
    })

    # Call the pipeline directly with the mock data
    results = simulate_nb_pipeline(mock_df)

    assert isinstance(results, pd.DataFrame)
    assert len(results) == 2
    assert "action_rl" in results.columns
    assert all(results["action_rl"] != "")