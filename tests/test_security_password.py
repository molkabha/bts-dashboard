from __future__ import annotations

from utils.security import generate_temp_password, password_hash, password_matches


def test_password_hash_and_match_bcrypt():

    raw = "Test-Secret-42!"

    stored = password_hash(raw)

    assert stored.startswith("$2")

    assert password_matches(raw, stored)

    assert not password_matches("wrong", stored)


def test_generate_temp_password_length():

    pwd = generate_temp_password(16)

    assert len(pwd) == 16
