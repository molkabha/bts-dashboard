"""Authentication and user management service."""

from __future__ import annotations

import secrets
import string
import time
from datetime import datetime
from typing import Optional

from utils.security import password_hash, password_matches
from services.data_service import db_read, db_execute, log_event
from security.middleware import security_middleware

# Rate limiting configuration
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300   # 5 minutes


def is_rate_limited(username: str) -> tuple[bool, Optional[int]]:
    """Check if a username or IP is rate limited due to too many failed attempts."""
    return security_middleware.is_login_locked_out(username, MAX_LOGIN_ATTEMPTS, LOGIN_WINDOW_SECONDS)


def record_failed_attempt(username: str) -> None:
    """Record a failed login attempt for rate limiting."""
    security_middleware.record_login_failure(username)


def clear_login_attempts(username: str) -> None:
    """Clear login attempts for a user/IP after successful login."""
    security_middleware.clear_login_lockout(username)


def get_user_record(username: str) -> Optional[dict]:
    """Get user record from SQLite DB."""
    username = str(username or "").strip().lower()
    if not username:
        return None
    df = db_read("get_user_by_username_or_email", (username, username))
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def authenticate_user(
    username: str, password: str, expected_role: Optional[str] = None
) -> tuple[bool, Optional[dict], str]:
    """Authenticate a user with username and password."""
    username = str(username or "").strip()
    password = str(password or "")
    if not username or not password:
        return False, None, "Identifiant ou mot de passe incorrect."

    limited, remaining = is_rate_limited(username)
    if limited:
        return False, None, f"Trop de tentatives échouées. Réessayez dans {remaining} secondes."

    rec = get_user_record(username)
    if not rec:
        record_failed_attempt(username)
        return False, None, "Identifiant ou mot de passe incorrect."

    if expected_role and rec["role"] != expected_role:
        return False, None, "Accès non autorisé pour ce rôle."

    if not rec.get("is_active"):
        return False, None, "Compte désactivé."

    if not password_matches(password, rec["password_hash"]):
        record_failed_attempt(username)
        return False, None, "Identifiant ou mot de passe incorrect."

    clear_login_attempts(username)
    return True, rec, "Authentification réussie."


def create_user_session(user_record: dict) -> dict:
    """Create a user session from user record."""
    session_id = secrets.token_urlsafe(24)
    now = datetime.now().isoformat(timespec="seconds")
    db_execute("insert_user_session", (session_id, user_record["username"], now, now))
    return {
        "authenticated": True,
        "role": user_record["role"],
        "user": user_record["username"],
        "username": user_record["username"],
        "display": user_record["display"],
        "email": user_record.get("email", ""),
        "must_change_password": bool(user_record.get("must_change_password", False)),
        "_session_start": time.time(),
        "session_id": session_id,
    }


def update_user_password(username: str, new_password: str, must_change_password: int = 0) -> None:
    """Update a user's password in the SQLite DB."""
    db_execute("update_password", (password_hash(new_password), must_change_password, username))
    log_event("password_updated", {"user": username})


def reset_user_password(username_or_email: str) -> tuple[bool, str]:
    """Send a temporary password to an active user and force password change."""
    rec = get_user_record(username_or_email)
    if not rec:
        return False, "Aucun compte actif ne correspond à ce courriel ou identifiant."
    if not rec.get("is_active"):
        return False, "Compte désactivé."

    email = str(rec.get("email") or "").strip()
    if not email:
        return False, "Aucun courriel n'est associé à ce compte."

    temp_password = generate_temp_password()
    from services.notification_service import send_account_password_email

    username = str(rec["username"])
    old_hash = str(rec.get("password_hash") or "")
    old_must_change = int(bool(rec.get("must_change_password", False)))
    db_execute("update_password", (password_hash(temp_password), 1, username))

    ok, message = send_account_password_email(
        email,
        str(rec.get("display") or username or ""),
        username or email,
        temp_password,
    )
    if not ok:
        db_execute("restore_password", (old_hash, old_must_change, username))
        return False, message

    log_event("password_reset_requested", {"user": username})
    return True, "Un mot de passe temporaire a été envoyé par courriel."


def generate_temp_password(length: int = 12) -> str:
    """Generate a temporary password that meets complexity requirements."""
    alphabet = string.ascii_letters + string.digits + "!@#$%?"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%?" for c in password)
        ):
            return password
