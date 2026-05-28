from __future__ import annotations

import pandas as pd


class _PickleStub:

    def __setstate__(self, state: object) -> None:

        if isinstance(state, dict):

            self.__dict__.update(state)


class MoteurDecisionEnergie(_PickleStub):

    qos_seuil: float = 0.6

    def appliquer_sur_dataset(self, df_in: pd.DataFrame) -> pd.DataFrame:

        from services.decision_service import MoteurDecisionEnergie as _Real

        seuils = getattr(self, "seuils", None) or self.__dict__.get("seuils")

        return _Real(seuils).appliquer_sur_dataset(df_in)


class StrategieOptimisation(_PickleStub):

    qos_seuil: float = 0.6

    def appliquer(self, df_in: pd.DataFrame) -> pd.DataFrame:

        from services.optimization_service import StrategieOptimisation as _Real

        return _Real().appliquer(df_in)
