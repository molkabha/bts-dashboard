from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any, Callable
from unittest.mock import patch

import pytest


@dataclass
class _MiniMocker:
    _finalizers: list[Callable[[], None]]

    def patch(self, target: str, *args: Any, **kwargs: Any) -> Any:
        p = patch(target, *args, **kwargs)
        started = p.start()
        self._finalizers.append(p.stop)
        return started


@pytest.fixture
def mocker(request: pytest.FixtureRequest) -> _MiniMocker:
    finalizers: list[Callable[[], None]] = []

    def _cleanup() -> None:
        # reverse order like unittest does
        for f in reversed(finalizers):
            with contextlib.suppress(Exception):
                f()

    request.addfinalizer(_cleanup)
    return _MiniMocker(_finalizers=finalizers)
