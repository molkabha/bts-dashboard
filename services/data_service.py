"""Data access and caching service."""

from __future__ import annotations

import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import streamlit as st

from config.settings import settings

try:
    import pyarrow.parquet as pq
except ImportError:
    pq = None

# Mapping for notebook outputs
NOTEBOOK_OUTPUTS = {
    "NB1": settings.NB1_OUTPUT,
    "NB2": settings.NB2_OUTPUT,
    "NB3": settings.NB3_OUTPUT,
}

# --- SQL Security ---
ALLOWED_QUERIES = {
    "get_user_by_username_or_email": """
        SELECT username, email, password_hash, role, display, must_change_password, is_active
        from app_users
        where lower(username) = lower(?) or lower(coalesce(email, '')) = lower(?)
        limit 1
    """,
    "update_user_profile": "update app_users set display = ?, email = ? where username = ?",
    "insert_alert_decision": "insert into alert_decisions(created_at, user, station_id, alert_ref, verdict, comment) values (?, ?, ?, ?, ?, ?)",
    "get_alert_history": "select created_at, user, alert_ref, verdict, comment from alert_decisions where station_id = ? order by id desc limit 50",
    "insert_nb3_validation": "insert into nb3_validations(created_at, user, station_id, decision_ref, verdict, comment) values (?, ?, ?, ?, ?, ?)",
    "get_nb3_history": "select created_at, user, decision_ref, verdict, comment from nb3_validations where station_id = ? order by id desc limit 50",
    "get_all_nb3_validations": "select decision_ref from nb3_validations",
    "insert_audit_event": "insert into audit_events(created_at, user, event_type, details) values (?, ?, ?, ?)",
    "get_recent_audit_events": "select * from audit_events order by id desc limit 100",
    "delete_engineer_assignments": "delete from engineer_assignments where engineer_user = ?",
    "insert_engineer_assignment": "insert into engineer_assignments(engineer_user, station_id, assigned_at, assigned_by) values (?, ?, ?, ?)",
    "get_engineer_assignments": "select station_id from engineer_assignments where engineer_user = ? order by station_id",
    "get_setting": "select value from app_settings where key = ?",
    "upsert_setting": "insert into app_settings(key, value) values (?, ?) on conflict(key) do update set value = excluded.value",
    "get_all_users": "select username, email, role, display, must_change_password, is_active, created_at, created_by from app_users order by role, display",
    "get_engineers": "select * from app_users where role = 'engineer'",
    "get_admins": "select * from app_users where role = 'admin'",
    "insert_user": "insert into app_users(username, email, password_hash, role, display, must_change_password, is_active, created_at, created_by) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
    "update_password": "update app_users set password_hash = ?, must_change_password = ? where username = ?",
    "set_user_active": "update app_users set is_active = ? where username = ?",
    "delete_user": "delete from app_users where username = ?",
    "count_active_admins": "select count(*) from app_users where role = 'admin' and is_active = 1",
    "upsert_ops_item": """
        insert into ops_items(item_ref, item_type, station_id, title, priority, status, owner, sla_due_at, updated_at, updated_by)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(item_ref, item_type) do update set
            station_id = excluded.station_id,
            title = excluded.title,
            priority = excluded.priority,
            status = excluded.status,
            owner = excluded.owner,
            sla_due_at = excluded.sla_due_at,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
    """,
    "get_ops_items": "select * from ops_items order by updated_at desc",
    "get_ops_item": "select * from ops_items where item_ref = ? and item_type = ? limit 1",
    "insert_item_comment": "insert into item_comments(created_at, user, item_ref, item_type, comment) values (?, ?, ?, ?, ?)",
    "get_item_comments": "select created_at, user, comment from item_comments where item_ref = ? and item_type = ? order by id desc limit 100",
    "insert_ticket": """
        insert into intervention_tickets(created_at, created_by, item_ref, item_type, station_id, title, assignee, planned_at, status, checklist, result)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
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

# --- Data Loading Utilities ---

def fix_mojibake(value: Any) -> Any:
    if isinstance(value, str) and any(token in value for token in ("Ãƒ", "Ã¢", "ÃŽ")):
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

def read_parquet_fast(path: Path, columns: list[str] | None = None, filters=None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    cols = None
    if columns:
        available = existing_columns(path)
        cols = [c for c in columns if c in available]
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
    return fix_dataframe_text(df)

def artifact_path(filename: str) -> Path:
    candidates = [settings.OUTPUTS_DIR / filename]
    for base in NOTEBOOK_OUTPUTS.values():
        candidates.append(base / filename)
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]

def first_existing_dataset(names: list[str]) -> Path | None:
    active = active_dataset_path()
    if active and active.exists():
        return active
    for name in names:
        path = artifact_path(name)
        if path.exists():
            return path
    return None

def active_dataset_path() -> Optional[Path]:
    configured = db_scalar("get_setting", ("active_dataset_path",), "")
    if configured:
        path = settings.ROOT / configured
        if path.exists():
            return path
    active_upload = settings.OUTPUTS_DIR / settings.ACTIVE_UPLOAD_DATASET
    if active_upload.exists():
        return active_upload
    return None

def active_dataset_info() -> dict:
    return {
        "name": db_scalar("get_setting", ("active_dataset_name",), "Standard"),
        "published_at": db_scalar("get_setting", ("active_dataset_published_at",), ""),
    }


def dataset_score_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Build a station-level score table from the active dataset."""
    return station_summary_from_df(df)


def dataset_decision_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Build a station-hour decision table from the active dataset."""
    if df.empty or "station_id" not in df.columns:
        return pd.DataFrame()
    group_cols = ["station_id"]
    if "heure" in df.columns:
        group_cols.append("heure")
    candidates = [
        "mode_operation",
        "action_proposee",
        "action_rl",
        "economie_estimee_kwh",
        "economie_rl_kwh",
        "score_qos",
        "anomalie_score_ensemble",
        "consommation_kwh",
        "technologie",
        "gouvernorat",
        "type_zone",
    ]
    agg = {}
    for col in candidates:
        if col not in df.columns:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            agg[col] = "mean"
        else:
            agg[col] = lambda s: s.dropna().astype(str).mode().iloc[0] if not s.dropna().empty else ""
    if not agg:
        return df[group_cols].drop_duplicates().reset_index(drop=True)
    return df.groupby(group_cols, as_index=False).agg(agg)


def load_active_dataset(columns: list[str] | None = None) -> pd.DataFrame:
    """Load the currently published dataset, if one exists."""
    path = active_dataset_path()
    if path is None or not path.exists():
        return pd.DataFrame()
    return read_parquet_fast(path, columns)

# --- File Integrity ---

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

# --- Filters ---

def apply_time_filters(df: pd.DataFrame, filters: dict | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    if not filters:
        filters = st.session_state.get("admin_time_filters", {})
    if not filters:
        return df
        
    out = df.copy()
    date_range = filters.get("date_range")
    if date_range and "timestamp" in out.columns:
        start, end = date_range
        ts = pd.to_datetime(out["timestamp"], errors="coerce")
        out = out[(ts.dt.date >= start) & (ts.dt.date <= end)]
    
    months = filters.get("months")
    if months and "mois" in out.columns:
        out = out[pd.to_numeric(out["mois"], errors="coerce").isin(months)]
        
    hours = filters.get("hours")
    if hours and "heure" in out.columns:
        out = out[pd.to_numeric(out["heure"], errors="coerce").between(int(hours[0]), int(hours[1]))]
        
    day_type = filters.get("day_type", "Tous")
    if day_type != "Tous" and "est_weekend" in out.columns:
        expected = 1 if day_type == "Weekend" else 0
        out = out[pd.to_numeric(out["est_weekend"], errors="coerce") == expected]
        
    days = filters.get("days")
    if days and "jour_semaine" in out.columns:
        out = out[pd.to_numeric(out["jour_semaine"], errors="coerce").isin(days)]
        
    return out

def apply_admin_dimension_filters(df: pd.DataFrame, filters: dict | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    if not filters:
        filters = st.session_state.get("admin_global_filters", {})
    if not filters:
        return df
        
    out = df.copy()
    mapping = {
        "stations": "station_id",
        "gouvernorats": "gouvernorat",
        "technologies": "technologie",
        "zones": "type_zone",
        "modes": "mode_operation",
    }
    for key, col in mapping.items():
        values = filters.get(key)
        if values and col in out.columns:
            out = out[out[col].astype(str).isin(values)]
            
    qos_min = filters.get("qos_min")
    if qos_min is not None and "score_qos" in out.columns:
        out = out[out["score_qos"].fillna(0) >= float(qos_min)]
        
    score_min = filters.get("score_min")
    if score_min is not None and "anomalie_score_ensemble" in out.columns:
        out = out[out["anomalie_score_ensemble"].fillna(0) >= float(score_min)]
        
    return out

def apply_station_criticite_filter(df: pd.DataFrame, filters: dict | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    if not filters:
        filters = st.session_state.get("admin_global_filters", {})
    categories = filters.get("criticites")
    if categories and "categorie" in df.columns:
        return df[df["categorie"].astype(str).isin(categories)]
    return df

# --- Database Ops ---

import threading

# Global lock for SQLite concurrent access (since it's a single-file DB)
_DB_LOCK = threading.Lock()

def db_connect():
    """Create a thread-safe connection to the SQLite database."""
    conn = sqlite3.connect(settings.DB_PATH, timeout=20, check_same_thread=False)
    conn.execute("pragma journal_mode=WAL")
    conn.execute("pragma foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

def db_execute(query_key: str, params: tuple = ()) -> None:
    """Execute a write query with a global lock."""
    sql = ALLOWED_QUERIES.get(query_key, query_key)
    with _DB_LOCK:
        with db_connect() as conn:
            conn.execute(sql, params)
            conn.commit()

def db_read(query_key: str, params: tuple = ()) -> pd.DataFrame:
    """Read data from the database. Reads can be concurrent in WAL mode, but we use the lock for safety in Streamlit."""
    sql = ALLOWED_QUERIES.get(query_key, query_key)
    with _DB_LOCK:
        with db_connect() as conn:
            return pd.read_sql_query(sql, conn, params=params)

def db_scalar(query_key: str, params: tuple = (), default=None):
    """Execute a query and return the first column of the first row."""
    sql = ALLOWED_QUERIES.get(query_key, query_key)
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
            """
            create table if not exists alert_decisions (
                id integer primary key autoincrement,
                created_at text not null,
                user text not null,
                station_id text not null,
                alert_ref text not null,
                verdict text not null,
                comment text
            );
            create table if not exists nb3_validations (
                id integer primary key autoincrement,
                created_at text not null,
                user text not null,
                station_id text not null,
                decision_ref text not null,
                verdict text not null,
                comment text
            );
            create table if not exists audit_events (
                id integer primary key autoincrement,
                created_at text not null,
                user text not null,
                event_type text not null,
                details text
            );
            create table if not exists engineer_assignments (
                engineer_user text not null,
                station_id text not null,
                assigned_at text not null,
                assigned_by text not null,
                primary key (engineer_user, station_id)
            );
            create table if not exists app_users (
                username text primary key,
                email text unique,
                password_hash text not null,
                role text not null,
                display text not null,
                must_change_password integer not null default 0,
                is_active integer not null default 1,
                created_at text not null,
                created_by text
            );
            create table if not exists app_settings (
                key text primary key,
                value text not null
            );
            create table if not exists ops_items (
                id integer primary key autoincrement,
                item_ref text not null,
                item_type text not null,
                station_id text,
                title text not null,
                priority text not null default 'Moyenne',
                status text not null default 'Nouveau',
                owner text,
                sla_due_at text,
                updated_at text not null,
                updated_by text not null,
                unique(item_ref, item_type)
            );
            create table if not exists item_comments (
                id integer primary key autoincrement,
                created_at text not null,
                user text not null,
                item_ref text not null,
                item_type text not null,
                comment text not null
            );
            create table if not exists intervention_tickets (
                id integer primary key autoincrement,
                created_at text not null,
                created_by text not null,
                item_ref text not null,
                item_type text not null,
                station_id text,
                title text not null,
                assignee text,
                planned_at text,
                status text not null,
                checklist text,
                result text
            );
            create table if not exists notifications (
                id integer primary key autoincrement,
                created_at text not null,
                user text not null,
                title text not null,
                body text,
                is_read integer not null default 0
            );
            create table if not exists user_sessions (
                session_id text primary key,
                username text not null,
                started_at text not null,
                last_seen_at text not null,
                is_active integer not null default 1
            );
            """
        )
        
        # Seed default admin if table is empty
        import os
        import secrets
        from utils.security import password_hash, password_matches
        
        primary_admin_email = "molkaalaya4@gmail.com"
        forbidden_default_password = "admin123"

        admin_count = conn.execute("select count(*) from app_users where role = 'admin'").fetchone()[0]
        if admin_count == 0:
            admin_user = os.getenv("ADMIN_USER") or os.getenv("BTS_ADMIN_USER", primary_admin_email)
            admin_pwd = os.getenv("ADMIN_PASSWORD") or os.getenv("BTS_ADMIN_PASSWORD", "")
            if admin_pwd.strip() == forbidden_default_password:
                admin_pwd = ""
            admin_hash = os.getenv("ADMIN_PASSWORD_HASH") or os.getenv("BTS_ADMIN_PASSWORD_HASH") or password_hash(
                admin_pwd or secrets.token_urlsafe(24)
            )
            admin_email = os.getenv("ADMIN_EMAIL") or os.getenv("BTS_ADMIN_EMAIL", primary_admin_email)
            
            conn.execute(
                """
                insert into app_users(username, email, password_hash, role, display, must_change_password, is_active, created_at, created_by)
                values (?, ?, ?, 'admin', 'Administrateur', 0, 1, ?, 'system')
                """,
                (admin_user, admin_email, admin_hash, datetime.now().isoformat())
            )

        primary = conn.execute(
            """
            select username from app_users
            where lower(username) = lower(?) or lower(coalesce(email, '')) = lower(?)
            limit 1
            """,
            (primary_admin_email, primary_admin_email),
        ).fetchone()
        if primary:
            conn.execute(
                """
                update app_users
                set email = ?, role = 'admin', display = 'Administrateur principal', is_active = 1
                where username = ?
                """,
                (primary_admin_email, primary["username"]),
            )
        else:
            conn.execute(
                """
                insert into app_users(username, email, password_hash, role, display, must_change_password, is_active, created_at, created_by)
                values (?, ?, ?, 'admin', 'Administrateur principal', 1, 1, ?, 'system')
                """,
                (primary_admin_email, primary_admin_email, password_hash(secrets.token_urlsafe(24)), datetime.now().isoformat()),
            )

        admins = conn.execute("select username, password_hash from app_users where role = 'admin'").fetchall()
        for admin in admins:
            if password_matches(forbidden_default_password, admin["password_hash"]):
                conn.execute(
                    """
                    update app_users
                    set password_hash = ?, must_change_password = 1
                    where username = ?
                    """,
                    (password_hash(secrets.token_urlsafe(24)), admin["username"]),
                )
        conn.commit()

# --- Domain Specific Loading ---

@st.cache_data(ttl=300, show_spinner=False)
def load_outputs() -> dict:
    data: dict = {
        "nb1": read_json(artifact_path("resultats_modeles.json")),
        "nb2": read_json(artifact_path("resultats_anomalie.json")),
        "nb3": read_json(artifact_path("rapport_optimisation.json")),
        "kpi": read_json(artifact_path("kpi_reseau.json")),
    }
    data["scores"] = read_parquet_fast(artifact_path("score_stations.parquet"))
    data["decisions"] = read_parquet_fast(artifact_path("decisions_par_station.parquet"))
    active = load_active_dataset()
    if not active.empty:
        data["active_dataset"] = active
        data["scores"] = dataset_score_summary(active)
        data["decisions"] = dataset_decision_summary(active)
    return data

@st.cache_data(ttl=300, show_spinner=False)
def load_station_data(station: str, columns: tuple[str, ...] = tuple()) -> pd.DataFrame:
    if not columns:
        columns = tuple(settings.NB1_COLUMNS)
    path = first_existing_dataset(settings.MAIN_DATASET_CANDIDATES)
    if path is None:
        return pd.DataFrame()
    return read_parquet_fast(path, list(columns), filters=[("station_id", "=", station)])

@st.cache_data(ttl=300, show_spinner=False)
def load_station_anomalies(station: str, columns: tuple[str, ...] = tuple()) -> pd.DataFrame:
    """
    Load NB2 anomaly rows for a single station from the anomaly dataset.
    UI pages can further filter by time using apply_time_filters().
    """
    if not columns:
        columns = tuple(settings.ANOMALY_COLUMNS)
    path = active_dataset_path() or artifact_path(settings.ANOMALY_DATASET)
    if path is None or not path.exists():
        return pd.DataFrame()
    return read_parquet_fast(path, list(columns), filters=[("station_id", "=", station)])

def load_filtered_main_data(columns: list[str]) -> pd.DataFrame:
    path = first_existing_dataset(settings.MAIN_DATASET_CANDIDATES)
    if path is None:
        return pd.DataFrame()
    cols = list(dict.fromkeys(columns + settings.TEMPORAL_COLUMNS))
    return apply_time_filters(read_parquet_fast(path, cols))

def load_top_anomalies(limit: int = 300) -> pd.DataFrame:
    path = active_dataset_path() or artifact_path(settings.ANOMALY_DATASET)
    df = read_parquet_fast(path, list(dict.fromkeys(settings.ANOMALY_COLUMNS + settings.TEMPORAL_COLUMNS)))
    df = apply_time_filters(df)
    if df.empty:
        return df
    sort_cols = [c for c in ["anomalie_score_ensemble", "nb_votes_anomalie"] if c in df.columns]
    if sort_cols:
        df = df.nlargest(min(limit, len(df)), sort_cols[0])
    return df.head(limit)

@st.cache_data(ttl=300, show_spinner=False)
def load_simulation_base(max_rows: int) -> pd.DataFrame:
    path = first_existing_dataset(settings.MAIN_DATASET_CANDIDATES)
    if path is None:
        return pd.DataFrame()
    return read_parquet_fast(path, settings.SIMULATION_COLUMNS).head(max_rows)

def available_stations() -> list[str]:
    path = first_existing_dataset(settings.MAIN_DATASET_CANDIDATES)
    if path is not None:
        df = read_parquet_fast(path, ["station_id"])
        if "station_id" in df.columns:
            return sorted(df["station_id"].dropna().astype(str).unique().tolist())
    outputs = st.session_state.get("data", load_outputs())
    df = outputs.get("scores")
    if isinstance(df, pd.DataFrame) and "station_id" in df.columns:
        return sorted(df["station_id"].dropna().astype(str).unique().tolist())
    return []

def engineer_assigned_stations(engineer_user: str | None = None) -> list[str]:
    engineer_user = (engineer_user or st.session_state.get("user") or "ing.reseau").strip().lower()
    stations = available_stations()
    configured = db_scalar("get_setting", (f"engineer_assignments_configured:{engineer_user}",), None)
    if configured is None and engineer_user == "ing.reseau":
        configured = db_scalar("get_setting", ("engineer_assignments_configured",), "0")
    configured = configured == "1"
    assigned = db_read("get_engineer_assignments", (engineer_user,))
    if configured:
        if assigned.empty:
            return []
        return [s for s in assigned["station_id"].astype(str).tolist() if s in stations]
    if engineer_user != "ing.reseau":
        return []
    return stations[:8]

# --- KPIs and Summaries ---

def compute_filtered_kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    conso = df["consommation_kwh"].sum() if "consommation_kwh" in df.columns else 0.0
    eco_rl = df["economie_rl_kwh"].fillna(0).sum() if "economie_rl_kwh" in df.columns else 0.0
    return {
        "nb_stations": df["station_id"].nunique() if "station_id" in df.columns else 0,
        "nb_mesures": len(df),
        "conso_totale_kwh": conso,
        "conso_moyenne_kwh": df["consommation_kwh"].mean() if "consommation_kwh" in df.columns else 0,
        "score_qos_moyen": df["score_qos"].mean() if "score_qos" in df.columns else np.nan,
        "pct_anomalies": (df["anomalie_score_ensemble"].gt(0.25).mean() * 100) if "anomalie_score_ensemble" in df.columns else 0,
        "pct_mode_eco": (df["mode_operation"].eq("ECO").mean() * 100) if "mode_operation" in df.columns else 0,
        "economie_rl_pct": (eco_rl / conso * 100) if conso else 0,
        "co2_evite_t": eco_rl * settings.FACTEUR_CO2_TN / 1000,
        "economie_dt": eco_rl * settings.PRIX_KWH_TN,
    }

def station_summary_from_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "station_id" not in df.columns:
        return pd.DataFrame()
    agg = {
        "consommation_kwh": "mean",
        "score_qos": "mean",
        "anomalie_score_ensemble": "mean",
        "gouvernorat": "first",
        "technologie": "first",
        "type_zone": "first",
    }
    for col in ["economie_estimee_kwh", "economie_rl_kwh", "latitude", "longitude"]:
        if col in df.columns:
            agg[col] = "mean" if col.startswith("economie") else "first"
    out = df.groupby("station_id", as_index=False).agg({k: v for k, v in agg.items() if k in df.columns})
    
    if "anomalie_score_ensemble" in out.columns:
        out = out.rename(columns={"anomalie_score_ensemble": "score_anom_moy", "score_qos": "score_qos_moy", "consommation_kwh": "conso_moy"})
        qos_penalty = 1 - out.get("score_qos_moy", pd.Series(0.75, index=out.index)).fillna(0.75)
        out["score_criticite"] = (out["score_anom_moy"].fillna(0) * 0.65 + qos_penalty * 0.35).clip(0, 1)
        out["categorie"] = pd.cut(
            out["score_criticite"],
            bins=[-0.01, 0.20, 0.40, 1.0],
            labels=["Faible", "Moyenne", "Critique"],
        ).astype(str)
    return out

# --- Logging ---

def log_event(event_type: str, details: dict | str = "") -> None:
    user = st.session_state.get("user", "system")
    payload = json.dumps(details, ensure_ascii=False) if isinstance(details, dict) else str(details)
    db_execute("insert_audit_event", (datetime.now().isoformat(timespec="seconds"), user, event_type, payload))
