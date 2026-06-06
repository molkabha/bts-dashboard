from pathlib import Path

import pandas as pd
import pytest

from services.data_service import NB_ALERT_CATEGORIES
from services.nb_metrics import (
    NB_CATEGORIE_CRITIQUE_MIN,
    NB_CATEGORIE_EFFICACE_MAX,
    nb_categorie_from_criticite,
    nb_score_criticite_from_components,
)


EXPORT_PATH = Path(__file__).resolve().parents[1] / ".tmp_score.parquet"


@pytest.mark.skipif(not EXPORT_PATH.exists(), reason="HF export sample not available")
def test_export_tt_ari_045_matches_nb_labels():
    export = pd.read_parquet(EXPORT_PATH)
    row = export.loc[export["station_id"] == "TT-ARI-045"].iloc[0]

    assert row["categorie"] == "ATTENTION"
    assert abs(float(row["score_criticite"]) - 0.0542) < 0.001
    assert nb_categorie_from_criticite(float(row["score_criticite"])) == "ATTENTION"


@pytest.mark.skipif(not EXPORT_PATH.exists(), reason="HF export sample not available")
def test_export_categories_use_nb_thresholds():
    export = pd.read_parquet(EXPORT_PATH)

    for _, row in export.iterrows():
        crit = float(row["score_criticite"])
        expected = nb_categorie_from_criticite(crit)
        assert row["categorie"] == expected


@pytest.mark.skipif(not EXPORT_PATH.exists(), reason="HF export sample not available")
def test_export_score_criticite_formula():
    export = pd.read_parquet(EXPORT_PATH)

    recomputed = nb_score_criticite_from_components(
        export["pct_anomalie_ensemble"],
        export["score_moy_ensemble"],
        export["nb_votes_moy"],
    )

    diff = (recomputed - export["score_criticite"]).abs()
    assert float(diff.max()) < 0.001


@pytest.mark.skipif(not EXPORT_PATH.exists(), reason="HF export sample not available")
def test_alert_count_matches_export_categories():
    export = pd.read_parquet(EXPORT_PATH)

    alert_count = int(
        export["categorie"].astype(str).str.upper().isin(NB_ALERT_CATEGORIES).sum()
    )

    assert alert_count == 41
    assert int((export["categorie"] == "CRITIQUE").sum()) == 2
    assert int((export["categorie"] == "EFFICACE").sum()) == 25


def test_nb_category_threshold_constants():
    assert nb_categorie_from_criticite(NB_CATEGORIE_EFFICACE_MAX) == "EFFICACE"
    assert nb_categorie_from_criticite(NB_CATEGORIE_EFFICACE_MAX + 0.001) == "ATTENTION"
    assert nb_categorie_from_criticite(NB_CATEGORIE_CRITIQUE_MIN) == "CRITIQUE"
