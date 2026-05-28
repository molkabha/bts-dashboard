from __future__ import annotations

import hashlib

import hmac

import secrets

import bcrypt


def password_hash(value: str) -> str:

    return bcrypt.hashpw(value.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode(
        "utf-8"
    )


def password_matches(value: str, stored_hash: str) -> bool:

    if not stored_hash:

        return False

    if (
        stored_hash.startswith("$2a$")
        or stored_hash.startswith("$2b$")
        or stored_hash.startswith("$2y$")
    ):

        try:

            return bcrypt.checkpw(value.encode("utf-8"), stored_hash.encode("utf-8"))

        except ValueError:

            return False

    if stored_hash.startswith("pbkdf2_sha256$"):

        try:

            _, rounds, salt, digest = stored_hash.split("$", 3)

            candidate = hashlib.pbkdf2_hmac(
                "sha256", value.encode("utf-8"), salt.encode("utf-8"), int(rounds)
            ).hex()

            return hmac.compare_digest(candidate, digest)

        except ValueError:

            return False

    return hmac.compare_digest(
        hashlib.sha256(value.encode("utf-8")).hexdigest(), stored_hash
    )


def generate_temp_password(length: int = 12) -> str:

    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"

    return "".join((secrets.choice(alphabet) for _ in range(length)))
