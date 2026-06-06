from __future__ import annotations

import pandas as pd

from services.nb_metrics import (
    compute_ecart_pct,
    effective_economie_kwh,
    harmonize_nb3_economies,
    merge_business_columns,
    nb3_row_economie_kwh,
)


def test_compute_ecart_pct():

    conso = pd.Series([110.0])

    pred = pd.Series([100.0])

    assert float(compute_ecart_pct(conso, pred).iloc[0]) == 10.0


def test_harmonize_nb3_economies_max_without_dashboard_cap():

    df = pd.DataFrame(
        {
            "consommation_kwh": [10.0],
            "economie_estimee_kwh": [3.0],
            "economie_rl_kwh": [5.0],
        }
    )

    out = harmonize_nb3_economies(df)

    assert float(out["economie_kwh"].iloc[0]) == 5.0

    assert float(out["conso_optimisee_kwh"].iloc[0]) == 5.0


def test_nb3_row_economie_kwh_returns_series():

    df = pd.DataFrame(
        {
            "economie_estimee_kwh": [3.0],
            "economie_rl_kwh": [5.0],
            "economie_kwh": [6.0],
        }
    )

    eco = nb3_row_economie_kwh(df)

    assert isinstance(eco, pd.Series)

    assert hasattr(eco, "empty")

    assert float(eco.iloc[0]) == 6.0


def test_harmonize_nb3_economies_preserves_nb3_export():

    df = pd.DataFrame(
        {
            "consommation_kwh": [10.0],
            "economie_estimee_kwh": [3.0],
            "economie_rl_kwh": [5.0],
            "economie_kwh": [6.0],
        }
    )

    out = harmonize_nb3_economies(df)

    assert float(out["economie_kwh"].iloc[0]) == 6.0


def test_effective_economie_kwh_matches_harmonized_column():

    df = pd.DataFrame(
        {
            "consommation_kwh": [8.0],
            "economie_estimee_kwh": [2.0],
            "economie_rl_kwh": [1.5],
        }
    )

    eco = effective_economie_kwh(df)

    harmonized = harmonize_nb3_economies(df)

    assert float(eco.iloc[0]) == float(harmonized["economie_kwh"].iloc[0])


def test_merge_business_columns_fills_missing():

    left = pd.DataFrame({"station_id": ["A"], "anomalie_score_ensemble": [None]})

    right = pd.DataFrame({"station_id": ["A"], "anomalie_score_ensemble": [0.42]})

    merged = merge_business_columns(
        left, right, ["anomalie_score_ensemble"], ["station_id"]
    )

    assert float(merged["anomalie_score_ensemble"].iloc[0]) == 0.42
