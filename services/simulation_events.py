from __future__ import annotations

from typing import Any

import pandas as pd

from config.settings import settings
from services.data_service import resolve_nb2_seuil_ensemble
from services.nb_metrics import effective_economie_kwh
from ui.formatting import is_no_named_action, resolve_row_action


def _qos_seuil() -> float:
    return float(settings.QOS_SEUIL_DEFAULT)


def _anomaly_seuil() -> float:
    seuil, _ = resolve_nb2_seuil_ensemble()
    return float(seuil)


def classify_tick_rows(df: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if df.empty:
        return [], []

    seuil = _anomaly_seuil()
    qos_seuil = _qos_seuil()
    alerts: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    eco_series = effective_economie_kwh(df)

    for i, (_, row) in enumerate(df.iterrows()):
        ts = row.get("timestamp")
        station = str(row.get("station_id", ""))
        score = float(row.get("anomalie_score_ensemble") or 0)
        qos = float(row.get("score_qos") or 0)
        mode = str(row.get("mode_operation", "NORMAL"))
        action_raw = row.get("action_rl") or row.get("action_proposee") or row.get("action_principale")
        action = resolve_row_action(row, prefer_rl=True)
        eco = float(eco_series.iloc[i]) if i < len(eco_series) else 0.0

        if score >= seuil and qos >= qos_seuil and is_no_named_action(action_raw):
            severity = "CRITIQUE" if score >= seuil * 2.4 else "ATTENTION"
            alerts.append({
                "timestamp": ts,
                "station_id": station,
                "severity": severity,
                "type": "anomalie_sans_action",
                "message": (
                    f"Anomalie detectee (score {score:.2f}) — QoS stable ({qos:.2f}). "
                    "Aucune action automatique."
                ),
                "score_anomalie": score,
                "score_qos": qos,
                "mode": mode,
            })
        elif score >= seuil and qos < qos_seuil:
            alerts.append({
                "timestamp": ts,
                "station_id": station,
                "severity": "CRITIQUE",
                "type": "qos_risque",
                "message": (
                    f"Anomalie (score {score:.2f}) avec QoS degrade ({qos:.2f}). "
                    "Surveillance prioritaire."
                ),
                "score_anomalie": score,
                "score_qos": qos,
                "mode": mode,
            })

        if not is_no_named_action(action_raw) and str(action_raw).strip().lower() not in {"maintien", "maintien_conso"}:
            decisions.append({
                "timestamp": ts,
                "station_id": station,
                "mode": mode,
                "action": action,
                "economie_kwh": eco,
                "message": f"{action} — economie estimee {eco:.2f} kWh",
            })
        elif eco > 0.01 and mode in {"ECO", "ATTENTION", "CRITIQUE"}:
            decisions.append({
                "timestamp": ts,
                "station_id": station,
                "mode": mode,
                "action": action,
                "economie_kwh": eco,
                "message": f"{action} — economie estimee {eco:.2f} kWh",
            })

    return alerts, decisions


def merge_event_log(existing: list[dict], new_items: list[dict], max_items: int = 200) -> list[dict]:
    combined = list(existing or []) + list(new_items or [])
    return combined[-max_items:]


def events_to_dataframe(events: list[dict]) -> pd.DataFrame:
    if not events:
        return pd.DataFrame()
    out = pd.DataFrame(events)
    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
        out = out.sort_values("timestamp", ascending=False)
    return out
