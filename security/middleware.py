"""Security middleware for the dashboard application.

NOTE: This app uses Streamlit, not Flask.
All request-lifecycle hooks have been replaced with Streamlit-compatible
session-state helpers that can be called at the top of each page render.
"""

from __future__ import annotations

import functools
import hmac
import os
import secrets
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import streamlit as st

from config.settings import settings
from utils.error_handler import AppError, ErrorCode
from utils.logging_config import configure_application_logging

try:
    import redis
except ImportError:
    redis = None

# Module-level storage for rate limiting (fallback when Redis is disabled).
# WARNING: This storage is local to the current process and does not persist across restarts.
# In multi-process deployments, rate limits will not be synchronized between instances.
# Redis is MANDATORY for production (REDIS_ENABLED=True) to ensure reliable security.
_GLOBAL_RATE_LIMITS: Dict[str, list] = {}

class SecurityMiddleware:
    """Security helpers for Streamlit session processing."""

    def __init__(self, secret_key: Optional[str] = None):
        """Initialize security middleware."""
        self.secret_key = secret_key or settings.SECRET_KEY or secrets.token_hex(32)
        self.logger, _ = configure_application_logging("production")
        self.redis_client = None
        
        if settings.REDIS_ENABLED and redis:
            try:
                self.redis_client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD,
                    decode_responses=True
                )
                self.redis_client.ping()
            except Exception as e:
                self.logger.error("redis_connection_failed", error=str(e))
                self.redis_client = None

    def _get_client_ip(self) -> str:
        """Get the client's IP address with trusted proxy validation."""
        try:
            # Streamlit 1.34+
            headers = st.context.headers
            remote_addr = headers.get("Remote-Addr", "127.0.0.1")
            
            # If there's an X-Forwarded-For header, validate it
            if "X-Forwarded-For" in headers:
                # Check if the immediate sender is a trusted proxy
                if remote_addr in settings.TRUSTED_PROXIES:
                    return headers["X-Forwarded-For"].split(",")[0].strip()
            
            return remote_addr
        except Exception:
            return "unknown"

    def apply_security_headers(self):
        """
        Add security-related meta tags to the Streamlit UI.

        NOTE: Real HTTP security headers (CSP, HSTS, etc.) MUST be set at the 
        reverse proxy level (Nginx). See nginx.conf for details.
        """
        st.markdown(
            """
            <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
            </style>
            """,
            unsafe_allow_html=True
        )
    # ------------------------------------------------------------------
    # CSRF helpers
    # ------------------------------------------------------------------

    def generate_csrf_token(self) -> str:
        """Generate and store a CSRF token for the current session."""
        token = secrets.token_urlsafe(32)
        st.session_state["_csrf_token"] = token
        return token

    def validate_csrf_token(self, token: str, rotate: bool = False) -> bool:
        """Validate a submitted CSRF token and optionally rotate it."""
        stored = st.session_state.get("_csrf_token")
        if not stored:
            return False
        
        valid = hmac.compare_digest(stored, token)
        
        if rotate or settings.CSRF_ROTATE_TOKEN:
            self.generate_csrf_token()
            
        return valid

    # ------------------------------------------------------------------
    # Login Lockout
    # ------------------------------------------------------------------

    def record_login_failure(self, username: str):
        """Record a failed login attempt."""
        now = time.time()
        ip = self._get_client_ip()
        keys = [f"lockout:ip:{ip}", f"lockout:user:{username}"]

        if self.redis_client:
            try:
                for key in keys:
                    self.redis_client.lpush(key, now)
                    self.redis_client.ltrim(key, 0, 10)  # Keep only last 10
                    self.redis_client.expire(key, 1800) # 30 min expiry
                return
            except Exception as e:
                self.logger.error("redis_lockout_record_failed", error=str(e))

        for key in keys:
            if key not in _GLOBAL_RATE_LIMITS:
                _GLOBAL_RATE_LIMITS[key] = []
            _GLOBAL_RATE_LIMITS[key].append(now)

    def is_login_locked_out(self, username: str, max_attempts: int = 5, window: int = 300) -> tuple[bool, Optional[int]]:
        """Check if login is locked out."""
        now = time.time()
        ip = self._get_client_ip()
        keys = [f"lockout:ip:{ip}", f"lockout:user:{username}"]
        
        lockout_duration = 900 # 15 minutes
        
        is_limited = False
        max_remaining = 0

        for key in keys:
            attempts = []
            if self.redis_client:
                try:
                    attempts = [float(t) for t in self.redis_client.lrange(key, 0, -1)]
                except Exception as e:
                    self.logger.error("redis_lockout_check_failed", error=str(e))
            else:
                attempts = _GLOBAL_RATE_LIMITS.get(key, [])

            recent = [t for t in attempts if now - t < window]
            
            if len(recent) >= max_attempts:
                oldest_recent = min(recent)
                time_since_first = now - oldest_recent
                if time_since_first < lockout_duration:
                    remaining = int(lockout_duration - time_since_first)
                    is_limited = True
                    max_remaining = max(max_remaining, remaining)
                
        return is_limited, (max_remaining if is_limited else None)

    def clear_login_lockout(self, username: str):
        """Clear lockout state after successful login."""
        ip = self._get_client_ip()
        keys = [f"lockout:ip:{ip}", f"lockout:user:{username}"]
        
        if self.redis_client:
            try:
                self.redis_client.delete(*keys)
            except Exception:
                pass
        
        for key in keys:
            _GLOBAL_RATE_LIMITS.pop(key, None)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def check_rate_limit(self, client_id: str, max_requests: int = 100, window: int = 60) -> bool:
        """
        Return True if the client is within the rate limit, False if exceeded.
        Uses Redis if enabled, otherwise falls back to a global dictionary.
        """
        now = time.time()
        ip = self._get_client_ip()
        # Track by both IP and username to prevent distributed attacks
        keys = [f"rl:ip:{ip}", f"rl:user:{client_id}"]

        if self.redis_client:
            try:
                for key in keys:
                    # Use Redis pipeline for atomicity
                    pipe = self.redis_client.pipeline()
                    pipe.incr(key)
                    pipe.expire(key, window)
                    count, _ = pipe.execute()
                    if int(count) > max_requests:
                        return False
                return True
            except Exception as e:
                self.logger.error("redis_rate_limit_failed", error=str(e))
                # Fallback to in-memory if Redis fails

        # In-memory fallback
        for key in keys:
            if key not in _GLOBAL_RATE_LIMITS:
                _GLOBAL_RATE_LIMITS[key] = []

            _GLOBAL_RATE_LIMITS[key] = [t for t in _GLOBAL_RATE_LIMITS[key] if now - t < window]

            if len(_GLOBAL_RATE_LIMITS[key]) >= max_requests:
                return False

            _GLOBAL_RATE_LIMITS[key].append(now)
        
        return True

    # ------------------------------------------------------------------
    # Session validation
    # ------------------------------------------------------------------

    def validate_session(self) -> bool:
        """
        Validate the current Streamlit session.
        Returns False (and clears the session) if the session has expired.
        """
        if not st.session_state.get("authenticated"):
            return True  # unauthenticated — nothing to validate

        session_start = st.session_state.get("_session_start")
        if session_start is None:
            return True

        if time.time() - session_start > 3600:  # 1-hour timeout
            self._clear_user_session()
            return False

        return True

    def _clear_user_session(self) -> None:
        """Remove authentication keys from the session."""
        for key in ("authenticated", "user", "username", "role", "display", "_session_start", "_csrf_token", "must_change_password"):
            st.session_state.pop(key, None)

    # ------------------------------------------------------------------
    # Page-level guard
    # ------------------------------------------------------------------

    def enforce(self, role: Optional[str] = None) -> None:
        """
        Call at the very top of every page to enforce session and rate limits.
        If the session is invalid, the page is stopped.
        """
        # 1. Rate limiting check (general protection)
        user = st.session_state.get("username", "anonymous")
        if not self.check_rate_limit(user, max_requests=200, window=60):
            st.error("Trop de requêtes. Veuillez patienter.")
            st.stop()

        # 2. Session validation (timeout)
        if not self.validate_session():
            st.warning("Votre session a expiré. Veuillez vous reconnecter.")
            st.rerun()

        # 3. RBAC
        if role and st.session_state.get("role") != role:
            st.error(f"Accès refusé. Rôle {role} requis.")
            st.stop()

    # ------------------------------------------------------------------
    # Decorators
    # ------------------------------------------------------------------

    def require_auth(self, func: Callable) -> Callable:
        """Decorator: raise AppError if no user is authenticated."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not st.session_state.get("authenticated"):
                raise AppError(ErrorCode.AUTH_FAILED, "Authentication required")
            return func(*args, **kwargs)
        return wrapper

    def require_role(self, role: str) -> Callable:
        """Decorator factory: raise AppError if the user does not have *role*."""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if st.session_state.get("role") != role:
                    raise AppError(ErrorCode.INSUFFICIENT_PERMISSIONS,
                                f"Role '{role}' required")
                return func(*args, **kwargs)
            return wrapper         
        return decorator


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

security_middleware = SecurityMiddleware()


def init_security(config: Dict[str, Any]) -> None:
    """Re-initialise the module singleton with production config."""
    global security_middleware
    security_middleware = SecurityMiddleware(secret_key=config.get("SECRET_KEY"))
    security_middleware.logger.info(
        "Security middleware initialized",
        extra={
            "environment": config.get("ENVIRONMENT", "development"),
            "csrf_protection": config.get("CSRF_PROTECTION", True),
            "rate_limiting": config.get("RATE_LIMITING", True),
        },
    )
