"""Stubs for unpickling pipeline_inference.joblib (classes NB3 notebook)."""

from __future__ import annotations


class _PickleStub:
    """Accept any pickled state from the NB3 notebook."""

    def __setstate__(self, state: object) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)


class MoteurDecisionEnergie(_PickleStub):
    qos_seuil: float = 0.6


class StrategieOptimisation(_PickleStub):
    qos_seuil: float = 0.6
