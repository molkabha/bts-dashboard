from __future__ import annotations

from security.middleware import SecurityMiddleware


def _middleware_with_fixed_ip() -> SecurityMiddleware:

    sm = SecurityMiddleware(secret_key="test-secret-key-for-pytest-only")

    sm._get_client_ip = lambda: "203.0.113.10"

    return sm


def test_check_rate_limit_allows_under_threshold():

    sm = _middleware_with_fixed_ip()

    for _ in range(5):

        assert sm.check_rate_limit("pytest-user", max_requests=10, window=60) is True


def test_check_rate_limit_blocks_over_threshold():

    sm = _middleware_with_fixed_ip()

    for _ in range(10):

        sm.check_rate_limit("pytest-user", max_requests=10, window=60)

    assert sm.check_rate_limit("pytest-user", max_requests=10, window=60) is False


def test_login_lockout_after_failed_attempts():

    sm = _middleware_with_fixed_ip()

    for _ in range(5):

        sm.record_login_failure("locked_user")

    limited, remaining = sm.is_login_locked_out(
        "locked_user", max_attempts=5, window=300
    )

    assert limited is True

    assert remaining is not None and remaining > 0


def test_clear_login_lockout():

    sm = _middleware_with_fixed_ip()

    for _ in range(5):

        sm.record_login_failure("unlock_user")

    sm.clear_login_lockout("unlock_user")

    limited, _ = sm.is_login_locked_out("unlock_user", max_attempts=5, window=300)

    assert limited is False
