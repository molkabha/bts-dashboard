"""Stubs for unpickling pipeline_inference.joblib (classes NB3 notebook)."""

from __future__ import annotations

import pandas as pd


class _PickleStub:
    """Accept any pickled state from the NB3 notebook."""

    def __setstate__(self, state: object) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)


class MoteurDecisionEnergie(_PickleStub):
    """Délègue au moteur Python du dashboard si le joblib n'expose pas les methodes."""

    qos_seuil: float = 0.6

    def appliquer_sur_dataset(self, df_in: pd.DataFrame) -> pd.DataFrame:
        from services.decision_service import MoteurDecisionEnergie as _Real

        seuils = getattr(self, "seuils", None) or self.__dict__.get("seuils")
        return _Real(seuils).appliquer_sur_dataset(df_in)


class StrategieOptimisation(_PickleStub):
    """Délègue a la strategie d'optimisation du dashboard (regles expertes NB3)."""

    qos_seuil: float = 0.6

    def appliquer(self, df_in: pd.DataFrame) -> pd.DataFrame:
        from services.optimization_service import StrategieOptimisation as _Real

        return _Real().appliquer(df_in)
