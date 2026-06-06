import pandas as pd

from services.nb_metrics import (
    NB_CATEGORIE_CRITIQUE_MIN,
    NB_CATEGORIE_EFFICACE_MAX,
    compute_nb_station_scores_from_df,
    nb_categorie_from_criticite,
    nb_score_criticite_from_components,
)


def test_nb_score_criticite_matches_export_formula():
    pct = pd.Series([0.045617, 0.130711])
    score = pd.Series([0.066877, 0.099050])
    votes = pd.Series([0.398125, 0.583967])

    crit = nb_score_criticite_from_components(pct, score, votes)

    assert abs(float(crit.iloc[0]) - 0.0542) < 0.001
    assert abs(float(crit.iloc[1]) - 0.1118) < 0.001


def test_nb_categorie_thresholds():
    assert nb_categorie_from_criticite(0.04) == "EFFICACE"
    assert nb_categorie_from_criticite(0.08) == "ATTENTION"
    assert nb_categorie_from_criticite(0.16) == "CRITIQUE"


def test_compute_nb_station_scores_from_df():
    df = pd.DataFrame(
        {
            "station_id": ["S1", "S1", "S2", "S2"],
            "anomalie_score_ensemble": [0.05, 0.20, 0.10, 0.12],
            "nb_votes_anomalie": [1, 3, 2, 2],
            "score_qos": [0.9, 0.8, 0.7, 0.75],
            "consommation_kwh": [100.0] * 4,
            "gouvernorat": ["Ariana"] * 4,
            "technologie": ["4G"] * 4,
            "type_zone": ["Urbain"] * 4,
        }
    )

    summary = compute_nb_station_scores_from_df(df, seuil_anom=0.13)

    assert set(summary["station_id"]) == {"S1", "S2"}
    assert "score_criticite" in summary.columns
    assert "categorie" in summary.columns
    assert summary["categorie"].isin(["EFFICACE", "ATTENTION", "CRITIQUE"]).all()
    assert float(summary.loc[summary["station_id"] == "S1", "pct_anomalie_ensemble"].iloc[0]) == 0.5
