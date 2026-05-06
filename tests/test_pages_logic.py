import pytest
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

def test_compute_kpis_nb3():
    df = pd.DataFrame({
        "consommation_kwh": [100, 200],
        "economie_rl_kwh": [10, 20],
        "mode_operation": ["ECO", "NORMAL"]
    })
    
    kpis = compute_filtered_kpis(df)
    assert kpis["conso_totale_kwh"] == 300
    assert kpis["economie_rl_pct"] == 10.0 # (30/300 * 100)
    assert kpis["pct_mode_eco"] == 50.0

def test_metric_value_helper():
    from ui.pages.admin_network import metric_value
    source = {"nb": 1234, "pct": 0.5678, "none": None}
    
    assert metric_value(source, "nb") == "1,234"
    assert metric_value(source, "pct", "%", 2) == "0.57%"
    assert metric_value(source, "none") == "N/D"
    assert metric_value(source, "missing") == "N/D"
