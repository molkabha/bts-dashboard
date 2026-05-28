from __future__ import annotations

import hmac

import logging

import secrets

import time

from typing import Dict, Optional

import streamlit as st

from config.settings import settings

_GLOBAL_RATE_LIMITS: Dict[str, list] = {}


class SecurityMiddleware:

    def __init__(self, secret_key: Optional[str] = None):

        self.secret_key = secret_key or settings.SECRET_KEY or secrets.token_hex(32)

        self.logger = logging.getLogger(__name__)

    def _get_client_ip(self) -> str:

        try:

            headers = st.context.headers

            remote_addr = headers.get("Remote-Addr", "127.0.0.1")

            if "X-Forwarded-For" in headers:

                if remote_addr in settings.TRUSTED_PROXIES:

                    return headers["X-Forwarded-For"].split(",")[0].strip()

            return remote_addr

        except Exception:

            return "unknown"

    def apply_security_headers(self):

        st.markdown(
            "\n            <style>\n                #MainMenu {visibility: hidden;}\n                footer {visibility: hidden;}\n            </style>\n            ",
            unsafe_allow_html=True,
        )

    def generate_csrf_token(self) -> str:

        token = secrets.token_urlsafe(32)

        st.session_state["_csrf_token"] = token

        return token

    def validate_csrf_token(self, token: str, rotate: bool = False) -> bool:

        stored = st.session_state.get("_csrf_token")

        if not stored:

            return False

        valid = hmac.compare_digest(stored, token)

        if rotate or settings.CSRF_ROTATE_TOKEN:

            self.generate_csrf_token()

        return valid

    def record_login_failure(self, username: str):

        now = time.time()

        ip = self._get_client_ip()

        keys = [f"lockout:ip:{ip}", f"lockout:user:{username}"]

        for key in keys:

            if key not in _GLOBAL_RATE_LIMITS:

                _GLOBAL_RATE_LIMITS[key] = []

            _GLOBAL_RATE_LIMITS[key].append(now)

    def is_login_locked_out(
        self, username: str, max_attempts: int = 5, window: int = 300
    ) -> tuple[bool, Optional[int]]:

        now = time.time()

        ip = self._get_client_ip()

        keys = [f"lockout:ip:{ip}", f"lockout:user:{username}"]

        lockout_duration = 900

        is_limited = False

        max_remaining = 0

        for key in keys:

            attempts = _GLOBAL_RATE_LIMITS.get(key, [])

            recent = [t for t in attempts if now - t < window]

            if len(recent) >= max_attempts:

                oldest_recent = min(recent)

                time_since_first = now - oldest_recent

                if time_since_first < lockout_duration:

                    remaining = int(lockout_duration - time_since_first)

                    is_limited = True

                    max_remaining = max(max_remaining, remaining)

        return (is_limited, max_remaining if is_limited else None)

    def clear_login_lockout(self, username: str):

        ip = self._get_client_ip()

        keys = [f"lockout:ip:{ip}", f"lockout:user:{username}"]

        for key in keys:

            _GLOBAL_RATE_LIMITS.pop(key, None)

    def check_rate_limit(
        self, client_id: str, max_requests: int = 100, window: int = 60
    ) -> bool:

        now = time.time()

        ip = self._get_client_ip()

        keys = [f"rl:ip:{ip}", f"rl:user:{client_id}"]

        for key in keys:

            if key not in _GLOBAL_RATE_LIMITS:

                _GLOBAL_RATE_LIMITS[key] = []

            _GLOBAL_RATE_LIMITS[key] = [
                t for t in _GLOBAL_RATE_LIMITS[key] if now - t < window
            ]

            if len(_GLOBAL_RATE_LIMITS[key]) >= max_requests:

                return False

            _GLOBAL_RATE_LIMITS[key].append(now)

        return True

    def validate_session(self) -> bool:

        if not st.session_state.get("authenticated"):

            return True

        session_start = st.session_state.get("_session_start")

        if session_start is None:

            return True

        if time.time() - session_start > 3600:

            self._clear_user_session()

            return False

        return True

    def _clear_user_session(self) -> None:

        for key in (
            "authenticated",
            "user",
            "username",
            "role",
            "display",
            "_session_start",
            "_csrf_token",
            "must_change_password",
        ):

            st.session_state.pop(key, None)

    def enforce(self, role: Optional[str] = None) -> None:

        user = st.session_state.get("username", "anonymous")

        if not self.check_rate_limit(user, max_requests=200, window=60):

            st.error("Trop de requêtes. Veuillez patienter.")

            st.stop()

        if not self.validate_session():

            st.warning("Votre session a expiré. Veuillez vous reconnecter.")

            st.rerun()

        if role and st.session_state.get("role") != role:

            st.error(f"Accès refusé. Rôle {role} requis.")

            st.stop()


security_middleware = SecurityMiddleware()
