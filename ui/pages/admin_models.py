import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from pathlib import Path
from config.settings import ROOT
from security.middleware import security_middleware
from services.data_service import (
    read_json,
    read_parquet_fast,
    full_file_digest,
    artifact_path,
    load_outputs,
)
from ui.layout import header, kpi_card, section
from ui.utils import download_df_button, artifact_notebook, fix_mojibake

# Catalog of artefacts produced by NB1/NB2/NB3 used to build the provenance table.
# Keys are human-readable labels prefixed with the producing notebook so that
# `artifact_notebook(label)` correctly maps each entry to "NB1", "NB2" or "NB3".
ARTEFACTS: dict[str, str] = {
    # NB1 - Supervised consumption models
    "NB1 - resultats_modeles": "resultats_modeles.json",
    "NB1 - df_full_processed": "df_full_processed.parquet",
    # NB2 - Anomalies and station criticity
    "NB2 - resultats_anomalie": "resultats_anomalie.json",
    "NB2 - df_avec_anomalies": "df_avec_anomalies.parquet",
    "NB2 - score_stations": "score_stations.parquet",
    # NB3 - Optimization / RL
    "NB3 - rapport_optimisation": "rapport_optimisation.json",
    "NB3 - kpi_reseau": "kpi_reseau.json",
    "NB3 - streamlit_data": "streamlit_data.parquet",
    "NB3 - decisions_par_station": "decisions_par_station.parquet",
    "NB3 - streamlit_carte_stations": "streamlit_carte_stations.parquet",
}


def source_artifact_path(notebook: str, filename: str):
    if notebook in {"NB1", "NB2", "NB3"}:
        return ROOT / notebook / "output" / filename
    return None

def generated_at_for(filename: str):
    payload = read_json(artifact_path(filename)) if filename.endswith(".json") else {}
    if "generated_at" in payload:
        return payload["generated_at"]
    if "kpi_reseau" in payload and isinstance(payload["kpi_reseau"], dict):
        return payload["kpi_reseau"].get("generated_at", "")
    return ""

def provenance_table():
    rows = []
    for label, filename in ARTEFACTS.items():
        notebook = artifact_notebook(label)
        path = artifact_path(filename)
        source_path = source_artifact_path(notebook, filename)
        output_hash = full_file_digest(path) if path.exists() else ""
        source_hash = full_file_digest(source_path) if source_path and source_path.exists() else ""
        modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S") if path.exists() else ""
        rows.append(
            {
                "notebook": notebook,
                "artefact": label,
                "fichier": f"outputs/{filename}",
                "present": path.exists(),
                "taille_mb": round(path.stat().st_size / 1_000_000, 2) if path.exists() else 0,
                "modifie": modified,
                "generated_at": generated_at_for(filename),
                "source_nb": str(source_path.relative_to(ROOT)) if source_path and source_path.exists() else "",
                "hash_outputs": output_hash,
                "hash_source": source_hash,
                "hash_match": bool(output_hash and source_hash and output_hash == source_hash),
            }
        )
    return pd.DataFrame(rows)

def data_quality_table():
    import numpy as np
    rows = []
    checks = [
        ("streamlit_data", artifact_path("streamlit_data.parquet"), ["timestamp", "station_id", "consommation_kwh", "conso_predite", "anomalie_score_ensemble", "mode_operation", "action_rl"]),
        ("df_avec_anomalies", artifact_path("df_avec_anomalies.parquet"), ["timestamp", "station_id", "conso_predite", "anomalie_score_ensemble", "nb_votes_anomalie"]),
        ("score_stations", artifact_path("score_stations.parquet"), ["station_id", "score_criticite", "categorie"]),
        ("decisions_par_station", artifact_path("decisions_par_station.parquet"), ["station_id", "heure", "action_rl", "economie_rl_kwh"]),
        ("streamlit_carte_stations", artifact_path("streamlit_carte_stations.parquet"), ["station_id", "latitude", "longitude"]),
    ]
    for name, path, required in checks:
        if not path.exists():
            rows.append({"dataset": name, "statut": "manquant", "lignes": 0, "colonnes": 0, "manquantes": ", ".join(required), "date_min": "", "date_max": "", "stations": 0, "nulls_critiques_pct": np.nan})
            continue
        df = read_parquet_fast(path, None)
        missing = [col for col in required if col not in df.columns]
        critical = [col for col in required if col in df.columns]
        null_pct = df[critical].isna().mean().mean() * 100 if critical else np.nan
        date_min = ""
        date_max = ""
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], errors="coerce").dropna()
            if not ts.empty:
                date_min = str(ts.min())
                date_max = str(ts.max())
        rows.append(
            {
                "dataset": name,
                "statut": "ok" if not missing and (pd.isna(null_pct) or null_pct < 1) else "a verifier",
                "lignes": len(df),
                "colonnes": df.shape[1],
                "manquantes": ", ".join(missing),
                "date_min": date_min,
                "date_max": date_max,
                "stations": df["station_id"].nunique() if "station_id" in df.columns else 0,
                "nulls_critiques_pct": round(float(null_pct), 3) if not pd.isna(null_pct) else np.nan,
            }
        )
    return pd.DataFrame(rows)

def admin_models_page():
    security_middleware.enforce()
    header("Modeles et provenance", "Performances, artefacts et origine NB1/NB2/NB3")
    
    outputs = load_outputs()
    nb1 = outputs.get("nb1", {})
    nb2 = outputs.get("nb2", {})
    nb3 = outputs.get("nb3", {})
    
    tab_perf, tab_sources, tab_quality, tab_flow = st.tabs(["Performances", "Artefacts", "Qualite donnees", "Flux"])
    
    with tab_perf:
        if nb1:
            section("NB1")
            df_models = pd.DataFrame.from_dict(nb1, orient="index").reset_index(names="modele")
            st.dataframe(df_models.sort_values("r2", ascending=False), width="stretch", hide_index=True)
        if nb2:
            section("NB2")
            st.dataframe(pd.DataFrame.from_dict(nb2, orient="index").reset_index(names="modele"), width="stretch", hide_index=True)
        if nb3.get("rl_resultats_tous_agents"):
            section("NB3")
            st.dataframe(pd.DataFrame.from_dict(nb3["rl_resultats_tous_agents"], orient="index").reset_index(names="agent"), width="stretch", hide_index=True)
            
    with tab_sources:
        provenance = provenance_table()
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("NB1", str((provenance["notebook"] == "NB1").sum()), "artefacts supervises")
        with c2:
            kpi_card("NB2", str((provenance["notebook"] == "NB2").sum()), "artefacts anomalies")
        with c3:
            kpi_card("NB3", str((provenance["notebook"] == "NB3").sum()), "artefacts optimisation")
        st.dataframe(provenance, width="stretch", hide_index=True)
        download_df_button(provenance, "provenance_nb1_nb2_nb3.csv", "Exporter provenance")
        
    with tab_quality:
        quality = data_quality_table()
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Datasets", str(len(quality)), "controles")
        with c2:
            kpi_card("OK", str(int((quality["statut"] == "ok").sum())), "qualite")
        with c3:
            kpi_card("A verifier", str(int((quality["statut"] != "ok").sum())), "qualite", "orange" if int((quality["statut"] != "ok").sum()) else "green")
        st.dataframe(quality, width="stretch", hide_index=True)
        download_df_button(quality, "qualite_donnees_outputs.csv", "Exporter qualite")
        
    with tab_flow:
        st.dataframe(
            pd.DataFrame(
                [
                    {"bloc": "NB1", "donnees": "Prediction consommation", "fichiers": "df_full_processed, resultats_modeles, modeles joblib"},
                    {"bloc": "NB2", "donnees": "Anomalies et criticite", "fichiers": "df_avec_anomalies, score_stations, resultats_anomalie"},
                    {"bloc": "NB3", "donnees": "Optimisation et RL", "fichiers": "streamlit_data, decisions_par_station, kpi_reseau, rapport_optimisation"},
                    {"bloc": "Dashboard", "donnees": "Lecture outputs et decisions humaines", "fichiers": "app.py, dashboard_ops.sqlite3"},
                ]
            ),
            width="stretch",
            hide_index=True,
        )
