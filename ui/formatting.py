"""Affichage sans None / NaN — valeurs calculees depuis le dataframe filtre."""

from __future__ import annotations

from typing import Any

import pandas as pd


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "none", "nan", "<na>"}:
        return True
    return False


def display_text(value: Any, default: str = "—") -> str:
    if is_missing(value):
        return default
    return str(value).strip()


# Codes d'action exportes par le notebook NB3 (snake_case).
ACTION_LABELS_FR: dict[str, str] = {
    "aucune_action": "Aucune action",
    "aucune action": "Aucune action",
    "maintien": "Maintien",
    "maintien_conso": "Maintien de la consommation",
    "reduction_puissance": "Réduction de puissance",
    "reduire_puissance": "Réduire la puissance",
    "couper_porteur": "Couper un porteur",
    "mode_eco": "Passage mode ECO",
    "mode_eco_force": "Forcer mode ECO",
    "alerte_qos": "Alerte QoS",
    "intervention": "Intervention terrain",
}


def format_action_label(value: Any, default: str = "—") -> str:
    """Libelle FR pour les actions NB3 (ex. aucune_action → Aucune action)."""
    if is_missing(value):
        return default
    raw = str(value).strip()
    key = raw.lower().replace(" ", "_")
    if key in ACTION_LABELS_FR:
        return ACTION_LABELS_FR[key]
    return raw.replace("_", " ").strip().capitalize()


def is_no_named_action(value: Any) -> bool:
    if is_missing(value):
        return False
    key = str(value).strip().lower().replace(" ", "_")
    return key in {"aucune_action", "aucune", "none", "rien"}


def row_has_no_named_action(row: Any) -> bool:
    for col in ("action_proposee", "action_rl", "action_principale"):
        try:
            if is_no_named_action(row.get(col) if hasattr(row, "get") else None):
                return True
        except Exception:
            continue
    return False


def resolve_row_action(row: Any, *, prefer_rl: bool = True, default: str = "—") -> str:
    """Choisit la meilleure colonne d'action disponible sur une ligne enrichie NB3."""
    order = (
        ("action_rl", "action_proposee", "action_principale")
        if prefer_rl
        else ("action_proposee", "action_principale", "action_rl")
    )
    for col in order:
        try:
            val = row.get(col) if hasattr(row, "get") else None
        except Exception:
            val = None
        if not is_missing(val):
            return format_action_label(val, default=default)
    return default


def display_number(
    value: Any,
    *,
    decimals: int = 0,
    suffix: str = "",
    default: str = "—",
) -> str:
    if is_missing(value):
        return default
    try:
        num = float(value)
        if pd.isna(num):
            return default
    except (TypeError, ValueError):
        return default
    if decimals <= 0:
        return f"{num:,.0f}{suffix}"
    return f"{num:,.{decimals}f}{suffix}"


def display_percent(value: Any, decimals: int = 1, default: str = "—") -> str:
    text = display_number(value, decimals=decimals, suffix="%", default=default)
    return text


def sanitize_kpi_value(value: Any, default: str = "—") -> str:
    """Pour kpi_card : jamais la chaine 'None'."""
    if is_missing(value):
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if pd.isna(float(value)):
            return default
        if float(value) == int(value):
            return f"{int(value):,}"
        return f"{float(value):,.2f}"
    text = str(value).strip()
    if text.lower() in {"none", "nan", "<na>"}:
        return default
    return text


def format_dataframe_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce").round(4)
        else:
            out[col] = out[col].astype(object).where(out[col].notna(), "")
            out[col] = out[col].astype(str).replace({"None": "", "nan": "", "<NA>": ""})
    return out
