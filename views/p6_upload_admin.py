"""Page 6 - Upload Dataset (Admin uniquement)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from security.middleware import security_middleware
from services.data_service import (
    active_dataset_info, db_execute, log_event,
)
from services.dataset_publish import PublishDatasetError, prepare_published_dataset
from services.data_service import enrich_dashboard_data, load_filtered_main_data
from config.settings import ROOT, settings
from ui.components import header, kpi_card, section
from ui.utils import download_df_button

OUTPUTS = settings.OUTPUTS_DIR
ACTIVE_UPLOAD_DATASET = settings.ACTIVE_UPLOAD_DATASET

REQUIRED_COLUMNS = [
    "timestamp", "station_id", "consommation_kwh", "heure", "mois",
    "technologie", "gouvernorat", "type_zone", "latitude", "longitude",
    "charge_cpu_pct", "score_qos", "taux_charge_voix", "taux_charge_data",
]


def _read_uploaded(uploaded) -> pd.DataFrame:
    name = str(getattr(uploaded, "name", "")).lower()
    size = getattr(uploaded, "size", 0) or 0
    if size > 250 * 1024 * 1024:
        raise ValueError("Fichier trop volumineux (max 250 Mo).")
    if name.endswith(".csv"):
        return pd.read_csv(uploaded)
    elif name.endswith(".parquet"):
        return pd.read_parquet(uploaded)
    raise ValueError("Format non supporte. Utilisez CSV ou Parquet.")


def _validate_schema(df: pd.DataFrame) -> list[dict]:
    """Validate columns and return list of {col, status, message}."""
    results = []
    for col in REQUIRED_COLUMNS:
        if col in df.columns:
            results.append({"Colonne": col, "Statut": "Presente", "Note": ""})
        else:
            results.append({"Colonne": col, "Statut": "ABSENTE",
                            "Note": f"Le modele utilisera une valeur de substitution (impact estime : -1 a 3% de precision)"})
    return results


def _publish_dataset(df: pd.DataFrame, source_name: str) -> tuple[bool, str]:
    if df.empty:
        return False, "Dataset vide."
    if "station_id" not in df.columns:
        return False, "Colonne station_id manquante."
    OUTPUTS.mkdir(exist_ok=True, parents=True)
    try:
        processed = prepare_published_dataset(df)
    except PublishDatasetError as exc:
        return False, str(exc)
    target = OUTPUTS / ACTIVE_UPLOAD_DATASET
    processed.to_parquet(target, index=False)
    rel = str(target.relative_to(ROOT))
    now = datetime.now().isoformat(timespec="seconds")
    db_execute("upsert_setting", ("active_dataset_path", rel))
    db_execute("upsert_setting", ("active_dataset_name", source_name))
    db_execute("upsert_setting", ("active_dataset_published_at", now))
    st.cache_data.clear()
    st.session_state.pop("data", None)
    log_event("admin_dataset_published", {"file": source_name, "rows": len(processed)})
    return True, (
        f"Dataset publie : {len(processed):,} lignes enrichies uniquement depuis les artefacts "
        "NB1/NB2/NB3 (simulation dashboard desactivee)."
    )


def page_upload_admin():
    security_middleware.enforce(role="admin")
    header("Import / dataset", "Importer un dataset et le publier dans tout le dashboard")
    info = active_dataset_info()
    if info:
        st.info(f"Dataset actif : {info.get('name', 'Standard')} ({info.get('published_at', '')})")

    # Section 1 - Upload
    with section("Importer et Publier"):
        uploaded = st.file_uploader("Glisser-deposer un fichier CSV ou Parquet", type=["csv", "parquet"],
                                    key="upload_dataset")
        if uploaded is not None:
            try:
                df_source = _read_uploaded(uploaded)
            except Exception as e:
                st.error(str(e))
                return

            # Schema validation
            validation = _validate_schema(df_source)
            val_df = pd.DataFrame(validation)
            with st.expander("Schema attendu et impact des colonnes manquantes", expanded=False):
                st.dataframe(val_df, width="stretch", hide_index=True)

            missing_critical = [v["Colonne"] for v in validation
                                if v["Statut"] == "ABSENTE" and v["Colonne"] in ("station_id", "consommation_kwh")]
            if missing_critical:
                st.error(f"Colonnes critiques absentes : {', '.join(missing_critical)}. Import impossible.")
                return

            # Preview
            with st.expander("Apercu du fichier source", expanded=False):
                st.dataframe(df_source.head(10), width="stretch", hide_index=True)

            c1, c2, c3 = st.columns(3)
            with c1:
                kpi_card("Lignes", f"{len(df_source):,}", "dataset")
            with c2:
                stations_n = df_source["station_id"].nunique() if "station_id" in df_source.columns else 0
                kpi_card("Stations", str(stations_n), "uniques")
            with c3:
                missing_pct = df_source.isna().mean().mean() * 100
                kpi_card("Valeurs manquantes", f"{missing_pct:.1f}%", "moyenne")

            st.info(
                "A la publication, ce fichier devient la source active. Les colonnes NB1/NB2/NB3 "
                "doivent provenir des notebooks (parquets/JSON). Le recalcul local est bloque si un artefact manque."
            )

            if st.button("Publier avec artefacts NB", type="primary", width="stretch"):
                with st.spinner("Publication en cours..."):
                    ok, msg = _publish_dataset(df_source, uploaded.name)
                if ok:
                    st.success(msg)
                    st.info("Les filtres, cartes, alertes, predictions et optimisations utilisent maintenant ce dataset.")
                else:
                    st.error(msg)

    # Section 2 - Pipeline rerun
    with st.expander("Relance avancee du pipeline", expanded=False):
        st.warning(
            "Re-enrichit l'echantillon actif depuis les parquets/JSON NB uniquement. "
            "Echec si une colonne notebook reste vide apres fusion."
        )
        if st.button("Re-enrichir depuis artefacts NB", type="primary"):
            progress = st.progress(0)
            status = st.empty()

            status.markdown("Chargement streamlit_data / dataset actif...")
            progress.progress(25)
            base = load_filtered_main_data(list(dict.fromkeys(REQUIRED_COLUMNS + [
                "conso_predite", "anomalie_score_ensemble", "mode_operation",
                "economie_estimee_kwh", "economie_rl_kwh", "action_proposee",
            ]))).head(50000)

            status.markdown("Fusion artefacts NB1/NB2/NB3...")
            progress.progress(60)
            try:
                result = prepare_published_dataset(base) if not base.empty else base
            except PublishDatasetError as exc:
                progress.progress(100)
                status.markdown("Enrichissement refuse.")
                st.error(str(exc))
                return

            status.markdown("Finalisation...")
            progress.progress(90)
            st.session_state["pipeline_result"] = result

            progress.progress(100)
            status.markdown("Enrichissement termine.")
            st.success(f"Echantillon traite : {len(result):,} lignes (100 % artefacts notebook).")

    # Section 3 - Pipeline result
    result = st.session_state.get("pipeline_result")
    if isinstance(result, pd.DataFrame) and not result.empty:
        with st.expander("Resultat du Pipeline", expanded=False):
            st.dataframe(result.head(500), width="stretch", hide_index=True)
            download_df_button(result, "pipeline_result.csv", "Exporter resultat")
