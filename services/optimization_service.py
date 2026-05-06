from __future__ import annotations

import pandas as pd
from services.decision_service import MoteurDecisionEnergie

class StrategieOptimisation:
    ECO_SLEEP_PAR_TECHNO = {"2G": 0.062, "3G": 1.608, "4G": 1.845, "4G+": 2.040}

    def _col(self, df: pd.DataFrame, col: str, default):
        if col in df.columns:
            return df[col]
        return pd.Series(default, index=df.index)

    def appliquer(self, df_in: pd.DataFrame) -> pd.DataFrame:
        df = df_in.copy()
        qos_ok = self._col(df, "optimisation_qos_autorisee", 1)
        technologie = self._col(df, "technologie", "")
        df["action_proposee"] = "aucune_action"
        df["economie_estimee_kwh"] = 0.0

        peut_sleep = (
            (qos_ok == 1)
            & (self._col(df, "heure", 12).between(1, 5))
            & (self._col(df, "taux_charge_voix", 0) < 0.15)
            & (self._col(df, "taux_charge_data", 0) < 0.15)
            & (self._col(df, "score_qos", 1) > 0.80)
            & (self._col(df, "nb_secteurs_actifs", 2) > 1)
        )
        df.loc[peut_sleep, "action_proposee"] = "sleep_mode_secteur"
        df.loc[peut_sleep, "economie_estimee_kwh"] = technologie.loc[peut_sleep].map(self.ECO_SLEEP_PAR_TECHNO).fillna(0)

        peut_reduire = (
            (qos_ok == 1)
            & (technologie.isin(["4G", "4G+"]))
            & (self._col(df, "puissance_emission_dbm", 43) > 40.5)
            & (self._col(df, "score_qos", 1) > 0.75)
            & (self._col(df, "charge_cpu_pct", 0) < 50)
            & (self._col(df, "taux_charge_data", 0) < 0.60)
            & (~peut_sleep)
        )
        df.loc[peut_reduire, "action_proposee"] = "reduction_puissance"
        df.loc[peut_reduire, "economie_estimee_kwh"] = self._col(df, "consommation_kwh", 0) * 0.08

        peut_free = (
            (self._col(df, "temperature_ambiante", 30) < 22)
            & (self._col(df, "vitesse_vent_ms", 0) > 3)
            & (self._col(df, "humidite_relative_pct", 50) < 75)
            & (self._col(df, "efficacite_free_cooling", 0) > 0.50)
        )
        df.loc[peut_free & (df["action_proposee"] == "aucune_action"), "action_proposee"] = "free_cooling"
        df.loc[peut_free, "economie_estimee_kwh"] += self._col(df, "consommation_kwh", 0) * 0.15

        alerte_2g = (technologie == "2G") & (self._col(df, "taux_charge_voix", 0) > 0.80) & (self._col(df, "score_qos", 1) < 0.70)
        df.loc[alerte_2g, "action_proposee"] = "alerte_saturation_voix"
        df.loc[alerte_2g, "economie_estimee_kwh"] = 0.0
        critique = (self._col(df, "mode_operation", "") == "CRITIQUE") | (self._col(df, "anomalie_score_ensemble", 0) > 0.60)
        df.loc[critique, "action_proposee"] = "alerte_noc_prioritaire"
        df.loc[critique, "economie_estimee_kwh"] = 0.0
        return df
