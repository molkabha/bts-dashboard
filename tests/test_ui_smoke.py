from ui.pages.engineer_simulation import engineer_simulation_page
from ui.pages.engineer_actions import engineer_actions_page
from ui.pages.engineer_alerts import engineer_alerts_page
from ui.pages.engineer_monitoring import engineer_monitoring_page
from ui.pages.engineer_stations import engineer_my_stations_page
from ui.pages.admin_admin import admin_admin_page
from ui.pages.admin_simulation import admin_simulation_page
from ui.pages.admin_models import admin_models_page
from ui.pages.admin_optimization import admin_optimization_page
from ui.pages.admin_anomalies import admin_anomalies_page
from ui.pages.admin_stations import admin_stations_page
from ui.pages.admin_network import admin_network_page
from ui.pages.analytics import analytics_page
from ui.pages.settings import settings_page
from ui.pages.home import home_page
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

# Disable Streamlit caching for tests


def mock_cache(func=None, **kwargs):
    if func is not None:
        return func
    return lambda f: f


patch("streamlit.cache_data", mock_cache).start()
patch("streamlit.cache_resource", mock_cache).start()

# Mock services before page imports to ensure they get the mock
mock_data = {
    "nb1": {}, "nb2": {}, "nb3": {}, "kpi": {},
    "scores": pd.DataFrame({"station_id": ["S1"], "score_criticite": [0.5], "categorie": ["Moyenne"]}),
    "decisions": pd.DataFrame({
        "station_id": ["S1"], "heure": [12], "mode_majoritaire": ["NORMAL"],
        "action_proposee": ["ECO"], "action_rl": ["ECO"],
        "economie_estimee_kwh": [2.0], "economie_rl_kwh": [10.0], "score_qos": [0.9]
    })
}

# Apply global patches to services
patch("services.data_service.load_outputs", return_value=mock_data).start()
patch("services.data_service.read_json", return_value={}).start()
patch("services.data_service.read_parquet_fast", return_value=pd.DataFrame()).start()
patch("services.data_service.full_file_digest", return_value="mock_hash").start()

# Import page functions to test


@pytest.fixture
def mock_streamlit():
    with patch("streamlit.markdown"), \
            patch("streamlit.columns", side_effect=lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]), \
            patch("streamlit.tabs", side_effect=lambda tabs: [MagicMock() for _ in tabs]), \
            patch("streamlit.sidebar", return_value=(MagicMock(), MagicMock())), \
            patch("streamlit.divider"), \
            patch("streamlit.info"), \
            patch("streamlit.warning"), \
            patch("streamlit.error"), \
            patch("streamlit.metric"), \
            patch("streamlit.plotly_chart"), \
            patch("streamlit.dataframe"), \
            patch("streamlit.button", return_value=False), \
            patch("streamlit.selectbox", return_value="S1"), \
            patch("streamlit.multiselect", return_value=[]), \
            patch("streamlit.date_input", return_value=(None, None)), \
            patch("streamlit.session_state", {"authenticated": True, "role": "admin", "display": "Admin", "user": "admin", "_session_start": 0, "data": mock_data}):
        yield


@patch("ui.pages.home.security_middleware")
def test_home_page_smoke(mock_sec, mock_streamlit):
    home_page()


@patch("ui.pages.settings.security_middleware")
def test_settings_page_smoke(mock_sec, mock_streamlit):
    settings_page()


@patch("ui.pages.analytics.security_middleware")
@patch("ui.pages.analytics.load_filtered_main_data")
def test_analytics_page_smoke(mock_load, mock_sec, mock_streamlit):
    mock_load.return_value = pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-01-01"]),
        "consommation_kwh": [100.0],
        "conso_predite": [90.0],
        "economie_rl_kwh": [10.0],
        "score_qos": [0.9],
        "type_zone": ["Urbain"],
        "technologie": ["4G"]
    })
    analytics_page()


@patch("ui.pages.admin_network.security_middleware")
@patch("ui.pages.admin_network.load_filtered_main_data")
def test_admin_network_page_smoke(mock_load, mock_sec, mock_streamlit):
    mock_load.return_value = pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-01-01"]),
        "station_id": ["S1"],
        "consommation_kwh": [100.0],
        "gouvernorat": ["Tunis"],
        "type_zone": ["Urbain"],
        "technologie": ["4G"],
        "score_criticite": [0.5],
        "categorie": ["Moyenne"],
        "anomalie_score_ensemble": [0.1],
        "score_qos": [0.9]
    })
    admin_network_page()


@patch("ui.pages.admin_stations.security_middleware")
@patch("ui.pages.admin_stations.load_filtered_main_data")
def test_admin_stations_page_smoke(mock_load, mock_sec, mock_streamlit):
    mock_load.return_value = pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-01-01"]),
        "station_id": ["S1"],
        "gouvernorat": ["Tunis"],
        "type_zone": ["Urbain"],
        "technologie": ["4G"],
        "consommation_kwh": [10.0],
        "score_qos": [0.9],
        "anomalie_score_ensemble": [0.1],
        "score_criticite": [0.5],
        "economie_rl_kwh": [1.0]
    })
    admin_stations_page()


@patch("ui.pages.admin_anomalies.security_middleware")
@patch("ui.pages.admin_anomalies.load_top_anomalies")
def test_admin_anomalies_page_smoke(mock_load, mock_sec, mock_streamlit):
    mock_load.return_value = pd.DataFrame({
        "station_id": ["S1"],
        "anomalie_score_ensemble": [0.9],
        "nb_votes_anomalie": [3],
        "timestamp": pd.to_datetime(["2024-01-01"])
    })
    admin_anomalies_page()


@patch("ui.pages.admin_optimization.security_middleware")
@patch("ui.pages.admin_optimization.load_filtered_main_data")
def test_admin_optimization_page_smoke(mock_load, mock_sec, mock_streamlit):
    mock_load.return_value = pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-01-01"]),
        "station_id": ["S1"],
        "consommation_kwh": [10.0],
        "economie_estimee_kwh": [2.0],
        "economie_rl_kwh": [3.0],
        "action_rl": ["ECO"],
        "action_proposee": ["ECO"],
        "score_qos": [0.9]
    })
    admin_optimization_page()


@patch("ui.pages.admin_models.security_middleware")
def test_admin_models_page_smoke(mock_sec, mock_streamlit):
    admin_models_page()


@patch("ui.pages.admin_simulation.security_middleware")
def test_admin_simulation_page_smoke(mock_sec, mock_streamlit):
    admin_simulation_page()


@patch("ui.pages.admin_admin.security_middleware")
@patch("ui.pages.admin_admin.db_read")
def test_admin_admin_page_smoke(mock_db, mock_sec, mock_streamlit):
    mock_db.return_value = pd.DataFrame({
        "username": ["eng1"], "role": ["engineer"], "display": ["Eng 1"], "is_active": [1],
        "email": ["eng1@tt.tn"], "created_at": ["2024-01-01"]
    })
    admin_admin_page()


@patch("ui.pages.engineer_stations.security_middleware")
@patch("ui.pages.engineer_stations.engineer_assigned_stations")
def test_engineer_stations_page_smoke(mock_assigned, mock_sec, mock_streamlit):
    mock_assigned.return_value = ["S1"]
    engineer_my_stations_page()


@patch("ui.pages.engineer_monitoring.security_middleware")
@patch("ui.pages.engineer_monitoring.load_station_data")
def test_engineer_monitoring_page_smoke(mock_load, mock_sec, mock_streamlit):
    mock_load.return_value = pd.DataFrame({
        "timestamp": pd.to_datetime([f"2024-01-01 {h:02d}:00:00" for h in range(24)]),
        "consommation_kwh": [10] * 24,
        "conso_predite": [9] * 24,
        "score_qos": [0.9] * 24,
        "anomalie_score_ensemble": [0.1] * 24
    })
    engineer_monitoring_page("S1")


@patch("ui.pages.engineer_alerts.security_middleware")
@patch("ui.pages.engineer_alerts.load_station_anomalies")
def test_engineer_alerts_page_smoke(mock_load, mock_sec, mock_streamlit):
    mock_load.return_value = pd.DataFrame({
        "station_id": ["S1"],
        "anomalie_score_ensemble": [0.9],
        "timestamp": pd.to_datetime(["2024-01-01"])
    })
    engineer_alerts_page("S1")


@patch("ui.pages.engineer_actions.security_middleware")
def test_engineer_actions_page_smoke(mock_sec, mock_streamlit):
    engineer_actions_page("S1")


@patch("ui.pages.engineer_simulation.security_middleware")
def test_engineer_simulation_page_smoke(mock_sec, mock_streamlit):
    engineer_simulation_page("S1")
