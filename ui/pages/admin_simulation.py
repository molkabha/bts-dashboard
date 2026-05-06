import streamlit as st
import pandas as pd
from datetime import datetime, time
from security.middleware import security_middleware
from services.data_service import (
    active_dataset_info,
    available_stations,
    load_simulation_base,
    log_event,
    db_execute,
)
from services.realtime_generator import generate_realtime_dataset
from config.settings import ROOT, settings
OUTPUTS = settings.OUTPUTS_DIR
ACTIVE_UPLOAD_DATASET = settings.ACTIVE_UPLOAD_DATASET
from ui.layout import header, kpi_card, section
from ui.realtime_api import render_api_response
from ui.utils import download_df_button
from services.pipeline_service import simulate_nb_pipeline as run_nb_pipeline
from services.data_service import load_outputs

def read_uploaded(uploaded) -> pd.DataFrame:
    name = str(getattr(uploaded, "name", "")).lower()
    size = getattr(uploaded, "size", 0) or 0
    if size > 250 * 1024 * 1024:
        raise ValueError("Fichier trop volumineux.")
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded)
        elif name.endswith(".parquet"):
            df = pd.read_parquet(uploaded, columns=None)
        else:
            raise ValueError("Format non supporte.")
    except Exception as exc:
        raise ValueError(f"Lecture du fichier impossible: {exc}") from exc
    if df.empty:
        raise ValueError("Dataset vide.")
    if len(df.columns) > 250:
        raise ValueError("Dataset refuse: trop de colonnes.")
    return df

def dataset_overview(df: pd.DataFrame, title: str = "Vue globale dataset") -> None:
    if df.empty:
        st.warning("Dataset vide.")
        return
    section(title)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("Lignes", f"{len(df):,}", "dataset")
    with c2:
        kpi_card("Colonnes", f"{df.shape[1]:,}", "schema")
    with c3:
        stations = df["station_id"].nunique() if "station_id" in df.columns else 0
        kpi_card("Stations", f"{stations:,}", "station_id")
    with c4:
        missing_pct = df.isna().mean().mean() * 100 if df.shape[1] else 0
        kpi_card("Valeurs nulles", f"{missing_pct:.2f}%", "moyenne")
    with c5:
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], errors="coerce").dropna()
            period = f"{ts.min().date()} - {ts.max().date()}" if not ts.empty else "N/D"
        else:
            period = "N/D"
        kpi_card("Periode", period, "timestamp")

def process_dataset(df_in: pd.DataFrame, source: str = "notebook_outputs"):
    outputs = st.session_state.get("data", load_outputs())
    return run_nb_pipeline(df_in, source=source, decisions=outputs.get("decisions"))

def publish_admin_dataset(df: pd.DataFrame, source_name: str) -> tuple[bool, str]:
    if df.empty:
        return False, "Dataset vide."
    if "station_id" not in df.columns:
        return False, "Publication impossible: colonne station_id manquante."
    OUTPUTS.mkdir(exist_ok=True, parents=True)
    published = process_dataset(df, source="import_admin_publie")
    target = OUTPUTS / ACTIVE_UPLOAD_DATASET
    published.to_parquet(target, index=False)
    rel_path = str(target.relative_to(ROOT))
    now = datetime.now().isoformat(timespec="seconds")
    db_execute("upsert_setting", ("active_dataset_path", rel_path))
    db_execute("upsert_setting", ("active_dataset_name", source_name))
    db_execute("upsert_setting", ("active_dataset_published_at", now))
    st.cache_data.clear()
    st.session_state.pop("data", None)
    log_event("admin_dataset_published", {"file": source_name, "path": rel_path, "rows": len(published)})
    return True, f"Nouveau dataset actif publie: {len(published):,} lignes."


def selected_start_time(prefix: str) -> datetime:
    use_now = st.checkbox("Utiliser l'heure actuelle", value=True, key=f"{prefix}_now")
    if use_now:
        return datetime.now().replace(second=0, microsecond=0)
    c1, c2 = st.columns(2)
    with c1:
        day = st.date_input("Date de debut", value=datetime.now().date(), key=f"{prefix}_date")
    with c2:
        hour = st.time_input("Heure de debut", value=time(datetime.now().hour, 0), key=f"{prefix}_time")
    return datetime.combine(day, hour).replace(second=0, microsecond=0)


def realtime_admin_dataset_tab():
    section("API temps reel reseau")
    stations = available_stations()
    if not stations:
        st.warning("Aucune station disponible pour generer un flux.")
        return
    scope = st.radio("Perimetre", ["Une station", "Plusieurs stations", "Toutes les stations"], horizontal=True)
    if scope == "Une station":
        selected = [st.selectbox("Station", stations)]
    elif scope == "Plusieurs stations":
        selected = st.multiselect("Stations", stations, default=stations[: min(5, len(stations))])
    else:
        selected = stations
    if not selected:
        st.warning("Selectionnez au moins une station.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        periods = st.number_input("Points par station", 1, 10080, 1, 1)
    with c2:
        freq_minutes = st.selectbox("Frequence", [5, 10, 15, 30, 60], index=0, format_func=lambda v: f"{v} min")
    with c3:
        anomaly_rate = st.slider("Taux anomalies", 0.0, 0.40, 0.08, 0.01)
    start_time = selected_start_time("admin_rt")

    if st.button("Appeler API temps reel", type="primary"):
        with st.spinner("Capture temps reel..."):
            generated = generate_realtime_dataset(
                selected,
                periods=int(periods),
                anomaly_rate=float(anomaly_rate),
                seed=42,
                start_time=start_time,
                freq_minutes=int(freq_minutes),
            )
            result = process_dataset(generated, source="flux_temps_reel_genere")
            st.session_state["admin_realtime_dataset"] = result

    result = st.session_state.get("admin_realtime_dataset")
    if isinstance(result, pd.DataFrame) and not result.empty:
        render_api_response(result, station=selected[0] if len(selected) == 1 else None)
        dataset_overview(result, "Dataset recu")
        st.dataframe(result.head(1000), width="stretch", hide_index=True)
        download_df_button(result, "dataset_temps_reel.csv")
        if st.button("Publier ce dataset temps reel comme dataset actif", type="primary"):
            ok, message = publish_admin_dataset(result, "dataset_temps_reel_genere")
            st.success(message) if ok else st.error(message)

def admin_simulation_page():
    security_middleware.enforce()
    header("Dataset reseau", "Import reel, generation temps reel et analyse reseau")
    info = active_dataset_info()
    if info:
        st.info(f"Dataset actif: {info.get('name')} {info.get('published_at', '')}")

    tab_upload, tab_realtime, tab_analysis = st.tabs(["Publier dataset", "Temps reel genere", "Analyse"])

    with tab_upload:
        uploaded = st.file_uploader("Dataset complet CSV ou Parquet", type=["csv", "parquet"])
        if uploaded is not None:
            try:
                df_source = read_uploaded(uploaded)
                st.info(f"Dataset charge: {len(df_source):,} lignes.")
                dataset_overview(df_source, "Vue globale du dataset charge")
                if st.button("Publier comme nouveau dataset actif", type="primary"):
                    with st.spinner("Publication du vrai dataset actif..."):
                        ok, message = publish_admin_dataset(df_source, uploaded.name)
                    st.success(message) if ok else st.error(message)
            except Exception as e:
                st.error(str(e))

    with tab_realtime:
        realtime_admin_dataset_tab()

    with tab_analysis:
        if st.button("Analyser le dataset courant", type="primary"):
            with st.spinner("Analyse..."):
                result = process_dataset(load_simulation_base(50000), source="notebook_outputs")
            if not result.empty:
                st.session_state["admin_sim_result"] = result

        result = st.session_state.get("admin_sim_result")
        if isinstance(result, pd.DataFrame) and not result.empty:
            section("Resultat analyse")
            st.dataframe(result.head(1000), width="stretch", hide_index=True)
            download_df_button(result, "analyse_reseau.csv")
