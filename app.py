from __future__ import annotations

import sys

from pathlib import Path

import streamlit as st

PACKAGE_ROOT = Path(__file__).resolve().parent

if str(PACKAGE_ROOT) not in sys.path:

    sys.path.insert(0, str(PACKAGE_ROOT))

try:

    from dotenv import load_dotenv

    ENV_PATH = PACKAGE_ROOT / ".env"

    if ENV_PATH.exists():

        load_dotenv(dotenv_path=ENV_PATH, override=False)

except ImportError:

    pass

st.set_page_config(
    page_title="BTS EMS — Tunisie Telecom",
    page_icon="TT",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui.dashboard import main

if __name__ == "__main__":

    main()
