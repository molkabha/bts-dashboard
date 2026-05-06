from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from ui.layout import kpi_card, section


MEASUREMENT_COLUMNS = [
    "consommation_kwh",
    "conso_predite",
    "score_qos",
    "charge_cpu_pct",
    "taux_charge_voix",
    "taux_charge_data",
    "nb_utilisateurs_actifs",
    "anomalie_score_ensemble",
    "nb_votes_anomalie",
    "temperature_ambiante",
    "humidite_relative_pct",
    "vitesse_vent_ms",
    "precipitation_mmh",
    "puissance_emission_dbm",
    "efficacite_free_cooling",
]

CONTEXT_COLUMNS = [
    "station_id",
    "timestamp",
    "technologie",
    "gouvernorat",
    "type_zone",
    "heure",
    "mois",
    "jour_semaine",
    "est_weekend",
    "est_ferie",
]

DECISION_COLUMNS = [
    "mode_operation",
    "priorite",
    "action_principale",
    "action_proposee",
    "action_rl",
    "economie_estimee_kwh",
    "economie_rl_kwh",
    "risque_qos",
    "source_decision_nb3",
]


def _json_value(value: Any):
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _row_payload(row: pd.Series) -> dict:
    payload = {
        "station": {col: _json_value(row[col]) for col in CONTEXT_COLUMNS if col in row.index},
        "measurements": {col: _json_value(row[col]) for col in MEASUREMENT_COLUMNS if col in row.index},
        "decision": {col: _json_value(row[col]) for col in DECISION_COLUMNS if col in row.index},
    }
    return payload


def api_response_from_frame(df: pd.DataFrame, station: str | None = None) -> dict:
    if df.empty:
        return {
            "status": 204,
            "request_id": str(uuid.uuid4()),
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "count": 0,
            "data": [],
        }
    out = df.copy()
    if station and "station_id" in out.columns:
        scoped = out[out["station_id"].astype(str) == str(station)]
        if not scoped.empty:
            out = scoped
    if "timestamp" in out.columns:
        out = out.sort_values("timestamp")
    latest = out.groupby("station_id", as_index=False).tail(1) if "station_id" in out.columns else out.tail(1)
    data = [_row_payload(row) for _, row in latest.iterrows()]
    captured_at = data[0]["station"].get("timestamp") if data else datetime.now().isoformat(timespec="seconds")
    return {
        "status": 200,
        "request_id": str(uuid.uuid4()),
        "captured_at": captured_at,
        "count": len(data),
        "data": data,
    }


def render_api_response(df: pd.DataFrame, station: str | None = None, base_path: str = "/api/v1/telemetry/latest") -> None:
    response = api_response_from_frame(df, station)
    station_suffix = f"/stations/{station}/telemetry/latest" if station else base_path
    endpoint = f"GET {station_suffix}"
    latency_ms = 28 + response["count"] * 3

    section("Reponse API temps reel")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("HTTP", str(response["status"]), endpoint)
    with c2:
        kpi_card("Latence", f"{latency_ms} ms", "simulation API")
    with c3:
        kpi_card("Captures", str(response["count"]), "stations")
    with c4:
        kpi_card("Capture", str(response["captured_at"]), "timestamp station")

    st.code(endpoint, language="http")
    st.json(response)
    st.download_button(
        "Telecharger JSON API",
        data=json.dumps(response, ensure_ascii=False, indent=2),
        file_name="reponse_api_temps_reel.json",
        mime="application/json",
        width="stretch",
    )
