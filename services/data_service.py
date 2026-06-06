from __future__ import annotations

import hashlib

import json

import sqlite3

import threading

import time

from datetime import datetime

from functools import lru_cache

from pathlib import Path

from typing import Any, Optional

import pandas as pd

import streamlit as st

from config.settings import ROOT, settings

from services.nb_metrics import (
    harmonize_nb3_economies,
    merge_business_columns,
    nb3_export_economie_kwh,
)

try:

    import pyarrow.parquet as pq

except ImportError:

    pq = None

try:

    from huggingface_hub import hf_hub_download

except ImportError:

    hf_hub_download = None

_HF_DISABLED_UNTIL = 0.0

_ARTIFACT_HIT_CACHE: dict[str, Path] = {}


def hf_hub_token() -> str | None:

    token = settings.HF_TOKEN

    if token:

        return str(token).strip() or None

    import os

    env = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")

    if env:

        return str(env).strip() or None

    try:

        if hasattr(st, "secrets"):

            direct = st.secrets.get("HF_TOKEN")

            if direct:

                return str(direct).strip() or None

            hub = st.secrets.get("huggingface")

            if isinstance(hub, dict) and hub.get("token"):

                return str(hub["token"]).strip() or None

    except Exception:

        pass

    return None


def artifact_is_ready(path: Path, min_bytes: int = 64) -> bool:

    try:

        return path.is_file() and path.stat().st_size >= min_bytes

    except OSError:

        return False


NOTEBOOK_OUTPUTS = {
    "NB1": settings.NB1_OUTPUT,
    "NB2": settings.NB2_OUTPUT,
    "NB3": settings.NB3_OUTPUT,
}


def resolve_cached_artifact(filename: str) -> Path | None:

    candidates = [settings.OUTPUTS_DIR / filename]

    for base in NOTEBOOK_OUTPUTS.values():

        candidates.append(base / filename)

    for path in candidates:

        if artifact_is_ready(path):

            return path

    if not settings.USE_HF_HUB or hf_hub_download is None:

        return None

    for hf_name in (filename, f"streamlit_{filename}"):

        try:

            downloaded = hf_hub_download(
                repo_id=settings.HF_REPO_ID,
                filename=hf_name,
                cache_dir=str(settings.HF_CACHE_DIR),
                local_files_only=True,
            )

            path = Path(downloaded)

            if artifact_is_ready(path):

                return path

        except Exception:

            continue

    return None


ARTIFACT_REGISTRY: dict[str, dict[str, str]] = {
    "agents_rl_7.pkl": {
        "notebook": "NB3",
        "type": "modele",
        "usage": "Agents RL entraines",
    },
    "autoencoder.keras": {
        "notebook": "NB2",
        "type": "modele",
        "usage": "Autoencoder anomalies",
    },
    "best_model.joblib": {
        "notebook": "NB1",
        "type": "modele",
        "usage": "Meilleur modele prediction",
    },
    "config.joblib": {
        "notebook": "NB1",
        "type": "modele",
        "usage": "Configuration preprocessing NB1",
    },
    "data_cleaning_avant_apres.png": {
        "notebook": "NB1",
        "type": "image",
        "usage": "Qualite donnees avant/apres",
    },
    "dc1_synthese_anomalies.png": {
        "notebook": "NB1",
        "type": "image",
        "usage": "Synthese anomalies preliminaires",
    },
    "decisions_par_station.parquet": {
        "notebook": "NB3",
        "type": "table",
        "usage": "Decisions station x heure",
    },
    "df_avec_anomalies.parquet": {
        "notebook": "NB2",
        "type": "table",
        "usage": "Dataset enrichi anomalies",
    },
    "df_full_processed.parquet": {
        "notebook": "NB1",
        "type": "table",
        "usage": "Dataset complet prepare NB1",
    },
    "df_test_processed.parquet": {
        "notebook": "NB1",
        "type": "table",
        "usage": "Split test prepare NB1",
    },
    "df_train_processed.parquet": {
        "notebook": "NB1",
        "type": "table",
        "usage": "Split train prepare NB1",
    },
    "eda_correlations.png": {
        "notebook": "NB1",
        "type": "image",
        "usage": "Correlations EDA",
    },
    "encodeurs.joblib": {
        "notebook": "NB1",
        "type": "modele",
        "usage": "Encodeurs categoriels",
    },
    "kpi_reseau.json": {
        "notebook": "NB3",
        "type": "json",
        "usage": "KPI reseau finaux",
    },
    "modele_lgbm.joblib": {
        "notebook": "NB1",
        "type": "modele",
        "usage": "Modele LightGBM",
    },
    "modele_stacking.joblib": {
        "notebook": "NB1",
        "type": "modele",
        "usage": "Modele stacking",
    },
    "modeles_anomalie.joblib": {
        "notebook": "NB2",
        "type": "modele",
        "usage": "Modeles detection anomalies",
    },
    "performance_qualitative_modeles.csv": {
        "notebook": "NB2",
        "type": "table",
        "usage": "Performance qualitative detecteurs",
    },
    "pipeline_inference.joblib": {
        "notebook": "NB3",
        "type": "modele",
        "usage": "Pipeline inference complet",
    },
    "precision_recall_modeles.png": {
        "notebook": "NB2",
        "type": "image",
        "usage": "Precision/recall detecteurs",
    },
    "quantile_models.joblib": {
        "notebook": "NB1",
        "type": "modele",
        "usage": "Modeles quantiles Q10/Q90",
    },
    "rapport_optimisation.json": {
        "notebook": "NB3",
        "type": "json",
        "usage": "Rapport optimisation",
    },
    "resultats_anomalie.json": {
        "notebook": "NB2",
        "type": "json",
        "usage": "Resultats detecteurs NB2",
    },
    "resultats_modeles.json": {
        "notebook": "NB1",
        "type": "json",
        "usage": "Resultats modeles NB1",
    },
    "rl_7agents_apprentissage.png": {
        "notebook": "NB3",
        "type": "image",
        "usage": "Apprentissage 7 agents RL",
    },
    "score_stations.parquet": {
        "notebook": "NB2",
        "type": "table",
        "usage": "Score station NB2",
    },
    "shap_bar.png": {"notebook": "NB1", "type": "image", "usage": "SHAP bar"},
    "shap_beeswarm.png": {"notebook": "NB1", "type": "image", "usage": "SHAP beeswarm"},
    "shap_waterfall.png": {
        "notebook": "NB1",
        "type": "image",
        "usage": "SHAP waterfall",
    },
    "streamlit_carte_stations.parquet": {
        "notebook": "NB3",
        "type": "table",
        "usage": "Carte stations pre-calculee",
    },
    "streamlit_data.parquet": {
        "notebook": "NB3",
        "type": "table",
        "usage": "Dataset principal Streamlit",
    },
    "streamlit_profil_horaire.parquet": {
        "notebook": "NB3",
        "type": "table",
        "usage": "Profil horaire pre-calcule",
    },
    "streamlit_score_stations.parquet": {
        "notebook": "NB3",
        "type": "table",
        "usage": "Scores stations Streamlit",
    },
    "streamlit_timeseries.parquet": {
        "notebook": "NB3",
        "type": "table",
        "usage": "Series temporelles pre-calculees",
    },
    "tableau_de_bord_complet.png": {
        "notebook": "NB3",
        "type": "image",
        "usage": "Tableau de bord notebook",
    },
    "tsne_anomalies.png": {
        "notebook": "NB2",
        "type": "image",
        "usage": "Projection t-SNE anomalies",
    },
}

COLUMN_ALIASES = {
    "economie_estimee_kwh": ["economie_kwh_estimee"],
    "score_qos": ["score_qos_moy"],
    "anomalie_score_ensemble": ["score_anom_moy", "score_moy_ensemble"],
    "consommation_kwh": ["conso_moy"],
    "latitude": ["lat", "gps_lat", "station_lat", "latitude_station"],
    "longitude": ["lon", "lng", "long", "gps_lon", "gps_lng", "station_lon"],
}

ALLOWED_QUERIES = {
    "get_user_by_username_or_email": "\n        SELECT username, email, password_hash, role, display, must_change_password, is_active\n        from app_users\n        where lower(username) = lower(?) or lower(coalesce(email, '')) = lower(?)\n        limit 1\n    ",
    "update_user_profile": "update app_users set display = ?, email = ? where username = ?",
    "insert_alert_decision": "insert into alert_decisions(created_at, user, station_id, alert_ref, verdict, comment) values (?, ?, ?, ?, ?, ?)",
    "get_alert_history": "select created_at, user, alert_ref, verdict, comment from alert_decisions where station_id = ? order by id desc limit 50",
    "get_all_alert_history": "select created_at, user, station_id, alert_ref, verdict, comment from alert_decisions order by id desc",
    "get_recent_alert_history": "select created_at, user, station_id, alert_ref, verdict, comment from alert_decisions order by id desc limit 100",
    "insert_nb3_validation": "insert into nb3_validations(created_at, user, station_id, decision_ref, verdict, comment) values (?, ?, ?, ?, ?, ?)",
    "get_nb3_history": "select created_at, user, decision_ref, verdict, comment from nb3_validations where station_id = ? order by id desc limit 50",
    "get_all_nb3_history": "select created_at, user, station_id, decision_ref, verdict, comment from nb3_validations order by id desc",
    "get_recent_nb3_history": "select created_at, user, station_id, decision_ref, verdict, comment from nb3_validations order by id desc limit 100",
    "get_all_nb3_validations": "select decision_ref from nb3_validations",
    "get_user_stations": "select assigned_stations from app_users where username = ?",
    "set_user_stations": "update app_users set assigned_stations = ? where username = ?",
    "get_all_engineers": "select username from app_users where role = 'ingenieur'",
    "insert_audit_event": "insert into audit_events(created_at, user, event_type, details) values (?, ?, ?, ?)",
    "get_recent_audit_events": "select * from audit_events order by id desc limit 100",
    "delete_engineer_assignments": "delete from engineer_assignments where engineer_user = ?",
    "insert_engineer_assignment": "insert into engineer_assignments(engineer_user, station_id, assigned_at, assigned_by) values (?, ?, ?, ?)",
    "get_engineer_assignments": "select station_id from engineer_assignments where engineer_user = ? order by station_id",
    "get_setting": "select value from app_settings where key = ?",
    "upsert_setting": "insert into app_settings(key, value) values (?, ?) on conflict(key) do update set value = excluded.value",
    "get_all_users": "select username, email, role, display, must_change_password, is_active, created_at, created_by from app_users order by role, display",
    "get_engineers": "select * from app_users where role = 'ingenieur'",
    "get_admins": "select * from app_users where role = 'admin'",
    "insert_user": "insert into app_users(username, email, password_hash, role, display, must_change_password, is_active, created_at, created_by) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
    "update_password": "update app_users set password_hash = ?, must_change_password = ? where username = ?",
    "restore_password": "update app_users set password_hash = ?, must_change_password = ? where username = ?",
    "set_user_active": "update app_users set is_active = ? where username = ?",
    "delete_user": "delete from app_users where username = ?",
    "count_active_admins": "select count(*) from app_users where role = 'admin' and is_active = 1",
    "upsert_ops_item": "\n        insert into ops_items(item_ref, item_type, station_id, title, priority, status, owner, sla_due_at, updated_at, updated_by)\n        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n        on conflict(item_ref, item_type) do update set\n            station_id = excluded.station_id,\n            title = excluded.title,\n            priority = excluded.priority,\n            status = excluded.status,\n            owner = excluded.owner,\n            sla_due_at = excluded.sla_due_at,\n            updated_at = excluded.updated_at,\n            updated_by = excluded.updated_by\n    ",
    "get_ops_items": "select * from ops_items order by updated_at desc",
    "get_ops_item": "select * from ops_items where item_ref = ? and item_type = ? limit 1",
    "insert_item_comment": "insert into item_comments(created_at, user, item_ref, item_type, comment) values (?, ?, ?, ?, ?)",
    "get_item_comments": "select created_at, user, comment from item_comments where item_ref = ? and item_type = ? order by id desc limit 100",
    "insert_ticket": "\n        insert into intervention_tickets(created_at, created_by, item_ref, item_type, station_id, title, assignee, planned_at, status, checklist, result)\n        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n    ",
    "update_ticket_status": "update intervention_tickets set status = ?, result = ? where id = ?",
    "get_tickets": "select * from intervention_tickets order by id desc limit 500",
    "insert_notification": "insert into notifications(created_at, user, title, body, is_read) values (?, ?, ?, ?, 0)",
    "get_notifications": "select * from notifications where user = ? order by id desc limit 100",
    "mark_notification_read": "update notifications set is_read = 1 where id = ? and user = ?",
    "insert_user_session": "insert into user_sessions(session_id, username, started_at, last_seen_at, is_active) values (?, ?, ?, ?, 1)",
    "touch_user_session": "update user_sessions set last_seen_at = ? where session_id = ?",
    "end_user_session": "update user_sessions set is_active = 0, last_seen_at = ? where session_id = ?",
    "get_user_sessions": "select * from user_sessions order by last_seen_at desc limit 200",
}


def fix_mojibake(value: Any) -> Any:

    if isinstance(value, str) and any((token in value for token in ("Ãƒ", "Ã¢", "ÃŽ"))):

        try:

            return value.encode("latin1").decode("utf-8")

        except UnicodeError:

            return value

    if isinstance(value, dict):

        return {fix_mojibake(k): fix_mojibake(v) for k, v in value.items()}

    if isinstance(value, list):

        return [fix_mojibake(v) for v in value]

    return value


def fix_dataframe_text(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty:

        return df

    out = df.copy()

    for col in out.select_dtypes(include=["object"]).columns:

        out[col] = out[col].map(fix_mojibake)

    return out


@st.cache_data(ttl=300, show_spinner=False)
def read_json(path: Path) -> dict:

    if not path.exists():

        return {}

    try:

        return fix_mojibake(json.loads(path.read_text(encoding="utf-8")))

    except Exception:

        return {}


def existing_columns(path: Path) -> list[str]:

    try:

        if pq is not None:

            return pq.read_schema(path).names

        return pd.read_parquet(path).columns.tolist()

    except Exception:

        return []


def parquet_num_rows(path: Path) -> int:

    try:

        if pq is not None:

            return int(pq.ParquetFile(path).metadata.num_rows)

        return int(len(pd.read_parquet(path, columns=[])))

    except Exception:

        return 0


def read_parquet_fast(
    path: Path, columns: list[str] | None = None, filters=None
) -> pd.DataFrame:

    if not path.exists():

        return pd.DataFrame()

    cols = None

    if columns:

        available = existing_columns(path)

        expanded = expand_requested_columns(columns)

        cols = [c for c in expanded if c in available]

    try:

        df = pd.read_parquet(path, columns=cols, filters=filters)

    except Exception:

        try:

            df = pd.read_parquet(path, columns=cols)

        except Exception:

            return pd.DataFrame()

        if filters:

            for col, op, value in filters:

                if op == "=" and col in df.columns:

                    df = df[df[col].astype(str) == str(value)]

    if "timestamp" in df.columns:

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    return normalize_dataframe_columns(fix_dataframe_text(df))


@st.cache_data(ttl=300, show_spinner=False)
def read_csv_artifact(path: Path) -> pd.DataFrame:

    if not path.exists():

        return pd.DataFrame()

    try:

        return fix_dataframe_text(pd.read_csv(path))

    except Exception:

        return pd.DataFrame()


def expand_requested_columns(columns: list[str]) -> list[str]:

    expanded: list[str] = []

    for col in columns:

        expanded.append(col)

        expanded.extend(COLUMN_ALIASES.get(col, []))

    return list(dict.fromkeys(expanded))


def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty:

        return df

    out = df.copy()

    for canonical, aliases in COLUMN_ALIASES.items():

        if canonical not in out.columns:

            for alias in aliases:

                if alias in out.columns:

                    out[canonical] = out[alias]

                    break

    return out


def artifact_quality(path: Path) -> tuple[int, int]:

    if not path.exists():

        return (0, 0)

    if path.suffix.lower() == ".json":

        return (1, path.stat().st_size)

    columns = set(existing_columns(path))

    canonical = set(columns)

    for target, aliases in COLUMN_ALIASES.items():

        if target in columns or any((alias in columns for alias in aliases)):

            canonical.add(target)

    critical = {
        "timestamp",
        "station_id",
        "consommation_kwh",
        "score_qos",
        "anomalie_score_ensemble",
        "economie_rl_kwh",
        "mode_operation",
        "action_rl",
    }

    return (len(critical.intersection(canonical)), parquet_num_rows(path))


def best_local_candidate(candidates: list[Path]) -> Path | None:

    existing = [path for path in candidates if path.exists()]

    if not existing:

        return None

    return max(existing, key=artifact_quality)


def _resolve_artifact_path(filename: str) -> Path:

    global _HF_DISABLED_UNTIL

    candidates = [settings.OUTPUTS_DIR / filename]

    for base in NOTEBOOK_OUTPUTS.values():

        candidates.append(base / filename)

    local_best = best_local_candidate(candidates)

    if local_best:

        return local_best

    if (
        settings.USE_HF_HUB
        and hf_hub_download is not None
        and (time.time() >= _HF_DISABLED_UNTIL)
    ):

        possible_filenames = [filename]

        if not filename.startswith("streamlit_"):

            possible_filenames.append(f"streamlit_{filename}")

        token = hf_hub_token()

        for hf_filename in possible_filenames:

            try:

                downloaded = hf_hub_download(
                    repo_id=settings.HF_REPO_ID,
                    filename=hf_filename,
                    cache_dir=str(settings.HF_CACHE_DIR),
                    local_files_only=False,
                    etag_timeout=30,
                    token=token,
                    resume_download=True,
                )

                hf_path = Path(downloaded)

                if artifact_is_ready(hf_path):

                    return hf_path

            except Exception as exc:

                exc_name = exc.__class__.__name__

                if "EntryNotFound" in exc_name or "RepositoryNotFound" in exc_name:

                    continue

                continue

    return candidates[0]


def artifact_path(filename: str) -> Path:

    cached = _ARTIFACT_HIT_CACHE.get(filename)

    if cached is not None and artifact_is_ready(cached):

        return cached

    resolved = _resolve_artifact_path(filename)

    if artifact_is_ready(resolved):

        _ARTIFACT_HIT_CACHE[filename] = resolved

    return resolved


def clear_artifact_path_cache() -> None:

    _ARTIFACT_HIT_CACHE.clear()


def artifact_url(filename: str) -> str:

    return f"https://huggingface.co/{settings.HF_REPO_ID}/resolve/main/{filename}"


def artifact_inventory() -> pd.DataFrame:

    rows = []

    for filename, meta in ARTIFACT_REGISTRY.items():

        local_candidates = [settings.OUTPUTS_DIR / filename] + [
            base / filename for base in NOTEBOOK_OUTPUTS.values()
        ]

        local_best = best_local_candidate(local_candidates)

        size_mb = (
            local_best.stat().st_size / 1024 / 1024
            if local_best and local_best.exists()
            else None
        )

        rows.append(
            {
                "fichier": filename,
                "notebook": meta["notebook"],
                "type": meta["type"],
                "usage": meta["usage"],
                "source": "HF",
                "fallback_local": bool(local_best),
                "taille_mb": round(size_mb, 3) if size_mb is not None else None,
                "lien_hf": artifact_url(filename),
            }
        )

    return pd.DataFrame(rows)


def artifact_image_path(filename: str) -> Path | None:

    path = artifact_path(filename)

    return path if path.exists() else None


def artifact_table(filename: str, columns: list[str] | None = None) -> pd.DataFrame:

    path = artifact_path(filename)

    if not path.exists():

        return pd.DataFrame()

    suffix = path.suffix.lower()

    if suffix == ".parquet":

        return read_parquet_fast(path, columns)

    if suffix == ".csv":

        return read_csv_artifact(path)

    return pd.DataFrame()


def _filter_artifact_by_df(table: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:

    if table.empty or df.empty:

        return table

    out = table.copy()

    if "station_id" in out.columns and "station_id" in df.columns:

        stations = df["station_id"].astype(str).unique()

        out = out[out["station_id"].astype(str).isin(stations)]

    if "timestamp" in out.columns and "timestamp" in df.columns:

        bounds = pd.to_datetime(df["timestamp"], errors="coerce")

        ttab = pd.to_datetime(out["timestamp"], errors="coerce")

        tmin, tmax = (bounds.min(), bounds.max())

        if pd.notna(tmin) and pd.notna(tmax):

            out = out[(ttab >= tmin) & (ttab <= tmax)]

    return out.reset_index(drop=True)


def artifact_table_for_df(
    filename: str, df: pd.DataFrame, columns: list[str] | None = None
) -> pd.DataFrame:

    return _filter_artifact_by_df(artifact_table(filename, columns), df)


def first_existing_dataset(names: list[str]) -> Path | None:

    for name in names:

        path = artifact_path(name)

        if path.exists():

            return path

    return None


def file_digest(path: Path | str, limit: int = 1048576) -> str:

    path = Path(path)

    if not path.exists() or not path.is_file():

        return ""

    h = hashlib.sha256()

    with path.open("rb") as f:

        h.update(f.read(limit))

    return h.hexdigest()[:16]


@st.cache_data(ttl=300, show_spinner=False)
def full_file_digest(path: Path | str) -> str:

    path = Path(path)

    if not path.exists() or not path.is_file():

        return ""

    h = hashlib.sha256()

    with path.open("rb") as f:

        for chunk in iter(lambda: f.read(1024 * 1024), b""):

            h.update(chunk)

    return h.hexdigest()


def apply_time_filters(df: pd.DataFrame, filters: dict | None = None) -> pd.DataFrame:

    if df.empty:

        return df

    if not filters:

        return df

    out = df

    date_range = filters.get("date_range")

    if date_range and "timestamp" in out.columns:

        try:

            start, end = date_range

        except (TypeError, ValueError):

            start, end = (None, None)

        if start is not None and end is not None:

            start = pd.to_datetime(start, errors="coerce")

            end = pd.to_datetime(end, errors="coerce")

            if pd.notna(start) and pd.notna(end):

                if start > end:

                    start, end = (end, start)

                end_inclusive = (
                    end + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
                )

                ts = pd.to_datetime(out["timestamp"], errors="coerce")

                out = out[(ts >= start) & (ts <= end_inclusive)]

    months = filters.get("months")

    if months and "mois" in out.columns:

        out = out[pd.to_numeric(out["mois"], errors="coerce").isin(months)]

    hours = filters.get("hours")

    if hours and "heure" in out.columns:

        out = out[
            pd.to_numeric(out["heure"], errors="coerce").between(
                int(hours[0]), int(hours[1])
            )
        ]

    day_type = filters.get("day_type", "Tous")

    if day_type != "Tous" and "est_weekend" in out.columns:

        expected = 1 if day_type == "Weekend" else 0

        out = out[pd.to_numeric(out["est_weekend"], errors="coerce") == expected]

    days = filters.get("days")

    if days and "jour_semaine" in out.columns:

        out = out[pd.to_numeric(out["jour_semaine"], errors="coerce").isin(days)]

    return out


ACTION_FILTER_COLUMNS = ["action_rl", "action_proposee", "action_principale"]


def _latest_row_per_station(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty or "station_id" not in df.columns:

        return pd.DataFrame()

    if "timestamp" in df.columns:

        return df.sort_values("timestamp").groupby("station_id", as_index=False).tail(1)

    return df.groupby("station_id", as_index=False).last()


def latest_action_per_station(
    df: pd.DataFrame, *, prefer_rl: bool = False
) -> pd.DataFrame:

    from ui.formatting import resolve_row_action

    latest = _latest_row_per_station(df)

    if latest.empty:

        return pd.DataFrame(columns=["station_id", "action_label"])

    work = latest.copy()

    work["action_label"] = work.apply(
        lambda r: resolve_row_action(r, prefer_rl=prefer_rl, default="Maintien"), axis=1
    )

    return work[["station_id", "action_label"]].assign(
        station_id=lambda x: x["station_id"].astype(str)
    )


def filter_by_station_latest_action(
    df: pd.DataFrame, actions: list[str]
) -> pd.DataFrame:

    if df.empty or not actions or "station_id" not in df.columns:

        return df

    if not any((c in df.columns for c in ACTION_FILTER_COLUMNS)):

        return df

    allowed = {str(a) for a in actions}

    latest = latest_action_per_station(df, prefer_rl=False)

    if latest.empty:

        return df

    station_ok = latest[latest["action_label"].astype(str).isin(allowed)][
        "station_id"
    ].astype(str)

    return df[df["station_id"].astype(str).isin(set(station_ok))]


def filter_by_station_latest_mode(df: pd.DataFrame, modes: list[str]) -> pd.DataFrame:

    if (
        df.empty
        or not modes
        or "station_id" not in df.columns
        or ("mode_operation" not in df.columns)
    ):

        return df

    allowed = {str(m) for m in modes}

    if "timestamp" in df.columns:

        latest_idx = (
            df.sort_values("timestamp").groupby("station_id", sort=False).tail(1).index
        )

        latest = df.loc[latest_idx, ["station_id", "mode_operation"]]

    else:

        latest = df.groupby("station_id", as_index=False).agg(
            mode_operation=("mode_operation", "last")
        )

    station_ok = latest[latest["mode_operation"].astype(str).isin(allowed)][
        "station_id"
    ].astype(str)

    return df[df["station_id"].astype(str).isin(set(station_ok))]


def apply_admin_dimension_filters(
    df: pd.DataFrame, filters: dict | None = None
) -> pd.DataFrame:

    if df.empty:

        return df

    if not filters:

        return df

    out = df

    mapping = {
        "stations": "station_id",
        "gouvernorats": "gouvernorat",
        "technologies": "technologie",
        "zones": "type_zone",
    }

    for key, col in mapping.items():

        values = filters.get(key)

        if values and col in out.columns:

            selected = {str(v) for v in values}

            out = out[out[col].astype(str).isin(selected)]

    actions = filters.get("actions")

    if actions:

        out = filter_by_station_latest_action(out, actions)

    elif filters.get("modes"):

        out = filter_by_station_latest_mode(out, filters["modes"])

    score_min = filters.get("score_min")

    if score_min is not None and "anomalie_score_ensemble" in out.columns:

        out = out[out["anomalie_score_ensemble"].fillna(0) >= float(score_min)]

    return out


def apply_station_criticite_filter(
    df: pd.DataFrame, filters: dict | None = None
) -> pd.DataFrame:

    if df.empty:

        return df

    if not filters:

        filters = st.session_state.get("admin_global_filters", {})

    categories = filters.get("criticites")

    if categories and "categorie" in df.columns:

        return df[df["categorie"].astype(str).isin(categories)]

    return df


_DB_LOCK = threading.Lock()


def db_connect():

    conn = sqlite3.connect(settings.DB_PATH, timeout=20, check_same_thread=False)

    conn.execute("pragma journal_mode=WAL")

    conn.execute("pragma foreign_keys=ON")

    conn.row_factory = sqlite3.Row

    return conn


def db_execute(query_key: str, params: tuple = ()) -> None:

    if query_key not in ALLOWED_QUERIES:

        raise ValueError(f"SQL query key is not allowed: {query_key}")

    sql = ALLOWED_QUERIES[query_key]

    with _DB_LOCK:

        with db_connect() as conn:

            conn.execute(sql, params)

            conn.commit()


def db_read(query_key: str, params: tuple = ()) -> pd.DataFrame:

    if query_key not in ALLOWED_QUERIES:

        raise ValueError(f"SQL query key is not allowed: {query_key}")

    sql = ALLOWED_QUERIES[query_key]

    with _DB_LOCK:

        with db_connect() as conn:

            return pd.read_sql_query(sql, conn, params=params)


def db_scalar(query_key: str, params: tuple = (), default=None):

    if query_key not in ALLOWED_QUERIES:

        raise ValueError(f"SQL query key is not allowed: {query_key}")

    sql = ALLOWED_QUERIES[query_key]

    try:

        with _DB_LOCK:

            with db_connect() as conn:

                row = conn.execute(sql, params).fetchone()

            return row[0] if row else default

    except Exception:

        return default


def init_db() -> None:

    with db_connect() as conn:

        conn.executescript(
            "\n            create table if not exists alert_decisions (\n                id integer primary key autoincrement,\n                created_at text not null,\n                user text not null,\n                station_id text not null,\n                alert_ref text not null,\n                verdict text not null,\n                comment text\n            );\n            create table if not exists nb3_validations (\n                id integer primary key autoincrement,\n                created_at text not null,\n                user text not null,\n                station_id text not null,\n                decision_ref text not null,\n                verdict text not null,\n                comment text\n            );\n            create table if not exists audit_events (\n                id integer primary key autoincrement,\n                created_at text not null,\n                user text not null,\n                event_type text not null,\n                details text\n            );\n            create table if not exists engineer_assignments (\n                engineer_user text not null,\n                station_id text not null,\n                assigned_at text not null,\n                assigned_by text not null,\n                primary key (engineer_user, station_id)\n            );\n            create table if not exists app_users (\n                username text primary key,\n                email text unique,\n                password_hash text not null,\n                role text not null,\n                display text not null,\n                must_change_password integer not null default 0,\n                is_active integer not null default 1,\n                assigned_stations text,\n                created_at text not null,\n                created_by text\n            );\n            "
        )

        try:

            conn.execute("alter table app_users add column assigned_stations text")

        except Exception:

            pass

        conn.executescript(
            "\n            create table if not exists app_settings (\n                key text primary key,\n                value text not null\n            );\n            create table if not exists ops_items (\n                id integer primary key autoincrement,\n                item_ref text not null,\n                item_type text not null,\n                station_id text,\n                title text not null,\n                priority text not null default 'Moyenne',\n                status text not null default 'Nouveau',\n                owner text,\n                sla_due_at text,\n                updated_at text not null,\n                updated_by text not null,\n                unique(item_ref, item_type)\n            );\n            create table if not exists item_comments (\n                id integer primary key autoincrement,\n                created_at text not null,\n                user text not null,\n                item_ref text not null,\n                item_type text not null,\n                comment text not null\n            );\n            create table if not exists intervention_tickets (\n                id integer primary key autoincrement,\n                created_at text not null,\n                created_by text not null,\n                item_ref text not null,\n                item_type text not null,\n                station_id text,\n                title text not null,\n                assignee text,\n                planned_at text,\n                status text not null,\n                checklist text,\n                result text\n            );\n            create table if not exists notifications (\n                id integer primary key autoincrement,\n                created_at text not null,\n                user text not null,\n                title text not null,\n                body text,\n                is_read integer not null default 0\n            );\n            create table if not exists user_sessions (\n                session_id text primary key,\n                username text not null,\n                started_at text not null,\n                last_seen_at text not null,\n                is_active integer not null default 1\n            );\n            "
        )

        import os

        import secrets

        from utils.security import password_hash, password_matches

        primary_admin_email = "molkaalaya4@gmail.com"

        forbidden_default_password = "admin123"

        admin_count = conn.execute(
            "select count(*) from app_users where role = 'admin'"
        ).fetchone()[0]

        if admin_count == 0:

            admin_user = os.getenv("ADMIN_USER") or os.getenv("BTS_ADMIN_USER", "admin")

            admin_pwd = os.getenv("ADMIN_PASSWORD") or os.getenv(
                "BTS_ADMIN_PASSWORD", ""
            )

            if admin_pwd.strip() == forbidden_default_password:

                admin_pwd = ""

            admin_hash_env = (
                os.getenv("ADMIN_PASSWORD_HASH")
                or os.getenv("BTS_ADMIN_PASSWORD_HASH")
                or ""
            )

            if admin_hash_env:

                admin_hash = admin_hash_env

            elif admin_pwd:

                admin_hash = password_hash(admin_pwd)

            else:

                admin_hash = password_hash(secrets.token_urlsafe(24))

            admin_email = os.getenv("ADMIN_EMAIL") or os.getenv(
                "BTS_ADMIN_EMAIL", primary_admin_email
            )

            must_change = 0 if admin_pwd or admin_hash_env else 1

            conn.execute(
                "\n                insert or ignore into app_users(username, email, password_hash, role, display, must_change_password, is_active, created_at, created_by)\n                values (?, ?, ?, 'admin', 'Administrateur', ?, 1, ?, 'system')\n                ",
                (
                    admin_user,
                    admin_email,
                    admin_hash,
                    must_change,
                    datetime.now().isoformat(),
                ),
            )

        primary = conn.execute(
            "select username from app_users where lower(username) = lower(?) or lower(coalesce(email, '')) = lower(?)",
            (primary_admin_email, primary_admin_email),
        ).fetchone()

        if primary:

            conn.execute(
                "update app_users set role = 'admin', is_active = 1 where username = ?",
                (primary["username"],),
            )

        else:

            conn.execute(
                "\n                insert or ignore into app_users(username, email, password_hash, role, display, must_change_password, is_active, created_at, created_by)\n                values (?, ?, ?, 'admin', 'Administrateur principal', 1, 1, ?, 'system')\n                ",
                (
                    primary_admin_email,
                    primary_admin_email,
                    password_hash(secrets.token_urlsafe(24)),
                    datetime.now().isoformat(),
                ),
            )

        admins = conn.execute(
            "select username, password_hash from app_users where role = 'admin'"
        ).fetchall()

        for admin in admins:

            if password_matches(forbidden_default_password, admin["password_hash"]):

                conn.execute(
                    "\n                    update app_users\n                    set password_hash = ?, must_change_password = 1\n                    where username = ?\n                    ",
                    (password_hash(secrets.token_urlsafe(24)), admin["username"]),
                )

        conn.commit()


def get_user_stations(username: str) -> list[str]:

    assigned = db_scalar("get_user_stations", (username,), "")

    if not assigned:

        return []

    return [s.strip() for s in assigned.split(",") if s.strip()]


def set_user_stations(username: str, stations: list[str]):

    val = ",".join(stations) if stations else ""

    db_execute("set_user_stations", (val, username))


INACTIVE_STATIONS_KEY = "inactive_stations"


def load_inactive_stations() -> set[str]:

    cached = st.session_state.get("inactive_stations")

    if isinstance(cached, (set, list, tuple)):

        return {str(s) for s in cached if str(s).strip()}

    inactive: set[str] = set()

    raw = db_scalar("get_setting", (INACTIVE_STATIONS_KEY,), None)

    if raw:

        try:

            parsed = json.loads(raw)

            if isinstance(parsed, list):

                inactive = {str(s) for s in parsed if str(s).strip()}

        except Exception:

            inactive = set()

    if not inactive:

        legacy = db_scalar("get_setting", ("dashboard_config",), None)

        if legacy:

            try:

                cfg = json.loads(legacy)

                if isinstance(cfg, dict):

                    inactive = {
                        str(s)
                        for s in cfg.get("inactive_stations", [])
                        if str(s).strip()
                    }

            except Exception:

                pass

    st.session_state["inactive_stations"] = inactive

    return inactive


_INVALID_STATION_IDS = frozenset({"", "none", "nan", "<na>", "null"})


def valid_station_id(value: Any) -> str | None:

    if value is None or (isinstance(value, float) and pd.isna(value)):

        return None

    text = str(value).strip()

    if text.lower() in _INVALID_STATION_IDS:

        return None

    return text


def clean_station_id_list(ids) -> list[str]:

    out: list[str] = []

    for raw in ids:

        sid = valid_station_id(raw)

        if sid and sid not in out:

            out.append(sid)

    return sorted(out)


def filter_valid_station_rows(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty or "station_id" not in df.columns:

        return df

    mask = df["station_id"].map(valid_station_id).notna()

    return df.loc[mask].copy()


def save_inactive_stations(station_ids: list[str]) -> None:

    cleaned = clean_station_id_list(station_ids)

    db_execute("upsert_setting", (INACTIVE_STATIONS_KEY, json.dumps(cleaned)))

    st.session_state["inactive_stations"] = set(cleaned)

    log_event("inactive_stations_updated", {"count": len(cleaned), "stations": cleaned})


def all_dataset_station_ids() -> list[str]:

    opts = load_filter_dimension_options(dataset_cache_key())

    stations = opts.get("stations") or []

    if stations:

        return clean_station_id_list(stations)

    outputs = load_outputs()

    df = outputs.get("scores")

    if isinstance(df, pd.DataFrame) and "station_id" in df.columns:

        return clean_station_id_list(df["station_id"].unique())

    path = first_existing_dataset(settings.MAIN_DATASET_CANDIDATES)

    if path and path.exists():

        df = read_parquet_fast(path, ["station_id"])

        if not df.empty and "station_id" in df.columns:

            return clean_station_id_list(df["station_id"].unique())

    return []


def filter_active_station_ids(station_ids: list[str]) -> list[str]:

    inactive = load_inactive_stations()

    if not inactive:

        return list(station_ids)

    return [str(s) for s in station_ids if str(s) not in inactive]


@st.cache_data(ttl=300, show_spinner=False)
def load_outputs() -> dict:

    rapport = read_json(artifact_path("rapport_optimisation.json"))

    kpi = read_json(artifact_path("kpi_reseau.json"))

    if not kpi and isinstance(rapport, dict):

        kpi = rapport.get("kpi_reseau", {})

    data: dict = {
        "nb1": read_json(artifact_path("resultats_modeles.json")),
        "nb2": read_json(artifact_path("resultats_anomalie.json")),
        "nb3": rapport if isinstance(rapport, dict) else {},
        "kpi": kpi if isinstance(kpi, dict) else {},
    }

    data["scores"] = read_parquet_fast(artifact_path("score_stations.parquet"))

    data["decisions"] = read_parquet_fast(
        artifact_path("decisions_par_station.parquet")
    )

    return data


DASHBOARD_BASE_COLUMNS = list(
    dict.fromkeys(
        settings.TEMPORAL_COLUMNS
        + [
            "station_id",
            "gouvernorat",
            "technologie",
            "type_zone",
            "consommation_kwh",
            "conso_predite",
            "pred_q10",
            "pred_q90",
            "anomalie_score_ensemble",
            "nb_votes_anomalie",
            "score_qos",
            "mode_operation",
            "action_proposee",
            "action_rl",
            "economie_estimee_kwh",
            "economie_rl_kwh",
            "economie_kwh",
            "ecart_pct",
            "heure",
            "charge_cpu_pct",
            "latitude",
            "longitude",
            "source_decision_nb3",
            "trafic_data_mbps",
            "pue",
            "taux_charge_data",
            "taux_charge_voix",
            "est_weekend",
            "jour_semaine",
        ]
    )
)


def dataset_cache_key() -> str:

    path = first_existing_dataset(settings.MAIN_DATASET_CANDIDATES)

    if path is None:

        return ""

    return f"{path.resolve()}|{path.stat().st_mtime}"


@st.cache_data(ttl=300, show_spinner=False)
def load_enriched_base_dataset(cache_key: str) -> pd.DataFrame:

    if not cache_key:

        return pd.DataFrame()

    path = Path(cache_key.split("|")[0])

    if not path.exists():

        return pd.DataFrame()

    available = set(existing_columns(path))

    read_cols = [c for c in DASHBOARD_BASE_COLUMNS if c in available]

    for required in ("station_id", "timestamp"):

        if required in available and required not in read_cols:

            read_cols.append(required)

    if not read_cols:

        return pd.DataFrame()

    df = read_parquet_fast(path, read_cols)

    return enrich_dashboard_data(df, DASHBOARD_BASE_COLUMNS)


@st.cache_data(ttl=300, show_spinner=False)
def get_dataset_date_bounds(cache_key: str) -> tuple[object, object]:

    if not cache_key:

        return (None, None)

    path = Path(cache_key.split("|")[0])

    if not path.exists():

        return (None, None)

    df = read_parquet_fast(path, ["timestamp"])

    if df.empty or "timestamp" not in df.columns:

        return (None, None)

    ts = pd.to_datetime(df["timestamp"], errors="coerce").dropna()

    if ts.empty:

        return (None, None)

    return (ts.min().date(), ts.max().date())


def _unique_latest_modes_per_station(df: pd.DataFrame) -> list[str]:

    from config.theme import MODE_ORDER, normalize_mode_key

    if df.empty or "station_id" not in df.columns or "mode_operation" not in df.columns:

        return []

    work = df[["station_id", "mode_operation"]].copy()

    if "timestamp" in df.columns:

        work["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        latest = (
            work.sort_values("timestamp").groupby("station_id", as_index=False).tail(1)
        )

    else:

        latest = work.groupby("station_id", as_index=False).agg(
            mode_operation=("mode_operation", "last")
        )

    seen: dict[str, str] = {}

    for raw in latest["mode_operation"].dropna().astype(str):

        key = normalize_mode_key(raw)

        if key and key not in ("NONE", "NAN"):

            seen[key] = key

    ordered = [m for m in MODE_ORDER if m in seen]

    ordered.extend(sorted(set(seen) - set(ordered)))

    return ordered


def _unique_latest_actions_per_station(df: pd.DataFrame) -> list[str]:

    if df.empty or "station_id" not in df.columns:

        return []

    if not any((c in df.columns for c in ACTION_FILTER_COLUMNS)):

        return []

    latest = latest_action_per_station(df, prefer_rl=False)

    if latest.empty:

        return []

    return sorted(latest["action_label"].dropna().astype(str).unique().tolist())


@st.cache_data(ttl=300, show_spinner=False)
def load_filter_dimension_options(cache_key: str) -> dict[str, list[str]]:

    if not cache_key:

        return {}

    path = Path(cache_key.split("|")[0])

    if not path.exists():

        return {}

    available = set(existing_columns(path))

    cols = [
        c
        for c in ("station_id", "gouvernorat", "technologie", "type_zone")
        if c in available
    ]

    cols.extend((c for c in ACTION_FILTER_COLUMNS if c in available))

    if "timestamp" in available:

        cols.append("timestamp")

    if not cols:

        return {}

    df = read_parquet_fast(path, list(dict.fromkeys(cols)))

    out: dict[str, list[str]] = {}

    mapping = {
        "stations": "station_id",
        "gouvernorats": "gouvernorat",
        "technologies": "technologie",
        "zones": "type_zone",
    }

    inactive = load_inactive_stations()

    for key, col in mapping.items():

        if col in df.columns:

            values = clean_station_id_list(df[col].unique())

            if key == "stations" and inactive:

                values = [v for v in values if v not in inactive]

            out[key] = values

    if any((c in df.columns for c in ACTION_FILTER_COLUMNS)):

        out["actions"] = _unique_latest_actions_per_station(df)

    return out


def load_filtered_main_data(columns: list[str]) -> pd.DataFrame:

    base = load_enriched_base_dataset(dataset_cache_key())

    if base.empty:

        return base

    if not columns:

        return base

    use = list(dict.fromkeys(list(columns) + settings.TEMPORAL_COLUMNS))

    present = [c for c in use if c in base.columns]

    return base[present] if present else base


NB2_BUSINESS_COLUMNS = ["score_qos", "anomalie_score_ensemble", "nb_votes_anomalie"]

NB3_BUSINESS_COLUMNS = [
    "mode_operation",
    "action_proposee",
    "action_principale",
    "action_rl",
    "economie_estimee_kwh",
    "economie_rl_kwh",
    "score_qos",
    "meilleur_agent_rl",
]

NB3_DECISION_HEURE_COLUMNS = ["action_rl", "action_proposee", "action_principale"]

DASHBOARD_COLUMN_SOURCES: dict[str, str] = {
    "timestamp": "Dataset actif",
    "station_id": "Dataset actif",
    "consommation_kwh": "Dataset actif",
    "conso_predite": "NB1 — streamlit_data.parquet / df_full_processed.parquet",
    "pred_q10": "NB1 — streamlit_data.parquet",
    "pred_q90": "NB1 — streamlit_data.parquet",
    "ecart_pct": "NB1 — streamlit_data.parquet",
    "anomalie_score_ensemble": "NB2 — df_avec_anomalies.parquet",
    "nb_votes_anomalie": "NB2 — df_avec_anomalies.parquet",
    "mode_operation": "NB3 — streamlit_data.parquet",
    "action_proposee": "NB3 — streamlit_data.parquet / decisions_par_station.parquet",
    "action_principale": "NB3 — decisions_par_station.parquet",
    "action_rl": "NB3 — streamlit_data.parquet / decisions_par_station.parquet",
    "economie_estimee_kwh": "NB3 — streamlit_data.parquet",
    "economie_rl_kwh": "NB3 — streamlit_data.parquet",
    "economie_kwh": "Calcul dashboard (max règles / RL, aligné NB3)",
    "score_qos": "Dataset / NB2 / NB3 (fusion)",
    "meilleur_agent_rl": "NB3 — kpi_reseau.json ou streamlit_data",
}


def dashboard_data_coverage(df: pd.DataFrame) -> pd.DataFrame:

    from services.nb_metrics import blank_mask

    if df.empty:

        return pd.DataFrame()

    rows: list[dict] = []

    for col, source in DASHBOARD_COLUMN_SOURCES.items():

        if col not in df.columns:

            rows.append(
                {"Colonne": col, "Source notebook": source, "Remplissage %": "—"}
            )

            continue

        filled = float((~blank_mask(df[col])).mean() * 100)

        rows.append(
            {
                "Colonne": col,
                "Source notebook": source,
                "Remplissage %": round(filled, 1),
            }
        )

    return pd.DataFrame(rows)


def enrich_dashboard_data(
    df: pd.DataFrame, requested_columns: list[str]
) -> pd.DataFrame:

    if df.empty:

        return df

    out = normalize_dataframe_columns(df)

    if {"station_id", "timestamp"}.issubset(out.columns):

        nb2_cols = list(
            dict.fromkeys(["timestamp", "station_id", *NB2_BUSINESS_COLUMNS])
        )

        nb2 = read_parquet_fast(artifact_path(settings.ANOMALY_DATASET), nb2_cols)

        out = merge_business_columns(
            out, nb2, NB2_BUSINESS_COLUMNS, ["station_id", "timestamp"]
        )

        nb3_cols = list(
            dict.fromkeys(["timestamp", "station_id", *NB3_BUSINESS_COLUMNS])
        )

        nb3 = read_parquet_fast(artifact_path("streamlit_data.parquet"), nb3_cols)

        out = merge_business_columns(
            out,
            nb3,
            NB3_BUSINESS_COLUMNS,
            ["station_id", "timestamp"],
            zero_as_missing=True,
        )

    if {"station_id", "heure"}.issubset(out.columns):

        decision_cols = list(
            dict.fromkeys(["station_id", "heure", *NB3_DECISION_HEURE_COLUMNS])
        )

        decisions = read_parquet_fast(
            artifact_path("decisions_par_station.parquet"), decision_cols
        )

        out = merge_business_columns(
            out,
            decisions,
            NB3_DECISION_HEURE_COLUMNS,
            ["station_id", "heure"],
            zero_as_missing=True,
        )

    out = harmonize_nb3_economies(normalize_dataframe_columns(out))

    if "source_decision_nb3" not in out.columns:

        out["source_decision_nb3"] = pd.NA

    if "mode_operation" in out.columns:

        from services.nb_metrics import blank_mask

        nb3_mask = ~blank_mask(out["mode_operation"])

        if nb3_mask.any():

            out.loc[nb3_mask, "source_decision_nb3"] = "NB3"

    return out


def load_top_anomalies(limit: int = 300) -> pd.DataFrame:

    path = artifact_path(settings.ANOMALY_DATASET)

    df = read_parquet_fast(
        path, list(dict.fromkeys(settings.ANOMALY_COLUMNS + settings.TEMPORAL_COLUMNS))
    )

    if df.empty:

        return df

    sort_cols = [
        c for c in ["anomalie_score_ensemble", "nb_votes_anomalie"] if c in df.columns
    ]

    if sort_cols:

        df = df.nlargest(min(limit, len(df)), sort_cols[0])

    return df.head(limit)


def available_stations() -> list[str]:

    return filter_active_station_ids(all_dataset_station_ids())


def engineer_assigned_stations(engineer_user: str | None = None) -> list[str]:

    if not engineer_user:

        engineer_user = st.session_state.get("user", "")

    return get_user_stations(engineer_user)


@st.cache_data(ttl=300, show_spinner=False)
def load_nb3_network_kpi() -> dict:

    kpi = read_json(artifact_path("kpi_reseau.json"))

    if kpi:

        return kpi

    rapport = read_json(artifact_path("rapport_optimisation.json"))

    return rapport.get("kpi_reseau", {}) if isinstance(rapport, dict) else {}


@st.cache_data(ttl=300, show_spinner=False)
def load_nb1_production_metrics() -> dict:

    nb1 = read_json(artifact_path("resultats_modeles.json"))

    if not isinstance(nb1, dict) or not nb1:

        return {}

    for name in ("LightGBM", "XGBoost", "Random Forest"):

        block = nb1.get(name)

        if isinstance(block, dict) and block.get("r2") is not None:

            return {"model": name, **block}

    best_name, best_block = max(
        (
            (k, v)
            for k, v in nb1.items()
            if isinstance(v, dict) and v.get("r2") is not None
        ),
        key=lambda item: float(item[1]["r2"]),
        default=(None, None),
    )

    if best_block:

        return {"model": best_name, **best_block}

    return {}


@st.cache_data(ttl=300, show_spinner=False)
def load_nb1_models_comparison() -> pd.DataFrame:

    nb1 = read_json(artifact_path("resultats_modeles.json"))

    if not isinstance(nb1, dict) or not nb1:

        return pd.DataFrame()

    prod_name = str(load_nb1_production_metrics().get("model") or "")

    rows: list[dict] = []

    for name, block in nb1.items():

        if not isinstance(block, dict) or block.get("r2") is None:

            continue

        rows.append(
            {
                "Modèle": str(name),
                "R2": float(block["r2"]),
                "RMSE": block.get("rmse"),
                "MAE": block.get("mae"),
                "Production": str(name) == prod_name if prod_name else False,
            }
        )

    if not rows:

        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("R2", ascending=False).reset_index(drop=True)


def _extract_nb2_seuil_ensemble(nb2: dict) -> float | None:

    if not isinstance(nb2, dict) or not nb2:

        return None

    for key in (
        "seuil_ensemble",
        "threshold_ensemble",
        "seuil",
        "ensemble_threshold",
        "optimal_threshold",
    ):

        parsed = _as_threshold_float(nb2.get(key))

        if parsed is not None:

            return parsed

    ensemble = nb2.get("ensemble")

    if isinstance(ensemble, dict):

        for key in ("seuil", "seuil_ensemble", "threshold", "seuil_test"):

            parsed = _as_threshold_float(ensemble.get(key))

            if parsed is not None:

                return parsed

    for value in nb2.values():

        if not isinstance(value, dict):

            continue

        for key in ("seuil_ensemble", "seuil", "threshold"):

            parsed = _as_threshold_float(value.get(key))

            if parsed is not None:

                return parsed

    return None


def _seuil_from_modeles_anomalie_joblib() -> tuple[float | None, str | None]:

    try:

        import joblib

    except ImportError:

        return (None, None)

    path = artifact_path("modeles_anomalie.joblib")

    if not path.exists():

        return (None, None)

    try:

        anom = joblib.load(path)

    except Exception:

        return (None, None)

    if not isinstance(anom, dict):

        return (None, None)

    for key in (
        "seuil_ensemble",
        "seuil_consensus",
        "threshold_ensemble",
        "seuil",
        "optimal_threshold",
    ):

        parsed = _as_threshold_float(anom.get(key))

        if parsed is not None:

            return (parsed, "modeles_anomalie.joblib (NB2)")

    return (None, None)


def _nb2_anomaly_rate_fraction(nb2: dict | None) -> float | None:

    kpi = read_json(artifact_path("kpi_reseau.json"))

    if isinstance(kpi, dict) and kpi.get("pct_anomalies") not in (None, ""):

        return float(kpi["pct_anomalies"]) / 100.0

    if not isinstance(nb2, dict):

        return None

    test_pcts = [
        float(v.get("pct_test")) / 100.0
        for v in nb2.values()
        if isinstance(v, dict) and v.get("pct_test") not in (None, "")
    ]

    return sum(test_pcts) / len(test_pcts) if test_pcts else None


def _seuil_from_anomaly_parquet(nb2: dict | None) -> tuple[float | None, str | None]:

    frac = _nb2_anomaly_rate_fraction(nb2)

    if frac is None or frac <= 0 or frac >= 1:

        return (None, None)

    for name in (settings.ANOMALY_DATASET, "df_avec_anomalies.parquet"):

        path = artifact_path(name)

        if not path.exists():

            continue

        df = read_parquet_fast(path, ["anomalie_score_ensemble"])

        if df.empty or "anomalie_score_ensemble" not in df.columns:

            continue

        scores = pd.to_numeric(df["anomalie_score_ensemble"], errors="coerce").dropna()

        if scores.empty:

            continue

        seuil = float(scores.quantile(1.0 - frac))

        return (
            seuil,
            f"{name} (quantile {1.0 - frac:.4f}, pct_anomalies={frac * 100:.2f}%)",
        )

    return (None, None)


def diagnose_nb2_seuil() -> dict:

    json_path = artifact_path("resultats_anomalie.json")

    nb2 = read_json(json_path)

    explicit = _extract_nb2_seuil_ensemble(nb2 if isinstance(nb2, dict) else {})

    joblib_seuil, _ = _seuil_from_modeles_anomalie_joblib()

    parquet_seuil, _ = _seuil_from_anomaly_parquet(nb2 if isinstance(nb2, dict) else {})

    detector_keys = [
        k
        for k, v in (nb2.items() if isinstance(nb2, dict) else [])
        if isinstance(v, dict) and ("pct_test" in v or "pct_anomalies" in v)
    ]

    parquet_path = artifact_path(settings.ANOMALY_DATASET)

    return {
        "json_path": str(json_path),
        "json_exists": json_path.exists(),
        "json_loaded": bool(nb2),
        "json_detector_keys": detector_keys[:12],
        "json_has_seuil_ensemble": explicit is not None,
        "joblib_path": str(artifact_path("modeles_anomalie.joblib")),
        "joblib_exists": artifact_path("modeles_anomalie.joblib").exists(),
        "joblib_has_seuil": joblib_seuil is not None,
        "parquet_path": str(parquet_path),
        "parquet_exists": parquet_path.exists(),
        "parquet_derived_seuil": parquet_seuil,
        "resolved": resolve_nb2_seuil_ensemble(nb2 if isinstance(nb2, dict) else {}),
    }


def resolve_nb2_seuil_ensemble(
    nb2: dict | None = None,
) -> tuple[float | None, str | None]:

    if nb2 is None:

        nb2 = read_json(artifact_path("resultats_anomalie.json"))

    nb2_dict = nb2 if isinstance(nb2, dict) else {}

    extracted = _extract_nb2_seuil_ensemble(nb2_dict)

    if extracted is not None:

        return (extracted, "resultats_anomalie.json (NB2)")

    joblib_seuil, joblib_src = _seuil_from_modeles_anomalie_joblib()

    if joblib_seuil is not None:

        return (joblib_seuil, joblib_src)

    parquet_seuil, parquet_src = _seuil_from_anomaly_parquet(nb2_dict)

    if parquet_seuil is not None:

        return (parquet_seuil, parquet_src)

    return (None, None)


def _as_threshold_float(value) -> float | None:

    try:

        if value is None or value == "":

            return None

        return float(value)

    except (TypeError, ValueError):

        return None


def _extract_qos_seuil(payload: dict) -> float | None:

    if not isinstance(payload, dict) or not payload:

        return None

    seuils = payload.get("seuils_decision")

    if isinstance(seuils, dict):

        for key in ("qos", "qos_seuil", "seuil_qos"):

            parsed = _as_threshold_float(seuils.get(key))

            if parsed is not None:

                return parsed

    for key in ("qos_seuil", "seuil_qos", "qos"):

        parsed = _as_threshold_float(payload.get(key))

        if parsed is not None:

            return parsed

    kpi = payload.get("kpi_reseau")

    if isinstance(kpi, dict):

        for key in ("qos_seuil", "seuil_qos", "qos"):

            parsed = _as_threshold_float(kpi.get(key))

            if parsed is not None:

                return parsed

    return None


def resolve_qos_seuil() -> tuple[float | None, str | None]:

    rapport = read_json(artifact_path("rapport_optimisation.json"))

    extracted = _extract_qos_seuil(rapport if isinstance(rapport, dict) else {})

    if extracted is not None:

        return (extracted, "rapport_optimisation.json (NB3)")

    kpi = read_json(artifact_path("kpi_reseau.json"))

    extracted = _extract_qos_seuil(kpi if isinstance(kpi, dict) else {})

    if extracted is not None:

        return (extracted, "kpi_reseau.json (NB3)")

    return (None, None)


@st.cache_data(ttl=300, show_spinner=False)
def load_nb2_network_stats() -> dict:

    nb2 = read_json(artifact_path("resultats_anomalie.json"))

    seuil, seuil_source = resolve_nb2_seuil_ensemble(
        nb2 if isinstance(nb2, dict) else {}
    )

    kpi = load_nb3_network_kpi()

    pct = (
        float(kpi.get("pct_anomalies"))
        if kpi and kpi.get("pct_anomalies") is not None
        else None
    )

    if pct is None and isinstance(nb2, dict):

        test_pcts = [
            float(v.get("pct_test"))
            for v in nb2.values()
            if isinstance(v, dict) and v.get("pct_test") not in (None, "")
        ]

        pct = sum(test_pcts) / len(test_pcts) if test_pcts else None

    return {
        "seuil_ensemble": seuil,
        "seuil_ensemble_source": seuil_source,
        "pct_anomalies_reseau": pct,
        "detecteurs": nb2 if isinstance(nb2, dict) else {},
    }


@st.cache_data(ttl=300, show_spinner=False)
def load_nb3_rapport() -> dict:

    return read_json(artifact_path("rapport_optimisation.json"))


def build_nb3_profil_horaire(df: pd.DataFrame) -> pd.DataFrame:

    if not df.empty and {"heure", "consommation_kwh"}.issubset(df.columns):

        work = harmonize_nb3_economies(df)

        hourly = work.groupby("heure", as_index=False).agg(
            conso_moy=("consommation_kwh", "mean")
        )

        if "economie_estimee_kwh" in work.columns:

            eco_by_h = work.groupby("heure")["economie_estimee_kwh"].apply(
                lambda s: pd.to_numeric(s, errors="coerce").mean()
            )

            hourly["conso_optimisee_moy"] = (
                hourly["conso_moy"]
                - eco_by_h.reindex(hourly["heure"]).fillna(0).to_numpy()
            )

        if "economie_rl_kwh" in work.columns:

            rl_by_h = work.groupby("heure")["economie_rl_kwh"].apply(
                lambda s: pd.to_numeric(s, errors="coerce").mean()
            )

            hourly["conso_optimisee_rl_moy"] = (
                hourly["conso_moy"]
                - rl_by_h.reindex(hourly["heure"]).fillna(0).to_numpy()
            )

        return hourly

    profil = artifact_table_for_df("streamlit_profil_horaire.parquet", df)

    return profil if isinstance(profil, pd.DataFrame) else pd.DataFrame()


def _plotly_safe_monthly_series(monthly: pd.DataFrame) -> pd.DataFrame:

    if monthly.empty:

        return monthly

    out = monthly.copy()

    if "timestamp" in out.columns:

        ts_col = out["timestamp"]

        if isinstance(ts_col.dtype, pd.PeriodDtype) or str(ts_col.dtype).startswith(
            "period"
        ):

            out["periode"] = ts_col.astype(str)

            out["timestamp"] = pd.to_datetime(out["periode"], errors="coerce")

        elif not pd.api.types.is_datetime64_any_dtype(ts_col):

            out["periode"] = ts_col.astype(str)

            out["timestamp"] = pd.to_datetime(out["periode"], errors="coerce")

        elif "periode" not in out.columns:

            out["periode"] = pd.to_datetime(ts_col, errors="coerce").dt.strftime(
                "%Y-%m"
            )

    for col in out.columns:

        if col in {"timestamp", "periode", "station_id"}:

            continue

        if pd.api.types.is_numeric_dtype(out[col]):

            out[col] = pd.to_numeric(out[col], errors="coerce")

    return out


def build_nb3_monthly_series(
    df: pd.DataFrame, kpis: dict | None = None
) -> pd.DataFrame:

    ts = artifact_table_for_df("streamlit_timeseries.parquet", df)

    if isinstance(ts, pd.DataFrame) and (not ts.empty) and ("timestamp" in ts.columns):

        ts = ts.copy()

        ts["timestamp"] = pd.to_datetime(ts["timestamp"], errors="coerce")

        conso_col = "conso_tot" if "conso_tot" in ts.columns else "consommation_kwh"

        agg_map = {conso_col: "sum"}

        if "economie_tot" in ts.columns:

            agg_map["economie_tot"] = "sum"

        if "economie_rl_tot" in ts.columns:

            agg_map["economie_rl_tot"] = "sum"

        monthly = (
            ts.groupby(ts["timestamp"].dt.to_period("M")).agg(agg_map).reset_index()
        )

        monthly = monthly.rename(
            columns={
                conso_col: "conso",
                "economie_tot": "eco_expert",
                "economie_rl_tot": "eco_rl",
            }
        )

        monthly["periode"] = monthly["timestamp"].astype(str)

        return _plotly_safe_monthly_series(monthly)

    if df.empty or "timestamp" not in df.columns:

        return pd.DataFrame()

    work = harmonize_nb3_economies(df)

    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")

    agg: dict = {"consommation_kwh": "sum"}

    if "economie_estimee_kwh" in work.columns:

        agg["economie_estimee_kwh"] = "sum"

    if "economie_rl_kwh" in work.columns:

        agg["economie_rl_kwh"] = "sum"

    monthly = work.groupby(work["timestamp"].dt.to_period("M"), as_index=False).agg(agg)

    monthly = monthly.rename(
        columns={
            "consommation_kwh": "conso",
            "economie_estimee_kwh": "eco_expert",
            "economie_rl_kwh": "eco_rl",
        }
    )

    monthly["periode"] = monthly["timestamp"].astype(str)

    return _plotly_safe_monthly_series(monthly)


def _extract_station_coordinates(df: pd.DataFrame) -> pd.DataFrame:

    from utils.geo_tunisia import normalize_geo_columns, valid_coordinate_mask

    if df.empty or "station_id" not in df.columns:

        return pd.DataFrame()

    work = normalize_geo_columns(df)

    if not {"latitude", "longitude"}.issubset(work.columns):

        return pd.DataFrame()

    valid = work[valid_coordinate_mask(work)].copy()

    if valid.empty:

        return pd.DataFrame()

    meta_cols = [
        c
        for c in ["gouvernorat", "technologie", "type_zone", "mode_operation"]
        if c in valid.columns
    ]

    agg: dict = {"latitude": "first", "longitude": "first"}

    for col in meta_cols:

        agg[col] = "first"

    coords = valid.groupby("station_id", as_index=False).agg(agg)

    coords["gps_source"] = "dataset_actif"

    return coords


def _merge_station_map_frames(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:

    if right.empty:

        return left

    if left.empty:

        return right.copy()

    l = left.copy()

    r = right.copy()

    l["station_id"] = l["station_id"].astype(str)

    r["station_id"] = r["station_id"].astype(str)

    l = l.set_index("station_id")

    r = r.set_index("station_id")

    for col in r.columns:

        if col not in l.columns:

            l[col] = r[col]

        else:

            l[col] = l[col].combine_first(r[col])

    return l.reset_index()


def _merge_gps_by_priority(frames: list[pd.DataFrame]) -> pd.DataFrame:

    from utils.geo_tunisia import (
        GPS_SOURCE_PRIORITY,
        normalize_geo_columns,
        valid_coordinate_mask,
    )

    best: dict[str, dict] = {}

    for frame in frames:

        if frame.empty or "station_id" not in frame.columns:

            continue

        work = normalize_geo_columns(frame)

        if not valid_coordinate_mask(work).any():

            continue

        keep_cols = ["station_id", "latitude", "longitude"]

        for col in ("gps_source", "gouvernorat", "technologie", "type_zone"):

            if col in work.columns:

                keep_cols.append(col)

        for _, row in work[valid_coordinate_mask(work)].iterrows():

            sid = str(row["station_id"])

            from utils.geo_tunisia import _text_val

            src = _text_val(row.get("gps_source"), "dataset_actif")

            base_src = src.split("+")[0]

            priority = GPS_SOURCE_PRIORITY.get(base_src, 20)

            if sid not in best or priority > best[sid]["priority"]:

                best[sid] = {"priority": priority, "row": row[keep_cols].to_dict()}

    if not best:

        return pd.DataFrame()

    return pd.DataFrame([entry["row"] for entry in best.values()])


def load_station_map_data(df: pd.DataFrame) -> pd.DataFrame:

    from utils.geo_tunisia import (
        normalize_geo_columns,
        sanitize_station_coordinates,
        valid_coordinate_mask,
    )

    summary = station_summary_from_df(df) if not df.empty else pd.DataFrame()

    summary = summary.drop(columns=["latitude", "longitude"], errors="ignore")

    gps_frames: list[pd.DataFrame] = []

    for artifact_name in (
        "streamlit_carte_stations.parquet",
        "streamlit_score_stations.parquet",
    ):

        artefact = artifact_table_for_df(artifact_name, df)

        if (
            not isinstance(artefact, pd.DataFrame)
            or artefact.empty
            or "station_id" not in artefact.columns
        ):

            continue

        artefact = normalize_geo_columns(artefact)

        if not valid_coordinate_mask(artefact).any():

            continue

        artefact = artefact[valid_coordinate_mask(artefact)].copy()

        artefact["gps_source"] = "carte_nb3"

        if not df.empty and "station_id" in df.columns:

            station_ids = df["station_id"].astype(str).unique()

            artefact = artefact[artefact["station_id"].astype(str).isin(station_ids)]

        if not artefact.empty:

            gps_frames.append(artefact)

    if not df.empty:

        coords = _extract_station_coordinates(df)

        if not coords.empty:

            gps_frames.append(coords)

    gps = _merge_gps_by_priority(gps_frames)

    if not gps.empty:

        summary = _merge_station_map_frames(summary, gps)

    if (
        not df.empty
        and {"station_id", "gouvernorat"}.issubset(df.columns)
        and (not summary.empty)
    ):

        gov_by_station = df.groupby("station_id")["gouvernorat"].agg(
            lambda s: (
                s.dropna().astype(str).mode().iloc[0] if not s.dropna().empty else ""
            )
        )

        summary["gouvernorat"] = (
            summary["station_id"]
            .astype(str)
            .map(gov_by_station.astype(str))
            .fillna(summary.get("gouvernorat", pd.Series(dtype=str)))
        )

    return sanitize_station_coordinates(summary)


def _dataset_month_count(df: pd.DataFrame) -> int:

    if "timestamp" not in df.columns:

        return 12

    ts = pd.to_datetime(df["timestamp"], errors="coerce").dropna()

    if ts.empty:

        return 12

    return max(1, int(ts.dt.to_period("M").nunique()))


def _sum_numeric_col(work: pd.DataFrame, column: str) -> float:

    if column not in work.columns:

        return 0.0

    return float(pd.to_numeric(work[column], errors="coerce").fillna(0).sum())


def _as_float(value: Any, default: float = 0.0) -> float:

    try:

        if value in (None, ""):

            return default

        return float(value)

    except (TypeError, ValueError):

        return default


def _has_active_dimension_filters(gf: dict | None = None) -> bool:

    filters = dict(gf or st.session_state.get("global_filters") or {})

    for key in (
        "stations",
        "gouvernorats",
        "technologies",
        "zones",
        "actions",
        "modes",
        "months",
        "hours",
    ):

        if filters.get(key):

            return True

    date_range = filters.get("date_range")

    if not date_range:

        return False

    dmin, dmax = get_dataset_date_bounds(dataset_cache_key())

    if not dmin or not dmax:

        return True

    start, end = date_range

    return (
        pd.Timestamp(start).date() != pd.Timestamp(dmin).date()
        or pd.Timestamp(end).date() != pd.Timestamp(dmax).date()
    )


def _is_full_network_kpi_scope(df: pd.DataFrame) -> bool:

    if df.empty:

        return False

    if st.session_state.get("role") != "admin":

        return False

    if _has_active_dimension_filters():

        return False

    nb3_kpi = load_nb3_network_kpi()

    return bool(nb3_kpi and nb3_kpi.get("economie_dt") not in (None, ""))


def _economie_totals_from_df(work: pd.DataFrame) -> tuple[float, float, float]:

    eco_series = nb3_export_economie_kwh(work)

    if not isinstance(eco_series, pd.Series):

        eco_series = pd.Series(np.asarray(eco_series, dtype=float))

    eco_combinee = float(eco_series.sum()) if not eco_series.empty else 0.0

    eco_expert = _sum_numeric_col(work, "economie_estimee_kwh")

    eco_rl = _sum_numeric_col(work, "economie_rl_kwh")

    return eco_combinee, eco_expert, eco_rl


def _filtered_conso_total(work: pd.DataFrame) -> float:

    if work.empty or "consommation_kwh" not in work.columns:

        return 0.0

    return float(pd.to_numeric(work["consommation_kwh"], errors="coerce").fillna(0).sum())


def _nb3_prorata_economies(
    work: pd.DataFrame, nb3_kpi: dict
) -> tuple[float, float, float, float, float, str] | None:

    kpi_conso = _as_float(nb3_kpi.get("conso_totale_kwh"))

    kpi_eco = _as_float(nb3_kpi.get("economie_combinee_kwh"))

    if kpi_conso <= 0 or kpi_eco <= 0:

        return None

    filtered_conso = _filtered_conso_total(work)

    share = min(max(filtered_conso / kpi_conso, 0.0), 1.0)

    eco_combinee = kpi_eco * share

    eco_rl = _as_float(nb3_kpi.get("economie_rl_kwh")) * share

    eco_expert = max(eco_combinee - eco_rl, 0.0)

    eco_dt = _as_float(nb3_kpi.get("economie_dt")) * share

    if eco_dt <= 0:

        eco_dt = eco_combinee * settings.PRIX_KWH_TN

    co2_t = _as_float(nb3_kpi.get("co2_evite_t")) * share

    if co2_t <= 0:

        co2_t = eco_combinee * settings.FACTEUR_CO2_TN / 1000

    return eco_combinee, eco_expert, eco_rl, eco_dt, co2_t, "kpi_reseau.json prorata (NB3)"


def _latest_per_station_modes(work: pd.DataFrame) -> pd.Series:

    if (
        work.empty
        or "station_id" not in work.columns
        or "mode_operation" not in work.columns
    ):

        return pd.Series(dtype=str)

    if "timestamp" in work.columns:

        latest = (
            work.sort_values("timestamp").groupby("station_id", as_index=False).last()
        )

    else:

        latest = work.groupby("station_id", as_index=False).last()

    return latest["mode_operation"].astype(str).str.strip()


def compute_filtered_kpis(df: pd.DataFrame) -> dict:

    if df.empty:

        return {}

    work = df.copy()

    nb3_kpi = load_nb3_network_kpi() or {}

    use_nb3_network_kpi = _is_full_network_kpi_scope(work)

    if use_nb3_network_kpi:

        eco_combinee = _as_float(nb3_kpi.get("economie_combinee_kwh"))

        eco_rl = _as_float(nb3_kpi.get("economie_rl_kwh"))

        eco_expert = max(eco_combinee - eco_rl, 0.0)

        eco_dt = _as_float(nb3_kpi.get("economie_dt"), eco_combinee * settings.PRIX_KWH_TN)

        co2_t = _as_float(nb3_kpi.get("co2_evite_t"), eco_combinee * settings.FACTEUR_CO2_TN / 1000)

        combinee_pct = _as_float(nb3_kpi.get("economie_combinee_pct"))

        rl_pct = _as_float(nb3_kpi.get("economie_rl_pct"))

        expert_pct = (eco_expert / _as_float(nb3_kpi.get("conso_totale_kwh")) * 100) if nb3_kpi.get("conso_totale_kwh") else 0.0

        conso = _as_float(nb3_kpi.get("conso_totale_kwh"))

        conso_moyenne = _as_float(nb3_kpi.get("conso_moyenne_kwh"))

        score_qos_moyen = nb3_kpi.get("score_qos_moyen")

        if score_qos_moyen not in (None, ""):

            score_qos_moyen = float(score_qos_moyen)

        pct_mode_eco = _as_float(nb3_kpi.get("pct_mode_eco"))

        pct_anomalies = nb3_kpi.get("pct_anomalies")

        if pct_anomalies not in (None, ""):

            pct_anomalies = float(pct_anomalies)

        nb_stations = int(_as_float(nb3_kpi.get("nb_stations"), work["station_id"].nunique() if "station_id" in work.columns else 0))

        nb_mesures = int(_as_float(nb3_kpi.get("nb_mesures"), len(work)))

        meilleur_agent = nb3_kpi.get("meilleur_agent_rl") or nb3_kpi.get("meilleur_agent")

        economies_source = "kpi_reseau.json (NB3)"

        economie_periode_label = "KPI réseau NB3 (export notebook)"

    else:

        prorata = _nb3_prorata_economies(work, nb3_kpi)

        conso_values = (
            pd.to_numeric(work["consommation_kwh"], errors="coerce").dropna()
            if "consommation_kwh" in work.columns
            else pd.Series(dtype=float)
        )

        conso = float(conso_values.sum()) if not conso_values.empty else 0.0

        conso_moyenne = float(conso_values.mean()) if not conso_values.empty else 0.0

        if prorata is not None:

            eco_combinee, eco_expert, eco_rl, eco_dt, co2_t, economies_source = prorata

            combinee_pct = (
                _as_float(nb3_kpi.get("economie_combinee_pct"))
                if nb3_kpi.get("economie_combinee_pct") not in (None, "")
                else (eco_combinee / conso * 100 if conso > 0 else 0.0)
            )

            rl_pct = eco_rl / conso * 100 if conso > 0 else 0.0

            expert_pct = eco_expert / conso * 100 if conso > 0 else 0.0

            economie_periode_label = "Période filtrée (prorata NB3)"

        else:

            eco_combinee, eco_expert, eco_rl = _economie_totals_from_df(work)

            eco_dt = eco_combinee * settings.PRIX_KWH_TN

            co2_t = eco_combinee * settings.FACTEUR_CO2_TN / 1000

            combinee_pct = eco_combinee / conso * 100 if conso > 0 else 0.0

            rl_pct = eco_rl / conso * 100 if conso > 0 else 0.0

            expert_pct = eco_expert / conso * 100 if conso > 0 else 0.0

            economies_source = "somme_parquet_nb3"

            economie_periode_label = "Période filtrée (export NB3)"

            economie_periode_label = "Période filtrée (export NB3)"

        modes = _latest_per_station_modes(work)

        pct_mode_eco = float(modes.eq("ECO").mean() * 100) if not modes.empty else 0.0

        seuil_anom, _ = resolve_nb2_seuil_ensemble()

        anomaly_values = (
            pd.to_numeric(work["anomalie_score_ensemble"], errors="coerce")
            if "anomalie_score_ensemble" in work.columns
            else pd.Series(dtype=float)
        )

        if seuil_anom is None or anomaly_values.dropna().empty:

            pct_anomalies = None

        else:

            pct_anomalies = float(anomaly_values.gt(seuil_anom).mean() * 100)

        qos_values = (
            pd.to_numeric(work["score_qos"], errors="coerce").dropna()
            if "score_qos" in work.columns
            else pd.Series(dtype=float)
        )

        score_qos_moyen = float(qos_values.mean()) if not qos_values.empty else None

        nb_stations = (
            int(work["station_id"].nunique()) if "station_id" in work.columns else 0
        )

        nb_mesures = len(work)

        meilleur_agent = None

        if "meilleur_agent_rl" in work.columns:

            agents = work["meilleur_agent_rl"].dropna().astype(str).str.strip()

            agents = agents[~agents.str.lower().isin({"", "none", "nan"})]

            if not agents.empty:

                meilleur_agent = agents.mode().iloc[0]

        if not meilleur_agent:

            meilleur_agent = nb3_kpi.get("meilleur_agent_rl") or nb3_kpi.get(
                "meilleur_agent"
            )

    economies_suspectes = combinee_pct > 100.0

    months = _dataset_month_count(work)

    economie_dt_mois = eco_dt / months if months > 0 else 0.0

    return {
        "nb_stations": nb_stations,
        "nb_mesures": nb_mesures,
        "conso_totale_kwh": conso,
        "conso_moyenne_kwh": conso_moyenne,
        "score_qos_moyen": score_qos_moyen,
        "pct_anomalies": pct_anomalies,
        "pct_mode_eco": pct_mode_eco,
        "economie_kwh": eco_combinee,
        "economie_estimee_kwh": eco_expert,
        "economie_rl_kwh": eco_rl,
        "economie_combinee_pct": combinee_pct,
        "economie_rl_pct": rl_pct,
        "economie_expert_pct": expert_pct,
        "meilleur_agent_rl": meilleur_agent,
        "co2_evite_t": co2_t,
        "economie_dt": eco_dt,
        "economie_dt_mois": economie_dt_mois,
        "economie_periode_label": economie_periode_label,
        "nb_mois_periode": months,
        "nb3_ref_economie_combinee_pct": nb3_kpi.get("economie_combinee_pct"),
        "nb3_ref_economie_rl_pct": nb3_kpi.get("economie_rl_pct"),
        "economies_source": economies_source,
        "economies_suspectes": economies_suspectes,
        "uses_nb3_network_kpi": use_nb3_network_kpi,
    }


def station_summary_from_df(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty or "station_id" not in df.columns:

        return pd.DataFrame()

    df = harmonize_nb3_economies(df)

    agg = {
        "consommation_kwh": "mean",
        "score_qos": "mean",
        "anomalie_score_ensemble": "mean",
        "gouvernorat": "first",
        "technologie": "first",
        "type_zone": "first",
    }

    for col in [
        "economie_estimee_kwh",
        "economie_rl_kwh",
        "economie_kwh",
        "latitude",
        "longitude",
    ]:

        if col in df.columns:

            agg[col] = "mean" if col.startswith("economie") else "first"

    available_agg = {k: v for k, v in agg.items() if k in df.columns}

    if available_agg:

        out = df.groupby("station_id", as_index=False).agg(available_agg)

    else:

        out = df[["station_id"]].drop_duplicates().reset_index(drop=True)

    rename_map = {
        "anomalie_score_ensemble": "score_anom_moy",
        "score_qos": "score_qos_moy",
        "consommation_kwh": "conso_moy",
    }

    out = out.rename(
        columns={old: new for old, new in rename_map.items() if old in out.columns}
    )

    has_anom = "score_anom_moy" in out.columns

    has_qos = "score_qos_moy" in out.columns

    if has_anom and has_qos:

        anomaly_score = pd.to_numeric(out["score_anom_moy"], errors="coerce")

        qos_score = pd.to_numeric(out["score_qos_moy"], errors="coerce")

        qos_penalty = (1 - qos_score).clip(0, 1)

        both = anomaly_score.notna() & qos_score.notna()

        out["score_criticite"] = pd.NA

        out.loc[both, "score_criticite"] = (
            (anomaly_score.clip(0, 1) * 0.65 + qos_penalty * 0.35).loc[both].clip(0, 1)
        )

        crit = pd.to_numeric(out["score_criticite"], errors="coerce")

        out["categorie"] = pd.cut(
            crit, bins=[-0.01, 0.2, 0.4, 1.0], labels=["Faible", "Moyenne", "Critique"]
        ).astype(str)

    return out


def log_event(event_type: str, details: dict | str = "") -> None:

    user = st.session_state.get("user", "system")

    payload = (
        json.dumps(details, ensure_ascii=False)
        if isinstance(details, dict)
        else str(details)
    )

    db_execute(
        "insert_audit_event",
        (datetime.now().isoformat(timespec="seconds"), user, event_type, payload),
    )
