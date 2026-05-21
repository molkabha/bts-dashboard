"""Streamlit entry point for the dashboard package."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Ensure imports like `from ui...` and `from services...` work when this file
# is executed from outside the project root.
PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

# Load environment variables from .env file (SMTP, secrets, etc.) BEFORE
# importing any module that reads os.getenv at import time.
# Pydantic Settings only loads declared fields; it does not propagate other
# variables (e.g. BTS_SMTP_*) into os.environ, so we must load them ourselves.
try:
    from dotenv import load_dotenv

    ENV_PATH = PACKAGE_ROOT / ".env"
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH, override=False)
except ImportError:
    # python-dotenv not installed; rely on the OS environment instead.
    pass


st.set_page_config(
    page_title="BTS EMS - Tunisie Telecom",
    page_icon="TT",
    layout="wide",
    initial_sidebar_state="expanded",
)


from ui.dashboard import main  # noqa: E402  # imported after path/env/page setup


if __name__ == "__main__":
    main()
