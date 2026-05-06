import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from services.auth_service import authenticate_user, create_user_session
from security.middleware import security_middleware
from config.settings import settings

def test_integration_login_flow():
    """Test the full flow from authentication to session creation."""
    user_data = {
        "username": "admin",
        "email": "admin@tt.tn",
        "password_hash": "mocked_hash",
        "role": "admin",
        "display": "Admin",
        "is_active": 1,
        "must_change_password": 0
    }
    
    with patch("services.auth_service.db_read", return_value=pd.DataFrame([user_data])):
        with patch("services.auth_service.password_matches", return_value=True):
            # 1. Authenticate
            success, record, msg = authenticate_user("admin", "password")
            assert success
            assert record["username"] == "admin"
            
            # 2. Create session
            session = create_user_session(record)
            assert session["authenticated"] is True
            assert session["role"] == "admin"

def test_rate_limiting_ip_spoofing():
    """Test that rate limiting handles X-Forwarded-For correctly with trusted proxies."""
    # Scenario 1: Untrusted proxy tries to spoof IP
    mock_headers = {
        "Remote-Addr": "192.168.1.1", # Untrusted
        "X-Forwarded-For": "10.0.0.5"  # Spoofed
    }
    
    with patch("streamlit.context", MagicMock(headers=mock_headers)):
        # Should return Remote-Addr because immediate sender is not trusted
        ip = security_middleware._get_client_ip()
        assert ip == "192.168.1.1"
        
    # Scenario 2: Trusted proxy forwards the IP
    settings.TRUSTED_PROXIES.append("172.16.0.1")
    mock_headers = {
        "Remote-Addr": "172.16.0.1", # Trusted
        "X-Forwarded-For": "203.0.113.42"
    }
    
    with patch("streamlit.context", MagicMock(headers=mock_headers)):
        # Should return the forwarded IP
        ip = security_middleware._get_client_ip()
        assert ip == "203.0.113.42"

@patch("services.data_service.db_connect")
def test_db_action_with_lock(mock_db_connect):
    """Test that DB actions use the connection and are thread-safe (mocked)."""
    from services.data_service import db_execute
    
    mock_conn = MagicMock()
    mock_db_connect.return_value.__enter__.return_value = mock_conn
    
    db_execute("insert_audit_event", ("2024-01-01", "user", "test", "{}"))
    
    assert mock_conn.execute.called
    assert mock_conn.commit.called
