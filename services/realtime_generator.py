"""Realtime station data generation service."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from utils.calendar import (
    FACTEUR_ZONE_REALTIME,
    PROFILS_TRAFIC_REALTIME,
    is_ramadan_date,
    is_tunisian_holiday,
    tunisian_holiday_name,
    ramadan_range,
)
from services.data_service import load_station_data


def _median_or_default(df: pd.DataFrame, col: str, default: float) -> float:
    if df.empty or col not in df.columns:
        return default
    values = pd.to_numeric(df[col], errors="coerce").dropna()
    return float(values.median()) if not values.empty else default


def _hourly_profile(df: pd.DataFrame, value_col: str, default: float) -> pd.Series:
    if df.empty or "heure" not in df.columns or value_col not in df.columns:
        return pd.Series([default] * 24, index=range(24), dtype=float)
    values = df.copy()
    values[value_col] = pd.to_numeric(values[value_col], errors="coerce")
    profile = values.dropna(subset=[value_col]).groupby("heure")[value_col].median()
    return profile.reindex(range(24), fill_value=default).fillna(default)


def _monthly_profile(df: pd.DataFrame, value_col: str, default: float) -> pd.Series:
    if df.empty or "mois" not in df.columns or value_col not in df.columns:
        return pd.Series([default] * 12, index=range(1, 13), dtype=float)
    values = df.copy()
    values[value_col] = pd.to_numeric(values[value_col], errors="coerce")
    profile = values.dropna(subset=[value_col]).groupby("mois")[value_col].median()
    return profile.reindex(range(1, 13), fill_value=default).fillna(default)


def generate_realtime_weather(
    ts: datetime, latitude: float | None, type_zone: str, rng: np.random.Generator
) -> dict:
    """Generate realistic weather data for a given timestamp and location."""
    hour = ts.hour
    month = ts.month
    lat = 35.5 if latitude is None or pd.isna(latitude) else float(latitude)
    zone_offset = {"Urbain": 1.2, "Periurbain": 0.4, "Rural": -0.3}.get(type_zone, 0.0)
    sud_offset = float(np.clip((35.5 - lat) * 0.7, -1.0, 2.5))

    temp_base = 19 + 11 * np.sin((month - 4) * np.pi / 6)
    temp_var = 6 * np.sin((hour - 6) * np.pi / 12)
    temperature = temp_base + temp_var + zone_offset + sud_offset + rng.normal(0, 1.5)

    rain_season = 0.16 if month in [11, 12, 1, 2, 3] else 0.07 if month in [4, 10] else 0.015
    pluie_event = rng.random() < rain_season
    precipitation = rng.gamma(1.7, 2.2) if pluie_event else 0.0

    humidite_base = 66 - 0.9 * max(temperature - 20, 0) + (16 if pluie_event else 0)
    humidite = np.clip(humidite_base + rng.normal(0, 9), 18, 98)
    vent = np.clip(rng.normal(3.4 + (0.9 if pluie_event else 0.0), 1.4), 0, 13)

    daylight = max(0, np.sin((hour - 6) / 12 * np.pi))
    summer_gain = 0.85 + 0.25 * np.sin((month - 4) * np.pi / 6)
    cloud_factor = 0.45 if pluie_event else rng.uniform(0.78, 1.0)
    rayonnement = np.clip(920 * daylight * summer_gain * cloud_factor + rng.normal(0, 35), 0, 1050)
    indice_uv = np.clip((rayonnement / 1050) * (9.5 + 1.0 * np.sin((month - 5) * np.pi / 6)), 0, 12)
    pression = np.clip(1015 - 0.11 * lat - (5.5 if pluie_event else 0) + rng.normal(0, 4), 950, 1060)

    return {
        "temperature_ambiante": round(float(temperature), 1),
        "humidite_relative_pct": round(float(humidite), 1),
        "vitesse_vent_ms": round(float(vent), 2),
        "rayonnement_solaire_wm2": round(float(rayonnement), 1),
        "precipitation_mmh": round(float(precipitation), 2),
        "pression_atmospherique_hpa": round(float(pression), 1),
        "indice_uv": round(float(indice_uv), 1),
    }


def generate_realtime_station_data(
    station: str,
    periods: int,
    anomaly_rate: float,
    seed: int,
    start_time: datetime | None = None,
    freq_minutes: int = 5,
) -> pd.DataFrame:
    """Generate realistic realtime station data with 7 anomaly detectors and 7 RL agents."""
    rng = np.random.default_rng(seed)

    # Load reference data from parquet files
    ref = load_station_data(
        station,
        (
            "timestamp", "station_id", "technologie", "gouvernorat", "type_zone",
            "latitude", "consommation_kwh", "score_qos", "charge_cpu_pct",
            "taux_charge_voix", "taux_charge_data", "nb_utilisateurs_actifs",
            "mois", "heure", "jour_semaine", "est_weekend",
        ),
    )

    technologie = ref["technologie"].dropna().astype(str).mode(
    ).iloc[0] if not ref.empty and "technologie" in ref.columns else "4G"
    gouvernorat = ref["gouvernorat"].dropna().astype(str).mode(
    ).iloc[0] if not ref.empty and "gouvernorat" in ref.columns else ""
    type_zone = ref["type_zone"].dropna().astype(str).mode(
    ).iloc[0] if not ref.empty and "type_zone" in ref.columns else ""
    latitude = float(ref["latitude"].dropna().median(
    )) if not ref.empty and "latitude" in ref.columns and not ref["latitude"].dropna().empty else None

    if not ref.empty:
        ref["timestamp"] = pd.to_datetime(ref["timestamp"], errors="coerce")
        if "heure" not in ref.columns:
            ref["heure"] = ref["timestamp"].dt.hour
        if "mois" not in ref.columns:
            ref["mois"] = ref["timestamp"].dt.month
        if "jour_semaine" not in ref.columns:
            ref["jour_semaine"] = ref["timestamp"].dt.weekday
        if "est_weekend" not in ref.columns:
            ref["est_weekend"] = ref["jour_semaine"].ge(5).astype(int)

        base_conso = _median_or_default(ref, "consommation_kwh", 3.5)
        base_qos = _median_or_default(ref, "score_qos", 0.82)
        base_cpu = _median_or_default(ref, "charge_cpu_pct", 45.0)
        base_voix = _median_or_default(ref, "taux_charge_voix", 0.22)
        base_data = _median_or_default(ref, "taux_charge_data", 0.35)
        base_users = _median_or_default(ref, "nb_utilisateurs_actifs", 120)

        hourly_consommation = _hourly_profile(ref, "consommation_kwh", base_conso)
        monthly_consommation = _monthly_profile(ref, "consommation_kwh", base_conso)
        hourly_qos = _hourly_profile(ref, "score_qos", base_qos)
    else:
        base_conso = 3.5
        base_qos = 0.82
        base_cpu = 45.0
        base_voix = 0.22
        base_data = 0.35
        base_users = 120
        hourly_consommation = pd.Series([base_conso] * 24, index=range(24))
        monthly_consommation = pd.Series([base_conso] * 12, index=range(1, 13))
        hourly_qos = pd.Series([base_qos] * 24, index=range(24))

    start = (start_time or datetime.now()).replace(second=0, microsecond=0)
    timestamps = [start + timedelta(minutes=i * freq_minutes) for i in range(periods)]
    rows = []
    for ts in timestamps:
        hour = ts.hour
        weekday = ts.weekday()
        est_weekend = int(weekday >= 5)
        est_vendredi = int(weekday == 4)
        est_ramadan = is_ramadan_date(ts)
        est_ferie = is_tunisian_holiday(ts)
        tunisian_holiday_name(ts)
        ramadan_start, ramadan_end, ramadan_method = ramadan_range(ts.year, "auto")
        month = ts.month

        if est_ramadan:
            profil_key = "ramadan"
        elif est_weekend or est_vendredi:
            profil_key = "weekend"
        else:
            profil_key = "normal"

        profil_factor = float(PROFILS_TRAFIC_REALTIME[profil_key][hour])
        zone_factor = FACTEUR_ZONE_REALTIME.get(type_zone, 1.0)
        tech_factor = {"2G": 0.85, "3G": 0.95, "4G": 1.00, "4G+": 1.05}.get(technologie, 1.0)
        holiday_factor = 0.60 if est_ferie else 1.0
        traffic_factor = profil_factor * zone_factor * tech_factor * holiday_factor

        # Base consumption with hourly and monthly patterns
        conso_base = hourly_consommation[hour] * monthly_consommation[month] / monthly_consommation.mean()
        conso = conso_base * traffic_factor * rng.uniform(0.85, 1.15)

        # QoS degrades only with high traffic (congestion) and random drops
        qos_base = hourly_qos[hour]
        qos_degradation = max(0, traffic_factor - 1.2) * 0.4
        qos = np.clip(qos_base - qos_degradation - rng.exponential(0.02), 0.1, 0.99)

        # CPU load correlates with traffic
        cpu = np.clip(base_cpu * traffic_factor + rng.normal(0, 8), 5, 98)

        # Voice and data traffic
        voix = np.clip(base_voix * traffic_factor + rng.normal(0, 0.05), 0.01, 0.95)
        data = np.clip(base_data * traffic_factor + rng.normal(0, 0.08), 0.01, 0.95)

        # Users
        users = int(base_users * traffic_factor * rng.uniform(0.8, 1.2))

        # Weather
        weather = generate_realtime_weather(ts, latitude, type_zone, rng)

        # --- 7 Unsupervised Anomaly Detectors ---
        conso_z = abs(conso - conso_base) / max(conso_base * 0.3, 0.01)
        cpu_z = abs(cpu - base_cpu) / max(base_cpu * 0.4, 0.01)
        qos_z = max(0, (0.82 - qos) / 0.15)
        traffic_z = max(0, (data + voix - base_data - base_voix) / 0.3)
        temp_z = max(0, (weather["temperature_ambiante"] - 40) / 10)

        detector_scores = {
            "isolation_forest": float(np.clip(0.4 * conso_z + 0.3 * cpu_z + 0.2 * qos_z + rng.normal(0, 0.08), 0, 1)),
            "lof": float(np.clip(0.3 * conso_z + 0.3 * traffic_z + 0.2 * cpu_z + rng.normal(0, 0.10), 0, 1)),
            "one_class_svm": float(np.clip(0.35 * conso_z + 0.25 * qos_z + 0.2 * temp_z + rng.normal(0, 0.07), 0, 1)),
            "autoencoder": float(np.clip(0.3 * conso_z + 0.25 * cpu_z + 0.25 * traffic_z + 0.1 * temp_z + rng.normal(0, 0.09), 0, 1)),
            "dbscan": float(np.clip(0.4 * traffic_z + 0.3 * conso_z + 0.15 * cpu_z + rng.normal(0, 0.12), 0, 1)),
            "elliptic_envelope": float(np.clip(0.35 * conso_z + 0.3 * qos_z + 0.2 * cpu_z + rng.normal(0, 0.08), 0, 1)),
            "knn_anomaly": float(np.clip(0.3 * conso_z + 0.2 * traffic_z + 0.2 * qos_z + 0.15 * temp_z + rng.normal(0, 0.10), 0, 1)),
        }

        seuil_det = 0.25
        nb_votes = sum(1 for v in detector_scores.values() if v > seuil_det)
        det_weights = [0.18, 0.15, 0.14, 0.17, 0.12, 0.12, 0.12]
        score_anomalie = float(np.clip(sum(w * s for w, s in zip(det_weights, detector_scores.values())), 0, 1))

        # Force anomaly injection at configured rate
        if rng.random() < anomaly_rate and score_anomalie < 0.25:
            boost = rng.uniform(0.30, 0.70)
            score_anomalie = float(np.clip(score_anomalie + boost, 0.25, 0.95))
            nb_votes = max(nb_votes, int(rng.integers(3, 7)))
            conso *= rng.uniform(1.3, 2.0)
            qos *= rng.uniform(0.4, 0.75)
            cpu = min(99, cpu * rng.uniform(1.3, 2.0))

        # --- 7 RL Agents ---
        # RL agents don't propose economies during critical anomalies
        if score_anomalie > 0.60 or qos < 0.60:
            eco_base = 0.0
        else:
            eco_base = conso * 0.03

        rl_agents = {
            "q_learning": float(np.clip(eco_base * rng.uniform(0.9, 1.4), 0, conso * 0.20)),
            "sarsa": float(np.clip(eco_base * rng.uniform(0.8, 1.3), 0, conso * 0.18)),
            "double_q_learning": float(np.clip(eco_base * rng.uniform(0.95, 1.5), 0, conso * 0.22)),
            "expected_sarsa": float(np.clip(eco_base * rng.uniform(0.85, 1.35), 0, conso * 0.19)),
            "q_learning_adaptatif": float(np.clip(eco_base * rng.uniform(1.0, 1.6), 0, conso * 0.25)),
            "sarsa_lambda": float(np.clip(eco_base * rng.uniform(0.9, 1.45), 0, conso * 0.21)),
            "dyna_q": float(np.clip(eco_base * rng.uniform(1.05, 1.55), 0, conso * 0.23)),
        }
        best_agent = max(rl_agents, key=rl_agents.get)
        economie_rl = rl_agents[best_agent]

        # Power emission
        puissance_emission = 43.0 + rng.normal(0, 3)
        if conso > conso_base * 1.5:
            puissance_emission += rng.uniform(2, 8)

        # Free cooling efficiency
        efficacite_free_cooling = float(np.clip(
            (22 - weather["temperature_ambiante"]) / 15 * weather["vitesse_vent_ms"] / 5, 0, 1
        )) if weather["temperature_ambiante"] < 22 else 0.0

        row = {
            "timestamp": ts,
            "station_id": station,
            "technologie": technologie,
            "gouvernorat": gouvernorat,
            "type_zone": type_zone,
            "latitude": latitude,
            "consommation_kwh": round(conso, 3),
            "conso_predite": round(conso * rng.uniform(0.95, 1.05), 3),
            "pred_q10": round(conso * rng.uniform(0.85, 0.95), 3),
            "pred_q90": round(conso * rng.uniform(1.05, 1.15), 3),
            "ecart_pct": round((conso - conso_base) / conso_base * 100, 2),
            "anomalie_score_ensemble": round(score_anomalie, 3),
            "nb_votes_anomalie": nb_votes,
            **{f"score_{k}": round(v, 3) for k, v in detector_scores.items()},
            **{f"eco_rl_{k}": round(v, 4) for k, v in rl_agents.items()},
            "meilleur_agent_rl": best_agent,
            "economie_rl_kwh": round(economie_rl, 4),
            "score_qos": round(qos, 3),
            "charge_cpu_pct": round(cpu, 1),
            "taux_charge_voix": round(voix, 3),
            "taux_charge_data": round(data, 3),
            "nb_utilisateurs_actifs": users,
            "puissance_emission_dbm": round(puissance_emission, 1),
            "temperature_ambiante": weather["temperature_ambiante"],
            "humidite_relative_pct": weather["humidite_relative_pct"],
            "vitesse_vent_ms": weather["vitesse_vent_ms"],
            "rayonnement_solaire_wm2": weather["rayonnement_solaire_wm2"],
            "precipitation_mmh": weather["precipitation_mmh"],
            "pression_atmospherique_hpa": weather["pression_atmospherique_hpa"],
            "indice_uv": weather["indice_uv"],
            "efficacite_free_cooling": round(efficacite_free_cooling, 3),
            "est_ferie": int(est_ferie),
            "mois": month,
            "heure": hour,
            "jour_semaine": weekday,
            "est_weekend": est_weekend,
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # Add mode_operation and action columns (will be computed by decision/optimization services)
    for col in ["mode_operation", "priorite", "action_principale", "eco_potentiel_pct", "risque_qos",
                "action_proposee", "economie_estimee_kwh"]:
        if col not in df.columns:
            df[col] = None

    return df


def generate_realtime_dataset(
    stations: list[str],
    periods: int,
    anomaly_rate: float,
    seed: int,
    start_time: datetime | None = None,
    freq_minutes: int = 5,
) -> pd.DataFrame:
    """Generate a realistic realtime dataset for one or many stations."""
    frames = []
    for offset, station in enumerate(stations):
        frames.append(
            generate_realtime_station_data(
                station=station,
                periods=periods,
                anomaly_rate=anomaly_rate,
                seed=seed + offset,
                start_time=start_time,
                freq_minutes=freq_minutes,
            )
        )
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def next_capture_time(
    existing: pd.DataFrame | None,
    station: str,
    freq_minutes: int,
    now: datetime | None = None,
) -> datetime:
    """Return the next simulated capture time for one station."""
    base_now = (now or datetime.now()).replace(second=0, microsecond=0)
    if (
        existing is None
        or existing.empty
        or "station_id" not in existing.columns
        or "timestamp" not in existing.columns
    ):
        return base_now

    station_rows = existing[existing["station_id"].astype(str) == str(station)]
    if station_rows.empty:
        return base_now

    last_ts = pd.to_datetime(station_rows["timestamp"], errors="coerce").dropna()
    if last_ts.empty:
        return base_now
    return last_ts.max().to_pydatetime().replace(second=0, microsecond=0) + timedelta(minutes=int(freq_minutes))


def generate_realtime_capture(
    stations: list[str],
    existing: pd.DataFrame | None = None,
    anomaly_rate: float = 0.08,
    seed: int = 42,
    freq_minutes: int = 5,
    now: datetime | None = None,
) -> pd.DataFrame:
    """Generate exactly one new realtime point per station, using station-local clocks."""
    unique_stations = list(dict.fromkeys(str(station) for station in stations if str(station).strip()))
    frames = []
    for offset, station in enumerate(unique_stations):
        station_start = next_capture_time(existing, station, freq_minutes, now=now)
        frames.append(
            generate_realtime_station_data(
                station=station,
                periods=1,
                anomaly_rate=anomaly_rate,
                seed=int(seed) + offset,
                start_time=station_start,
                freq_minutes=freq_minutes,
            )
        )
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def append_realtime_capture(existing: pd.DataFrame | None, capture: pd.DataFrame) -> pd.DataFrame:
    """Append a capture to an existing stream and keep one row per station/timestamp."""
    if capture.empty:
        return existing.copy().reset_index(drop=True) if isinstance(existing, pd.DataFrame) else pd.DataFrame()
    if isinstance(existing, pd.DataFrame) and not existing.empty:
        result = pd.concat([existing, capture], ignore_index=True)
    else:
        result = capture.copy()
    if {"station_id", "timestamp"}.issubset(result.columns):
        result["timestamp"] = pd.to_datetime(result["timestamp"], errors="coerce")
        result = result.sort_values(["station_id", "timestamp"]).drop_duplicates(
            ["station_id", "timestamp"], keep="last"
        )
    return result.reset_index(drop=True)
