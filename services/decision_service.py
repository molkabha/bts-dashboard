from __future__ import annotations

import numpy as np

import pandas as pd

from config.settings import settings


class MoteurDecisionEnergie:

    MODES = {
        "ECO": {"priorite": 0, "color": "#059669"},
        "NORMAL": {"priorite": 1, "color": "#2563eb"},
        "ATTENTION": {"priorite": 2, "color": "#d97706"},
        "CRITIQUE": {"priorite": 3, "color": "#c8102e"},
    }

    ACTIONS = {
        "ECO": [
            "Activer sleep mode sur secteurs non sollicites",
            "Reduire puissance emission de 2 dBm",
            "Activer free cooling si conditions favorables",
        ],
        "NORMAL": ["Monitoring standard toutes les 15 min"],
        "ATTENTION": ["Augmenter frequence monitoring et preparer basculement"],
        "CRITIQUE": ["Alerte immediate - intervention NOC prioritaire"],
    }

    def __init__(self, seuils: dict | None = None):

        self.seuils = {
            "eco_score": 0.25,
            "critique_score": 0.6,
            "eco_cpu": 50.0,
            "critique_ecart": 30.0,
            "eco_heure_debut": 0,
            "eco_heure_fin": 6,
            "qos": float(settings.QOS_SEUIL_DEFAULT),
        }

        if seuils:

            self.seuils.update(seuils)

    def risque_qos(self, score_qos: float) -> str:

        if score_qos >= 0.8:

            return "Faible"

        if score_qos >= self.seuils["qos"]:

            return "Modere"

        return "Critique"

    def decider_mode(self, row: pd.Series) -> dict:

        score = float(row.get("anomalie_score_ensemble", 0) or 0)

        ecart = abs(float(row.get("ecart_pct", 0) or 0))

        cpu = float(row.get("charge_cpu_pct", 50) or 50)

        heure = int(row.get("heure", 12) or 12)

        votes = int(row.get("nb_votes_anomalie", 0) or 0)

        score_qos_raw = row.get("score_qos", 1)

        score_qos = (
            1.0
            if pd.isna(score_qos_raw)
            else float(score_qos_raw if score_qos_raw != "" else 1)
        )

        qos_ok = int(
            row.get("optimisation_qos_autorisee", score_qos >= self.seuils["qos"])
        )

        if score > self.seuils["critique_score"] or votes >= 5:

            mode = "CRITIQUE"

        elif ecart > self.seuils["critique_ecart"] or (
            score > self.seuils["eco_score"] and votes >= 2
        ):

            mode = "ATTENTION"

        elif (
            score < self.seuils["eco_score"]
            and cpu < self.seuils["eco_cpu"]
            and (
                self.seuils["eco_heure_debut"] <= heure <= self.seuils["eco_heure_fin"]
            )
            and (qos_ok == 1)
        ):

            mode = "ECO"

        else:

            mode = "NORMAL"

        return {
            "mode_operation": mode,
            "priorite": self.MODES[mode]["priorite"],
            "action_principale": self.ACTIONS[mode][0],
            "eco_potentiel_pct": 20 if mode == "ECO" else 0,
            "risque_qos": self.risque_qos(score_qos),
        }

    def appliquer_sur_dataset(self, df_in: pd.DataFrame) -> pd.DataFrame:

        df = df_in.copy()

        if df.empty:

            for col in [
                "mode_operation",
                "priorite",
                "action_principale",
                "eco_potentiel_pct",
                "risque_qos",
            ]:

                df[col] = []

            return df

        score = pd.to_numeric(
            pd.Series(df.get("anomalie_score_ensemble", 0), index=df.index),
            errors="coerce",
        ).fillna(0)

        ecart = (
            pd.to_numeric(
                pd.Series(df.get("ecart_pct", 0), index=df.index), errors="coerce"
            )
            .abs()
            .fillna(0)
        )

        cpu = pd.to_numeric(
            pd.Series(df.get("charge_cpu_pct", 50), index=df.index), errors="coerce"
        ).fillna(50)

        heure = (
            pd.to_numeric(
                pd.Series(df.get("heure", 12), index=df.index), errors="coerce"
            )
            .fillna(12)
            .astype(int)
        )

        votes = (
            pd.to_numeric(
                pd.Series(df.get("nb_votes_anomalie", 0), index=df.index),
                errors="coerce",
            )
            .fillna(0)
            .astype(int)
        )

        score_qos = pd.to_numeric(
            pd.Series(df.get("score_qos", 1), index=df.index), errors="coerce"
        ).fillna(1)

        qos_val = df.get("optimisation_qos_autorisee", score_qos >= self.seuils["qos"])

        qos_ok = (
            pd.to_numeric(pd.Series(qos_val, index=df.index), errors="coerce")
            .fillna(0)
            .astype(int)
        )

        critique = (score > self.seuils["critique_score"]) | (votes >= 5)

        attention = (ecart > self.seuils["critique_ecart"]) | (
            score > self.seuils["eco_score"]
        ) & (votes >= 2)

        eco = (
            (score < self.seuils["eco_score"])
            & (cpu < self.seuils["eco_cpu"])
            & heure.between(
                self.seuils["eco_heure_debut"], self.seuils["eco_heure_fin"]
            )
            & (qos_ok == 1)
        )

        modes = np.select(
            [critique, attention, eco],
            ["CRITIQUE", "ATTENTION", "ECO"],
            default="NORMAL",
        )

        df["mode_operation"] = modes

        df["priorite"] = pd.Series(modes, index=df.index).map(
            lambda mode: self.MODES[mode]["priorite"]
        )

        df["action_principale"] = pd.Series(modes, index=df.index).map(
            lambda mode: self.ACTIONS[mode][0]
        )

        df["eco_potentiel_pct"] = np.where(df["mode_operation"].eq("ECO"), 20, 0)

        df["risque_qos"] = np.select(
            [score_qos >= 0.8, score_qos >= self.seuils["qos"]],
            ["Faible", "Modere"],
            default="Critique",
        )

        return df
