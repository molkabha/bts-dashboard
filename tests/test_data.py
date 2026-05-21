from pathlib import Path
from data.loader import read_parquet_fast
from config.settings import ROOT
from services import data_service


def test_read_parquet_fast_returns_empty_frame_for_missing_file():
    df = read_parquet_fast(Path("missing-file.parquet"))

    assert df.empty


def test_active_dataset_path_uses_module_root_for_relative_setting(monkeypatch):
    active = ROOT / "tmp_active_dataset_for_test.parquet"
    active.write_text("placeholder", encoding="utf-8")
    try:
        monkeypatch.setattr(data_service, "db_scalar", lambda *args, **kwargs: active.name)
        assert data_service.active_dataset_path() == active
    finally:
        active.unlink(missing_ok=True)
