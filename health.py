"""Health check script for BTS EMS Dashboard."""

import sys
import sqlite3
from pathlib import Path

def check_health():
    # 1. Check if database is accessible
    db_path = Path(__file__).resolve().parents[1] / "dashboard_ops.sqlite3"
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception as e:
        print(f"CRITICAL: Database unreachable: {e}")
        return False

    # 2. Check for critical artifacts
    artifacts_dir = Path(__file__).resolve().parents[1] / "NB3" / "output"
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
