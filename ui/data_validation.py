from __future__ import annotations

import pandas as pd

import streamlit as st

from services.nb_metrics import blank_mask


def format_nb2_seuil_alert() -> str:

    from services.data_service import diagnose_nb2_seuil

    d = diagnose_nb2_seuil()

    seuil, source = d.get("resolved") or (None, None)

    if seuil is not None:

        return ""

    lines = [
        "**Seuil d'anomalie indisponible** — le dashboard ne trouve aucune source NB valide."
    ]

    if not d.get("json_exists"):

        lines.append(
            "- `resultats_anomalie.json` : fichier absent localement (téléchargement Hugging Face échoué ou dossier `VF/NB2/output` vide)."
        )

    elif d.get("json_loaded") and (not d.get("json_has_seuil_ensemble")):

        keys = ", ".join(d.get("json_detector_keys") or []) or "—"

        lines.append(
            f"- `resultats_anomalie.json` : présent mais **sans** `seuil_ensemble` (détecteurs : {keys})."
        )

    if not d.get("parquet_exists"):

        lines.append(
            "- `df_avec_anomalies.parquet` : absent — impossible de déduire le seuil depuis les scores."
        )

    elif d.get("parquet_derived_seuil") is None:

        lines.append(
            "- Parquet présent mais dérivation du seuil impossible (scores vides ou `pct_anomalies` manquant dans `kpi_reseau.json`)."
        )

    lines.append(
        "Actions : copier les artefacts Hub dans `VF/NB2/output`, corriger le SSL Python, ou ajouter `seuil_ensemble` dans l'export JSON du notebook NB2."
    )

    return "\n".join(lines)


MSG_ANOM_COL = "Scores d'anomalie indisponibles : colonne `anomalie_score_ensemble` absente ou vide sur la période filtrée (export `df_avec_anomalies.parquet` requis)."

MSG_QOS_COL = "Indicateur QoS indisponible : colonne `score_qos` absente ou vide sur la période filtrée."

MSG_QOS_SEUIL = "Seuil QoS indisponible : export NB3 `rapport_optimisation.json` avec `seuils_decision.qos` (ou `kpi_reseau.json`) requis."


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

        st.warning(format_nb2_seuil_alert())

        return None

    try:

        return float(raw)

    except (TypeError, ValueError):

        st.warning(format_nb2_seuil_alert())

        return None


def qos_seuil_or_warn() -> float:

    from config.settings import settings
    from services.data_service import resolve_qos_seuil

    seuil, _source = resolve_qos_seuil()

    if seuil is not None:

        return seuil

    return float(settings.QOS_SEUIL_DEFAULT)
