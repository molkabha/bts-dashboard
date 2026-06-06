from __future__ import annotations

import pandas as pd

from services.data_service import _nb3_prorata_economies


def test_nb3_prorata_scales_down_with_shorter_period():

    nb3_kpi = {
        "conso_totale_kwh": 1000.0,
        "economie_combinee_kwh": 100.0,
        "economie_rl_kwh": 40.0,
        "economie_dt": 40.0,
        "co2_evite_t": 2.0,
    }

    full = pd.DataFrame({"consommation_kwh": [600.0, 400.0]})

    partial = pd.DataFrame({"consommation_kwh": [600.0, 300.0]})

    full_result = _nb3_prorata_economies(full, nb3_kpi)

    partial_result = _nb3_prorata_economies(partial, nb3_kpi)

    assert full_result is not None

    assert partial_result is not None

    assert partial_result[3] < full_result[3]

    assert abs(full_result[3] - 40.0) < 1e-6

    assert abs(partial_result[3] - 36.0) < 1e-6
