"""Stubs + decision helpers for unpickling pipeline_inference.joblib (NB3 notebook classes)."""

from __future__ import annotations

import numpy as np
import pandas as pd


class _PickleStub:
    """Accept any pickled state from the NB3 notebook."""

    def __setstate__(self, state: object) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)


class MoteurDecisionEnergie(_PickleStub):
    qos_seuil: float = 0.6


class StrategieOptimisation(_PickleStub):
    qos_seuil: float = 0.6


def apply_nb3_decisions(
    df: pd.DataFrame,
    *,
    qos_seuil: float = 0.6,
    env_rl_meta: dict | None = None,
    anomaly_seuil: float = 0.15,
) -> pd.DataFrame:
    """NB3-style modes/actions from scores QoS / anomalie (fallback when moteur code is absent)."""
    if df.empty:
        return df
    out = df.copy()
    meta = env_rl_meta or {}
    actions = meta.get("actions") or {
        0: "aucune_action",
        1: "sleep_mode_secteur",
        2: "reduction_puissance",
        3: "free_cooling",
        4: "eco_calendaire",
    }
    eco_frac = meta.get("eco_fraction") or {0: 0.0, 1: 0.2, 2: 0.08, 3: 0.15, 4: 0.12}
    qos_min = meta.get("qos_min") or {}

    modes, actions_out, actions_rl, eco_est, eco_rl = [], [], [], [], []
    for _, row in out.iterrows():
        score = float(row.get("anomalie_score_ensemble") or 0)
        qos = float(row.get("score_qos") or 0)
        heure = int(row.get("heure") or 0)
        conso = float(row.get("consommation_kwh") or 0)
        ecart = float(row.get("ecart_pct") or 0)

        mode = "NORMAL"
        action = str(actions.get(0, "aucune_action"))
        rl_action = action
        eco = 0.0

        if score >= anomaly_seuil * 2.2 and qos < qos_seuil:
            mode, action = "CRITIQUE", "alerte_qos"
        elif score >= anomaly_seuil and qos >= qos_seuil:
            mode, action = "ATTENTION", "aucune_action"
        elif score >= anomaly_seuil and qos < qos_seuil:
            mode, action = "CRITIQUE", "intervention"
        elif heure <= 5 or heure >= 23:
            mode, action, rl_action = "ECO", "reduction_puissance", str(actions.get(2, "reduction_puissance"))
            eco = min(conso * float(eco_frac.get(2, 0.08)), conso)
        elif 10 <= heure <= 16 and score < anomaly_seuil * 0.6:
            mode, action, rl_action = "ECO", "mode_eco", str(actions.get(4, "eco_calendaire"))
            eco = min(conso * float(eco_frac.get(4, 0.12)), conso)
        elif abs(ecart) > 25 and qos >= qos_seuil:
            mode, action = "ATTENTION", "reduction_puissance"
            eco = min(conso * 0.06, conso)

        rl_qos = qos_min.get(2)
        if rl_qos is not None and qos < float(rl_qos) and action != "intervention":
            rl_action = str(actions.get(0, "aucune_action"))
            eco = 0.0

        modes.append(mode)
        actions_out.append(action)
        actions_rl.append(rl_action)
        eco_est.append(eco)
        eco_rl.append(eco * 0.95)

    out["mode_operation"] = modes
    out["action_proposee"] = actions_out
    out["action_rl"] = actions_rl
    out["action_principale"] = actions_out
    out["economie_estimee_kwh"] = eco_est
    out["economie_rl_kwh"] = eco_rl
    out["source_decision_nb3"] = "pipeline_nb3"
    return out
