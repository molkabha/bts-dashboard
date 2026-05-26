"""Smoke tests: imports and dashboard wiring without launching Streamlit."""

from __future__ import annotations

import importlib

import pytest


def test_import_core_services():
    for module in (
        "services.nb_metrics",
        "services.decision_service",
        "services.data_service",
        "services.optimization_service",
        "config.settings",
    ):
        importlib.import_module(module)


def test_page_functions_registry():
    from ui.dashboard import ADMIN_ONLY_PAGE_INDICES, ENGINEER_PAGE_INDICES, PAGE_FUNCTIONS
    from ui.display import ADMIN_PAGE_LABELS, ENGINEER_PAGE_LABELS

    assert len(ADMIN_PAGE_LABELS) == 7
    assert len(ENGINEER_PAGE_LABELS) == 6
    assert "Configuration" in ADMIN_PAGE_LABELS
    assert "Configuration" not in ENGINEER_PAGE_LABELS

    assert PAGE_FUNCTIONS[0].__name__ == "page_accueil"
    assert PAGE_FUNCTIONS[12].__name__ == "page_configuration"
    assert PAGE_FUNCTIONS[14].__name__ == "page_optimisation_rl"
    assert ADMIN_ONLY_PAGE_INDICES == {12}
    assert 6 in ENGINEER_PAGE_INDICES
    assert 12 not in ENGINEER_PAGE_INDICES


def test_settings_production_secret_guard():
    from config.settings import Settings

    with pytest.raises(ValueError):
        Settings(ENVIRONMENT="production", SECRET_KEY="temporary-secret-key-for-dev")
