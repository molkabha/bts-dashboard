from __future__ import annotations

import numpy as np

import pandas as pd

from config.settings import settings


class StrategieOptimisation:

    ECO_SLEEP_PAR_TECHNO = {"2G": 0.062, "3G": 1.608, "4G": 1.845, "4G+": 2.04}

    MAX_ECO_FRAC_DEFAULT = 0.42

    MAX_ECO_FRAC_SLEEP = float(settings.NB3_MAX_ECO_FRAC)

    def _col(self, df: pd.DataFrame, col: str, default):

        if col in df.columns:

            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):

                return df[col].fillna(default)

            return pd.to_numeric(df[col], errors="coerce").fillna(default)

        return pd.Series(default, index=df.index)

    def appliquer(self, df_in: pd.DataFrame) -> pd.DataFrame:

        df = df_in.copy()

        qos_ok = self._col(df, "optimisation_qos_autorisee", 1)

        technologie = (
            df["technologie"].astype(str)
            if "technologie" in df.columns
            else pd.Series("4G", index=df.index)
        )

        heure = self._col(df, "heure", 12)

        conso = self._col(df, "consommation_kwh", 0)

        df["action_proposee"] = "monitoring_standard"

        df["economie_estimee_kwh"] = 0.0

        peut_sleep = (
            (qos_ok == 1)
            & heure.between(1, 5)
            & (self._col(df, "taux_charge_voix", 0) < 0.15)
            & (self._col(df, "taux_charge_data", 0) < 0.15)
            & (self._col(df, "score_qos", 1) > 0.8)
        )

        df.loc[peut_sleep, "action_proposee"] = "sleep_mode_secteur"

        sleep_ref = (
            technologie.loc[peut_sleep].map(self.ECO_SLEEP_PAR_TECHNO).fillna(0.5)
        )

        sleep_cap = conso.loc[peut_sleep] * self.MAX_ECO_FRAC_SLEEP

        df.loc[peut_sleep, "economie_estimee_kwh"] = np.minimum(
            sleep_ref.to_numpy(dtype=float), sleep_cap.to_numpy(dtype=float)
        )

        peut_reduire = (
            (qos_ok == 1)
            & technologie.isin(["4G", "4G+", "3G"])
            & (self._col(df, "puissance_emission_dbm", 43) > 40.5)
            & (self._col(df, "score_qos", 1) > 0.75)
            & (self._col(df, "charge_cpu_pct", 0) < 50)
            & ~peut_sleep
        )

        df.loc[peut_reduire, "action_proposee"] = "reduction_puissance"

        df.loc[peut_reduire, "economie_estimee_kwh"] = conso.loc[peut_reduire] * 0.08

        peut_free = (
            (self._col(df, "temperature_ambiante", 30) < 22)
            & (self._col(df, "vitesse_vent_ms", 0) > 3)
            & (self._col(df, "humidite_relative_pct", 50) < 75)
        )

        free_mask = peut_free & (df["action_proposee"] == "monitoring_standard")

        df.loc[free_mask, "action_proposee"] = "free_cooling"

        df.loc[free_mask, "economie_estimee_kwh"] = conso.loc[free_mask] * 0.15

        est_weekend = self._col(df, "est_weekend", 0)

        est_ferie = self._col(df, "est_ferie", 0)

        peut_eco_cal = (
            (qos_ok == 1)
            & ((est_weekend == 1) | (est_ferie == 1))
            & heure.between(2, 6)
            & (self._col(df, "score_qos", 1) > 0.8)
            & (self._col(df, "taux_charge_data", 0) < 0.13)
            & ~peut_sleep
            & ~peut_reduire
            & (df["action_proposee"] == "monitoring_standard")
        )

        df.loc[peut_eco_cal, "action_proposee"] = "eco_calendaire"

        df.loc[peut_eco_cal, "economie_estimee_kwh"] = conso.loc[peut_eco_cal] * 0.12

        alerte_2g = (
            (technologie == "2G")
            & (self._col(df, "taux_charge_voix", 0) > 0.8)
            & (self._col(df, "score_qos", 1) < float(settings.QOS_SEUIL_DEFAULT))
        )

        df.loc[alerte_2g, "action_proposee"] = "alerte_saturation_voix"

        df.loc[alerte_2g, "economie_estimee_kwh"] = 0.0

        critique = (self._col(df, "mode_operation", "") == "CRITIQUE") | (
            self._col(df, "anomalie_score_ensemble", 0) > 0.6
        )

        df.loc[critique, "action_proposee"] = "alerte_noc_prioritaire"

        df.loc[critique, "economie_estimee_kwh"] = 0.0

        eco = pd.to_numeric(df["economie_estimee_kwh"], errors="coerce").fillna(0.0)

        is_sleep = df["action_proposee"].eq("sleep_mode_secteur")

        max_frac = np.where(
            is_sleep, self.MAX_ECO_FRAC_SLEEP, self.MAX_ECO_FRAC_DEFAULT
        )

        df["economie_estimee_kwh"] = np.minimum(eco, conso * max_frac)

        return df
