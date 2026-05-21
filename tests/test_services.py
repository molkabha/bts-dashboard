"""Service-layer tests."""

from __future__ import annotations

import pandas as pd

# Fix: both imports now use the same bare-module style (no "dashboard_app." prefix).
from services.optimization_service import StrategieOptimisation
from services.decision_service import MoteurDecisionEnergie
from services.data_service import station_summary_from_df


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
    assert result.loc[0, "mode_operation"] == "NORMAL"  # Day (12)


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


def test_pipeline_fills_empty_realtime_business_columns():
    """Realtime generator may provide NB3 columns as None; the pipeline must compute them."""
    from services.pipeline_service import simulate_nb_pipeline

    df = pd.DataFrame(
        [
            {
                "station_id": "S1",
                "consommation_kwh": 10,
                "score_qos": 0.9,
                "charge_cpu_pct": 25,
                "optimisation_qos_autorisee": 1,
                "heure": 3,
                "taux_charge_voix": 0.05,
                "taux_charge_data": 0.05,
                "nb_secteurs_actifs": 3,
                "technologie": "4G",
                "mode_operation": None,
                "action_proposee": None,
                "economie_estimee_kwh": None,
            }
        ]
    )

    result = simulate_nb_pipeline(df, source="flux_temps_reel_genere")

    assert result.loc[0, "mode_operation"] == "ECO"
    assert result.loc[0, "action_proposee"] == "sleep_mode_secteur"
    assert result.loc[0, "economie_estimee_kwh"] > 0


def test_station_summary_always_has_criticite_columns():
    df = pd.DataFrame(
        {
            "station_id": ["S1", "S1", "S2"],
            "consommation_kwh": [10.0, 12.0, 8.0],
            "technologie": ["4G", "4G", "3G"],
        }
    )

    summary = station_summary_from_df(df)

    assert "score_criticite" in summary.columns
    assert "categorie" in summary.columns
    assert summary["score_criticite"].notna().all()


def test_realtime_generation_handles_reference_without_qos(monkeypatch):
    from services import realtime_generator

    reference = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-05-07 20:00:00", "2026-05-07 21:00:00"]),
            "station_id": ["S1", "S1"],
            "technologie": ["4G", "4G"],
            "consommation_kwh": [4.0, 4.5],
            "heure": [20, 21],
            "mois": [5, 5],
        }
    )
    monkeypatch.setattr(realtime_generator, "load_station_data", lambda *args, **kwargs: reference)

    result = realtime_generator.generate_realtime_station_data(
        "S1",
        periods=2,
        anomaly_rate=0.0,
        seed=1,
        start_time=pd.Timestamp("2026-05-07 20:00:00").to_pydatetime(),
        freq_minutes=60,
    )

    assert len(result) == 2
    assert result["score_qos"].notna().all()
    assert result.loc[0, "timestamp"] == pd.Timestamp("2026-05-07 20:00:00")
    assert result.loc[1, "timestamp"] == pd.Timestamp("2026-05-07 21:00:00")


def test_realtime_dataset_one_capture_per_station(monkeypatch):
    from services import realtime_generator

    monkeypatch.setattr(realtime_generator, "load_station_data", lambda *args, **kwargs: pd.DataFrame())

    result = realtime_generator.generate_realtime_dataset(
        ["S1", "S2", "S3"],
        periods=1,
        anomaly_rate=0.0,
        seed=10,
        start_time=pd.Timestamp("2026-05-07 20:00:00").to_pydatetime(),
        freq_minutes=60,
    )

    assert len(result) == 3
    assert result["station_id"].tolist() == ["S1", "S2", "S3"]
    assert result["timestamp"].nunique() == 1


def test_realtime_capture_uses_station_local_next_timestamp(monkeypatch):
    from services import realtime_generator

    monkeypatch.setattr(realtime_generator, "load_station_data", lambda *args, **kwargs: pd.DataFrame())
    existing = pd.DataFrame(
        {
            "station_id": ["S1", "S1", "S2"],
            "timestamp": pd.to_datetime(
                ["2026-05-07 20:00:00", "2026-05-07 21:00:00", "2026-05-07 19:00:00"]
            ),
        }
    )

    capture = realtime_generator.generate_realtime_capture(
        ["S1", "S2", "S3"],
        existing=existing,
        anomaly_rate=0.0,
        seed=20,
        freq_minutes=60,
        now=pd.Timestamp("2026-05-07 20:30:00").to_pydatetime(),
    )

    by_station = capture.set_index("station_id")["timestamp"]
    assert by_station["S1"] == pd.Timestamp("2026-05-07 22:00:00")
    assert by_station["S2"] == pd.Timestamp("2026-05-07 20:00:00")
    assert by_station["S3"] == pd.Timestamp("2026-05-07 20:30:00")


def test_append_realtime_capture_deduplicates_station_timestamp():
    from services.realtime_generator import append_realtime_capture

    existing = pd.DataFrame(
        {
            "station_id": ["S1"],
            "timestamp": pd.to_datetime(["2026-05-07 20:00:00"]),
            "consommation_kwh": [1.0],
        }
    )
    capture = pd.DataFrame(
        {
            "station_id": ["S1", "S2"],
            "timestamp": pd.to_datetime(["2026-05-07 20:00:00", "2026-05-07 20:00:00"]),
            "consommation_kwh": [2.0, 3.0],
        }
    )

    result = append_realtime_capture(existing, capture)

    assert len(result) == 2
    assert result[result["station_id"] == "S1"].iloc[0]["consommation_kwh"] == 2.0
