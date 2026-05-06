"""Security tests for the dashboard application."""

from __future__ import annotations

import pytest

# Fix: imports use the actual package structure (no "dashboard_app." prefix).
# The project root is added to sys.path by conftest.py / pytest.ini so bare
# module names (services.*, utils.*) resolve correctly.
from services.auth_service import (
    authenticate_user,
    create_user_session,
    generate_temp_password,
    is_rate_limited,
    record_failed_attempt,
    update_user_password,
)
from utils.validators import (
    StationDataValidator,
    UserInputValidator,
    pattern_match,
    validate_api_input,
)
from utils.error_handler import (
    AppError,
    ErrorCode,
)


class TestAuthentication:
    """Tests for authentication functions."""

    def test_authenticate_user_success(self, mocker):
        """Test successful authentication."""
        mocker.patch("services.auth_service.get_user_record", return_value={
            "username": "testuser",
            "password_hash": "pbkdf2_sha256$260000$abc123$def456",
            "role": "admin",
            "display": "Test User",
            "is_active": True,
            "must_change_password": False,
        })
        mocker.patch("services.auth_service.password_matches", return_value=True)
        mocker.patch("services.auth_service.clear_login_attempts")

        success, user, message = authenticate_user("testuser", "password123")

        assert success is True
        assert user is not None
        assert "Authentification réussie" in message

    def test_authenticate_user_wrong_password(self, mocker):
        """Test authentication with wrong password."""
        mocker.patch("services.auth_service.get_user_record", return_value={
            "username": "testuser",
            "password_hash": "wrong_hash",
            "role": "admin",
            "display": "Test User",
            "is_active": True,
        })
        mocker.patch("services.auth_service.password_matches", return_value=False)
        mocker.patch("services.auth_service.record_failed_attempt")

        success, user, message = authenticate_user("testuser", "wrongpass")

        assert success is False
        assert user is None
        assert "incorrect" in message.lower()

    def test_authenticate_user_inactive(self, mocker):
        """Test authentication with inactive account."""
        mocker.patch("services.auth_service.get_user_record", return_value={
            "username": "testuser",
            "password_hash": "hash",
            "role": "admin",
            "display": "Test User",
            "is_active": False,
        })
        mocker.patch("services.auth_service.password_matches", return_value=True)

        success, user, message = authenticate_user("testuser", "password")

        assert success is False
        assert "désactiv" in message.lower()

    def test_rate_limiting(self, mocker):
        """Test rate limiting functionality."""
        # Mock security_middleware to simulate lockout
        mocker.patch("services.auth_service.security_middleware.is_login_locked_out", return_value=(True, 900))

        limited, remaining = is_rate_limited("testuser")

        assert limited is True
        assert remaining == 900

    def test_generate_temp_password(self):
        """Test temporary password generation."""
        password = generate_temp_password()

        assert len(password) == 12
        assert any(c.islower() for c in password)
        assert any(c.isupper() for c in password)
        assert any(c.isdigit() for c in password)

    def test_update_user_password(self, mocker):
        """Test password update calling DB execute."""
        mock_db = mocker.patch("services.auth_service.db_execute")
        update_user_password("testuser", "NewPass@123")
        assert mock_db.called


class TestInputValidation:
    """Tests for input validation."""

    def test_station_data_validator_valid(self):
        """Test valid station data."""
        data = {
            "station_id": "STATION001",
            "technologie": "4G",
            "gouvernorat": "Tunis",
            "type_zone": "Urbain",
            "latitude": 36.8,
            "longitude": 10.18,
            "consommation_kwh": 100.5,
            "score_qos": 0.85,
            "anomalie_score_ensemble": 0.2,
        }

        validator = StationDataValidator(**data)

        assert validator.station_id == "STATION001"
        assert validator.technologie == "4G"
        assert validator.gouvernorat == "Tunis"

    def test_station_data_validator_invalid_technology(self):
        """Test invalid technology raises ValueError."""
        with pytest.raises(ValueError):
            StationDataValidator(
                station_id="STATION001",
                technologie="6G",  # Invalid
                gouvernorat="Tunis",
                type_zone="Urbain",
                consommation_kwh=10.0,
            )

    def test_station_data_validator_invalid_gouvernorat(self):
        """Test invalid gouvernorat raises ValueError."""
        with pytest.raises(ValueError):
            StationDataValidator(
                station_id="STATION001",
                technologie="4G",
                gouvernorat="InvalidCity",
                type_zone="Urbain",
                consommation_kwh=10.0,
            )

    def test_sql_injection_detection(self):
        """Test SQL injection pattern detection."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "admin'--",
            "SELECT * FROM users",
        ]

        for value in malicious_inputs:
            assert UserInputValidator.validate_no_sql_injection(value) is False, \
                f"Expected injection detected for: {value!r}"

    def test_safe_input(self):
        """Test safe input passes validation."""
        safe_inputs = [
            "normal text",
            "station123",
            "Tunis city",
        ]

        for value in safe_inputs:
            assert UserInputValidator.validate_no_sql_injection(value) is True

    def test_xss_detection(self):
        """Test XSS pattern detection."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<img onload=evil()>",
        ]

        for value in malicious_inputs:
            assert UserInputValidator.validate_no_xss(value) is False, \
                f"Expected XSS detected for: {value!r}"

    def test_password_strength_valid(self):
        """Strong password passes validation."""
        ok, errors = UserInputValidator.validate_password_strength("Str0ng!Pass")
        assert ok is True
        assert errors == []

    def test_password_strength_too_short(self):
        """Short password fails validation."""
        ok, errors = UserInputValidator.validate_password_strength("Ab1!")
        assert ok is False
        assert any("8" in e for e in errors)
