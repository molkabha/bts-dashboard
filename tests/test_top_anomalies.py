from __future__ import annotations

import pandas as pd

from services.data_service import top_anomaly_stations_from_df


def test_top_anomaly_stations_from_df_respects_filter():

    df = pd.DataFrame(
        {
            "station_id": ["A", "A", "B", "B"],
            "anomalie_score_ensemble": [0.05, 0.08, 0.9, 0.85],
        }
    )

    filtered = df[df["station_id"] == "A"]

    top = top_anomaly_stations_from_df(filtered, limit=5)

    assert len(top) == 1

    assert top.iloc[0]["station_id"] == "A"

    assert float(top.iloc[0]["anomalie_score_ensemble"]) == 0.08


def test_top_anomaly_stations_empty_when_scores_missing():

    df = pd.DataFrame({"station_id": ["A"], "consommation_kwh": [1.0]})

    assert top_anomaly_stations_from_df(df).empty
