"""Tests for UI formatting helpers."""

from __future__ import annotations

import pandas as pd

from ui.formatting import format_action_label, resolve_row_action, row_has_no_named_action


def test_format_action_label_snake_case():
    assert format_action_label("sleep_mode_secteur") == "Veille secteur"


def test_resolve_row_action_prefers_rl():
    row = pd.Series(
        {
            "action_rl": "free_cooling",
            "action_proposee": "reduction_puissance",
        },
    )
    assert resolve_row_action(row, prefer_rl=True) == "Free cooling"


def test_row_has_no_named_action():
    row = pd.Series({"action_proposee": "aucune_action"})
    assert row_has_no_named_action(row) is True
