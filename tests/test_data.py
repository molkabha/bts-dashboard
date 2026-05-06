from pathlib import Path
import pandas as pd
from data.loader import read_parquet_fast
from services.data_service import artifact_path
from utils.security import password_hash, password_matches


def test_read_parquet_fast_returns_empty_frame_for_missing_file():
    df = read_parquet_fast(Path("missing-file.parquet"))

    assert df.empty
