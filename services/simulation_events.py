from __future__ import annotations

from typing import Any

import pandas as pd

from config.settings import settings

from services.data_service import resolve_nb2_seuil_ensemble, resolve_nb3_seuils_decision, resolve_qos_seuil

from services.nb_metrics import effective_economie_kwh

from ui.formatting import is_no_named_action, resolve_row_action


def _nb3_seuils() -> dict:

    seuils = resolve_nb3_seuils_decision()

    qos_seuil, _ = resolve_qos_seuil()

    merged = {
        "eco_score": 0.25,
        "critique_score": 0.6,
        "critique_ecart": 30.0,
        "qos": qos_seuil if qos_seuil is not None else float(settings.QOS_SEUIL_DEFAULT),
    }

    for key, value in seuils.items():

        try:

            if value not in (None, ""):

                merged[str(key)] = float(value)

        except (TypeError, ValueError):

            continue

    return merged


def _qos_seuil() -> float:

    return float(_nb3_seuils().get("qos", settings.QOS_SEUIL_DEFAULT))


def _anomaly_seuil(scale: float = 1.0) -> float | None:

    seuil, _ = resolve_nb2_seuil_ensemble()

    if seuil is None:

        return None

    if scale <= 0:

        scale = 1.0

    return float(seuil) / scale


def alert_ref(row: dict[str, Any]) -> str:

    ts = row.get("timestamp")

    station = str(row.get("station_id", ""))

    kind = str(row.get("type", "alert"))

    return f"{station}|{ts}|{kind}"


def classify_tick_rows(
    df: pd.DataFrame, *, anomaly_sensitivity: float = 1.0
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:

    if df.empty:

        return ([], [])

    seuil = _anomaly_seuil(anomaly_sensitivity)

    qos_seuil = _qos_seuil()

    nb3_seuils = _nb3_seuils()

    critique_ecart = float(nb3_seuils.get("critique_ecart", 30.0))

    critique_score = float(nb3_seuils.get("critique_score", 0.6))

    alerts: list[dict[str, Any]] = []

    decisions: list[dict[str, Any]] = []

    eco_series = effective_economie_kwh(df)

    for i, (_, row) in enumerate(df.iterrows()):

        ts = row.get("timestamp")

        station = str(row.get("station_id", ""))

        score = float(row.get("anomalie_score_ensemble") or 0)

        qos = float(row.get("score_qos") or 0)

        mode = str(row.get("mode_operation", "NORMAL"))

        action = resolve_row_action(row, prefer_rl=True)

        action_expert = resolve_row_action(row, prefer_rl=False)

        eco = float(eco_series.iloc[i]) if i < len(eco_series) else 0.0

        ecart = float(row.get("ecart_pct") or 0)

        has_named_action = not is_no_named_action(
            row.get("action_proposee")
            or row.get("action_rl")
            or row.get("action_principale")
        )

        if mode == "CRITIQUE":

            item = {
                "timestamp": ts,
                "station_id": station,
                "severity": "CRITIQUE",
                "type": "mode_critique",
                "message": f"Mode CRITIQUE — {action}. Anomalie {score:.2f}, QoS {qos:.2f}.",
                "score_anomalie": score,
                "score_qos": qos,
                "mode": mode,
            }

            item["alert_ref"] = alert_ref(item)

            alerts.append(item)

        elif abs(ecart) >= critique_ecart and qos >= qos_seuil:

            severity = "CRITIQUE" if mode == "CRITIQUE" else "ATTENTION"

            direction = "au-dessus" if ecart > 0 else "en-dessous"

            item = {
                "timestamp": ts,
                "station_id": station,
                "severity": severity,
                "type": "ecart_conso",
                "message": f"Ecart {ecart:+.1f} % vs LightGBM ({direction} du predit). Action : {action}.",
                "score_anomalie": score,
                "score_qos": qos,
                "mode": mode,
            }

            item["alert_ref"] = alert_ref(item)

            alerts.append(item)

        elif (
            seuil is not None
            and score >= seuil
            and (qos >= qos_seuil)
            and (not has_named_action)
        ):

            severity = (
                "CRITIQUE"
                if mode == "CRITIQUE" or score >= critique_score
                else "ATTENTION"
            )

            item = {
                "timestamp": ts,
                "station_id": station,
                "severity": severity,
                "type": "anomalie_sans_action",
                "message": f"Anomalie detectee (score {score:.2f}) — QoS stable ({qos:.2f}). Aucune action automatique.",
                "score_anomalie": score,
                "score_qos": qos,
                "mode": mode,
            }

            item["alert_ref"] = alert_ref(item)

            alerts.append(item)

        elif seuil is not None and score >= seuil and (qos < qos_seuil):

            item = {
                "timestamp": ts,
                "station_id": station,
                "severity": "CRITIQUE",
                "type": "qos_risque",
                "message": f"Anomalie (score {score:.2f}) avec QoS degrade ({qos:.2f}). Surveillance prioritaire.",
                "score_anomalie": score,
                "score_qos": qos,
                "mode": mode,
            }

            item["alert_ref"] = alert_ref(item)

            alerts.append(item)

        journal_action = (
            action_expert
            if not is_no_named_action(row.get("action_proposee"))
            else action
        )

        if has_named_action and str(journal_action).strip().lower() not in {
            "maintien",
            "maintien_conso",
            "—",
        }:

            detail = f"{journal_action}"

            if eco > 0.01:

                detail += f" — economie estimee {eco:.2f} kWh"

            elif mode != "NORMAL":

                detail += f" — mode {mode}"

            decisions.append(
                {
                    "timestamp": ts,
                    "station_id": station,
                    "mode": mode,
                    "action": journal_action,
                    "economie_kwh": eco,
                    "message": detail,
                }
            )

        elif eco > 0.05 and mode in {"ECO", "ATTENTION", "CRITIQUE"}:

            decisions.append(
                {
                    "timestamp": ts,
                    "station_id": station,
                    "mode": mode,
                    "action": journal_action,
                    "economie_kwh": eco,
                    "message": f"{journal_action} — economie estimee {eco:.2f} kWh (mode {mode})",
                }
            )

    return (alerts, decisions)


def merge_event_log(
    existing: list[dict], new_items: list[dict], max_items: int = 300
) -> list[dict]:

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


def filter_events(
    events: list[dict],
    *,
    station: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    current_hour_only: bool = False,
    current_ts: pd.Timestamp | None = None,
) -> list[dict]:

    out = list(events or [])

    if station and str(station).strip().lower() not in {"toutes", "none", "nan", ""}:

        out = [e for e in out if str(e.get("station_id")) == str(station)]

    if severity and severity != "Toutes":

        out = [e for e in out if str(e.get("severity")) == severity]

    if event_type and event_type != "Toutes":

        out = [e for e in out if str(e.get("type")) == event_type]

    if current_hour_only and current_ts is not None:

        ts = pd.Timestamp(current_ts)

        out = [e for e in out if pd.Timestamp(e.get("timestamp")) == ts]

    return out


def persist_alert_ack(
    user: str, station_id: str, alert_ref_id: str, verdict: str, comment: str = ""
) -> None:

    from datetime import datetime

    from services.data_service import db_execute, init_db

    init_db()

    db_execute(
        "insert_alert_decision",
        (
            datetime.now().isoformat(timespec="seconds"),
            user,
            station_id,
            alert_ref_id,
            verdict,
            comment or "",
        ),
    )
