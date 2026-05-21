"""Health check script for BTS EMS Dashboard."""

import sys
import sqlite3
from pathlib import Path

from config.settings import settings


def check_health():
    # 1. Check if database is accessible
    project_root = Path(__file__).resolve().parent
    db_path = settings.DB_PATH if settings.DB_PATH.is_absolute() else project_root / settings.DB_PATH
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception as e:
        print(f"CRITICAL: Database unreachable: {e}")
        return False

    # 2. Check for critical artifacts
    artifacts_dir = settings.OUTPUTS_DIR if settings.OUTPUTS_DIR.is_absolute() else project_root / settings.OUTPUTS_DIR
    if not artifacts_dir.exists():
        print(f"WARNING: Artifacts directory missing: {artifacts_dir}")
        # Not strictly critical for start, but important

    print("OK: System healthy")
    return True


if __name__ == "__main__":
    if check_health():
        sys.exit(0)
    else:
        sys.exit(1)
