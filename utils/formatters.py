"""Formatting helpers for metrics and text."""

from __future__ import annotations

from typing import Any
import numpy as np

def metric_value(value: Any, unit: str = "", decimals: int = 1) -> str:
    """Format a metric value for display."""
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "N/D"
        if isinstance(value, (int, float, np.number)):
            formatted = f"{value:.{decimals}f}"
            return f"{formatted} {unit}".strip()
        return f"{value} {unit}".strip()
    except Exception:
        return str(value)

def fix_text_encoding(text: str) -> str:
    """Fix potential mojibake in strings."""
    if not isinstance(text, str):
        return str(text)
    if any(token in text for token in ("Ãƒ", "Ã¢", "ÃŽ")):
        try:
            return text.encode("latin1").decode("utf-8")
        except UnicodeError:
            pass
    return text
