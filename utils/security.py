"""Security and password utilities."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def password_hash(value: str) -> str:
    """Hash a password using PBKDF2-SHA256 with a random salt."""
    salt = secrets.token_hex(16)
    rounds = 260000
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt.encode("utf-8"), rounds).hex()
    return f"pbkdf2_sha256${rounds}${salt}${digest}"


def password_matches(value: str, stored_hash: str) -> bool:
    """Check if a password matches a stored hash."""
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, rounds, salt, digest = stored_hash.split("$", 3)
            candidate = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt.encode("utf-8"), int(rounds)).hex()
            return hmac.compare_digest(candidate, digest)
        except ValueError:
            return False
    return hmac.compare_digest(hashlib.sha256(value.encode("utf-8")).hexdigest(), stored_hash)