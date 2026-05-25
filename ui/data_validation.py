"""Alertes UI lorsque des sorties notebook requises sont absentes (pas de valeurs par défaut)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.nb_metrics import blank_mask

MSG_NB2_SEUIL = (
    "Seuil d'anomalie indisponible : export NB2 `resultats_anomalie.json` "
    "introuvable ou sans clé `seuil_ensemble`."
)
MSG_ANOM_COL = (
    "Scores d'anomalie indisponibles : colonne `anomalie_score_ensemble` absente "
    "ou vide sur la période filtrée (export `df_avec_anomalies.parquet` requis)."
)
MSG_QOS_COL = (
    "Indicateur QoS indisponible : colonne `score_qos` absente ou vide "
    "sur la période filtrée."
)
MSG_QOS_SEUIL = (
    "Seuil QoS indisponible : export NB3 `rapport_optimisation.json` "
    "avec `seuils_decision.qos` (ou `kpi_reseau.json`) requis."
)


def column_has_values(df: pd.DataFrame, column: str) -> bool:
    if df.empty or column not in df.columns:
        return False
    return bool((~blank_mask(df[column])).any())


def require_column_or_warn(df: pd.DataFrame, column: str, message: str) -> bool:
    if column_has_values(df, column):
        return True
    st.warning(message)
    return False


def nb2_seuil_or_warn(nb2_stats: dict | None = None) -> float | None:
    if nb2_stats is None:
        from services.data_service import load_nb2_network_stats

        nb2_stats = load_nb2_network_stats()
    raw = nb2_stats.get("seuil_ensemble")
    if raw is None:
        st.warning(MSG_NB2_SEUIL)
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        st.warning(MSG_NB2_SEUIL)
        return None


def qos_seuil_or_warn() -> float | None:
    from services.data_service import resolve_qos_seuil

    seuil, _source = resolve_qos_seuil()
    if seuil is None:
        st.warning(MSG_QOS_SEUIL)
        return None
    return seuil
