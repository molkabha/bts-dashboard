import pandas as pd
from services.data_service import apply_admin_dimension_filters, compute_filtered_kpis


def test_admin_dimension_filters():
    df = pd.DataFrame({
        "station_id": ["ST1", "ST2", "ST3"],
        "technologie": ["4G", "3G", "4G"],
        "gouvernorat": ["Tunis", "Sousse", "Tunis"]
    })

    # Filter by technology
    filters = {"technologies": ["4G"]}
    filtered = apply_admin_dimension_filters(df, filters)
    assert len(filtered) == 2
    assert all(filtered["technologie"] == "4G")

    # Filter by gouvernorat
    filters = {"gouvernorats": ["Sousse"]}
    filtered = apply_admin_dimension_filters(df, filters)
    assert len(filtered) == 1
    assert filtered.iloc[0]["gouvernorat"] == "Sousse"


def test_admin_dimension_filters_ignore_qos_min():
    df = pd.DataFrame({
        "station_id": ["ST1", "ST2"],
        "score_qos": [0.2, 0.9],
    })

    filtered = apply_admin_dimension_filters(df, {"qos_min": 0.8})

    assert len(filtered) == 2


def test_compute_kpis_nb3():
    df = pd.DataFrame({
        "consommation_kwh": [100, 200],
        "economie_rl_kwh": [10, 20],
        "mode_operation": ["ECO", "NORMAL"]
    })

    kpis = compute_filtered_kpis(df)
    assert kpis["conso_totale_kwh"] == 300
    assert kpis["economie_rl_pct"] == 10.0  # (30/300 * 100)
    assert kpis["pct_mode_eco"] == 50.0


def test_compute_kpis_returns_none_for_missing_qos():
    df = pd.DataFrame({
        "station_id": ["ST1", "ST2"],
        "consommation_kwh": [100, 200],
    })

    kpis = compute_filtered_kpis(df)

    assert kpis["score_qos_moyen"] is None


def test_compute_kpis_returns_none_for_empty_qos():
    df = pd.DataFrame({
        "station_id": ["ST1", "ST2"],
        "consommation_kwh": [100, 200],
        "score_qos": [None, float("nan")],
    })

    kpis = compute_filtered_kpis(df)

    assert kpis["score_qos_moyen"] is None


def test_metric_value_helper():
    from ui.pages.admin_network import metric_value
    source = {"nb": 1234, "pct": 0.5678, "none": None, "nan": float("nan")}

    assert metric_value(source, "nb") == "1,234"
    assert metric_value(source, "pct", "%", 2) == "0.57%"
    assert metric_value(source, "none") == "N/D"
    assert metric_value(source, "missing") == "N/D"
    assert metric_value(source, "nan") == "N/D"


def test_admin_optimization_actions_summary_handles_missing_numeric_columns():
    from ui.pages.admin_optimization import actions_summary

    df = pd.DataFrame({"action_proposee": ["sleep_mode_secteur", "sleep_mode_secteur", "aucune_action"]})
    summary, action_col = actions_summary(df)

    assert action_col == "action_proposee"
    assert set(["economie_rl_kwh", "conso_moy", "score_qos_moy"]).issubset(summary.columns)
    assert summary["economie_rl_kwh"].sum() == 0.0


def test_sync_selectbox_with_table_selection_updates_state(monkeypatch):
    from ui import utils

    state = {}
    monkeypatch.setattr(utils.st, "session_state", state)
    table = pd.DataFrame({"decision_ref": ["0", "12", "30"]})
    event = {"selection": {"rows": [1]}}

    index = utils.sync_selectbox_with_table_selection(event, table, "decision_ref", ["0", "12", "30"], "selected_ref")

    assert index == 1
    assert state["selected_ref"] == "12"
