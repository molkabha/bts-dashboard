"""Replay real NB1/NB2/NB3 rows for simulation (no synthetic generator)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from services.data_service import load_filtered_main_data

REPLAY_COLUMNS = [
    "timestamp",
    "station_id",
    "consommation_kwh",
    "conso_predite",
    "pred_q10",
    "pred_q90",
    "heure",
    "mois",
    "charge_cpu_pct",
    "temperature_ambiante",
    "score_qos",
    "anomalie_score_ensemble",
    "nb_votes_anomalie",
    "mode_operation",
    "action_proposee",
    "action_rl",
    "action_principale",
    "economie_estimee_kwh",
    "economie_rl_kwh",
    "economie_kwh",
    "meilleur_agent_rl",
    "ecart_pct",
    "technologie",
    "gouvernorat",
    "type_zone",
]


def load_replay_source() -> pd.DataFrame:
    """Full enriched dataset for hour-by-hour replay."""
    return load_filtered_main_data(REPLAY_COLUMNS)


def replay_timestamps(
    source: pd.DataFrame,
    stations: list[str],
    start_dt: datetime | None = None,
    *,
    on_date: datetime | None = None,
) -> list:
    if source.empty or "timestamp" not in source.columns or not stations:
        return []
    station_set = {str(s) for s in stations}
    work = source[source["station_id"].astype(str).isin(station_set)].copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work = work.dropna(subset=["timestamp"]).sort_values("timestamp")
    if on_date is not None:
        target = pd.Timestamp(on_date).date()
        work = work[work["timestamp"].dt.date == target]
    if start_dt is not None:
        work = work[work["timestamp"] >= pd.Timestamp(start_dt)]
    return sorted(work["timestamp"].drop_duplicates().tolist())


def replay_batch(
    source: pd.DataFrame,
    stations: list[str],
    tick: int,
    start_dt: datetime | None = None,
    *,
    on_date: datetime | None = None,
) -> tuple[pd.DataFrame, datetime | None]:
    """Return all station rows for replay tick (one timestamp slice)."""
    stamps = replay_timestamps(source, stations, start_dt, on_date=on_date)
    if tick < 0 or tick >= len(stamps):
        return pd.DataFrame(), None
    ts = stamps[tick]
    batch = source[
        (pd.to_datetime(source["timestamp"], errors="coerce") == ts)
        & (source["station_id"].astype(str).isin(stations))
    ].copy()
    return batch, ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
