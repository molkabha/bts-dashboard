import pytest
import pandas as pd
import numpy as np
from datetime import date, datetime
from unittest.mock import patch
from utils.security import password_hash, password_matches
from services.data_service import apply_time_filters
from services.auth_service import authenticate_user

def test_password_security_roundtrip():
    """Test that passwords can be hashed and verified correctly."""
    pwd = "TestPassword123!"
    h = password_hash(pwd)
    assert h.startswith("pbkdf2_sha256$")
    assert password_matches(pwd, h)
    assert not password_matches("WrongPassword", h)
    assert not password_matches("", h)

def test_apply_time_filters_empty_df():
    """Test that filters handle empty DataFrames gracefully."""
    df = pd.DataFrame()
    filtered = apply_time_filters(df, {"date_range": (date(2024, 1, 1), date(2024, 1, 31))})
    assert filtered.empty

def test_apply_time_filters_logic():
    """Test time filtering logic on a sample dataset."""
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-01-01 10:00", "2024-01-02 10:00", "2024-02-01 10:00"]),
        "heure": [10, 10, 10],
        "mois": [1, 1, 2]
    })
    
    # Filter by date range
    filters = {"date_range": (date(2024, 1, 1), date(2024, 1, 2))}
    filtered = apply_time_filters(df, filters)
    assert len(filtered) == 2
    
    # Filter by month
    filters = {"months": [2]}
    filtered = apply_time_filters(df, filters)
    assert len(filtered) == 1
    assert filtered.iloc[0]["mois"] == 2

@patch("services.auth_service.db_read")
def test_auth_logic_mocked(mock_db_read):
    """Test authentication logic by mocking database reads."""
    # Mocking db_read to return a user record
    user_data = {
        "username": "valid_user",
        "email": "valid@example.com",
        "password_hash": password_hash("secret123"),
        "role": "admin",
        "display": "Valid User",
        "is_active": 1,
        "must_change_password": 0
    }
    mock_db_read.return_value = pd.DataFrame([user_data])
    
    # Test valid login
    success, record, msg = authenticate_user("valid_user", "secret123")
    assert success
    assert record["username"] == "valid_user"
    
    # Test invalid password
    success, _, _ = authenticate_user("valid_user", "wrong_pwd")
    assert not success
    
    # Test non-existent user
    mock_db_read.return_value = pd.DataFrame()
    success, _, _ = authenticate_user("unknown", "any")
    assert not success
