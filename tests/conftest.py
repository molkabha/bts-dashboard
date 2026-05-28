from __future__ import annotations

import sys

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _clear_security_rate_limits():

    from security import middleware as mw

    mw._GLOBAL_RATE_LIMITS.clear()

    yield

    mw._GLOBAL_RATE_LIMITS.clear()
