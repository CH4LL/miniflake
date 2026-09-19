from __future__ import annotations

import time
from typing import Any

import pytest

from app.api.auth import DemoAuth, sign_token, verify_passphrase, verify_token
from app.config import Settings


def _settings(**overrides: Any) -> Settings:
    base = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        "DEMO_AUTH_ENABLED": True,
        "DEMO_PASSPHRASE": "correct-horse-battery",
        "AUTH_SIGNING_SECRET": "test-signing-secret-at-least-32-chars-long",
        "AUTH_COOKIE_MAX_AGE_SECONDS": 3600,
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def test_sign_and_verify_round_trip() -> None:
    settings = _settings()
    token = sign_token(settings.auth_signing_secret, now=1000.0)
    assert verify_token(token, settings.auth_signing_secret, max_age_seconds=3600, now=1000.0)


def test_tampered_payload_rejected() -> None:
    settings = _settings()
    token = sign_token(settings.auth_signing_secret, now=1000.0)
    payload, signature = token.split(".", 1)
    tampered = payload[:-1] + ("A" if payload[-1] != "A" else "B") + "." + signature
    assert not verify_token(
        tampered, settings.auth_signing_secret, max_age_seconds=3600, now=1000.0
    )


def test_tampered_signature_rejected() -> None:
    settings = _settings()
    token = sign_token(settings.auth_signing_secret, now=1000.0)
    payload, signature = token.split(".", 1)
    tampered = payload + "." + ("A" * len(signature))
    assert not verify_token(
        tampered, settings.auth_signing_secret, max_age_seconds=3600, now=1000.0
    )


def test_wrong_secret_rejected() -> None:
    settings = _settings()
    token = sign_token(settings.auth_signing_secret, now=1000.0)
    assert not verify_token(
        token, "wrong-secret-at-least-32-chars-long", max_age_seconds=3600, now=1000.0
    )


def test_expired_token_rejected() -> None:
    settings = _settings()
    token = sign_token(settings.auth_signing_secret, now=1000.0)
    assert not verify_token(token, settings.auth_signing_secret, max_age_seconds=3600, now=5000.0)


def test_malformed_token_rejected() -> None:
    settings = _settings()
    assert not verify_token(
        "not-a-valid-token", settings.auth_signing_secret, max_age_seconds=3600, now=1000.0
    )
    assert not verify_token("", settings.auth_signing_secret, max_age_seconds=3600, now=1000.0)


def test_verify_passphrase_constant_time() -> None:
    settings = _settings()
    assert verify_passphrase("correct-horse-battery", settings.demo_passphrase)
    assert not verify_passphrase("wrong-passphrase", settings.demo_passphrase)


def test_demo_auth_disabled_is_noop() -> None:
    settings = _settings(DEMO_AUTH_ENABLED=False)
    auth = DemoAuth(settings)
    assert not auth.enabled
    assert auth.is_authenticated(None)
    assert auth.is_authenticated("anything")


def test_demo_auth_missing_passphrase_raises() -> None:
    settings = _settings(DEMO_PASSPHRASE=None)
    with pytest.raises(RuntimeError, match="DEMO_PASSPHRASE"):
        DemoAuth(settings)


def test_demo_auth_missing_secret_raises() -> None:
    settings = _settings(AUTH_SIGNING_SECRET=None)
    with pytest.raises(RuntimeError, match="AUTH_SIGNING_SECRET"):
        DemoAuth(settings)


def test_demo_auth_sign_and_verify_cookie() -> None:
    settings = _settings()
    auth = DemoAuth(settings, clock=time.monotonic)
    token = auth.sign_cookie()
    assert auth.is_authenticated(token)


def test_demo_auth_expired_cookie_rejected() -> None:
    now = [1000.0]

    def clock() -> float:
        return now[0]

    settings = _settings(AUTH_COOKIE_MAX_AGE_SECONDS=60)
    auth = DemoAuth(settings, clock=clock)
    token = auth.sign_cookie()
    assert auth.is_authenticated(token)
    now[0] += 120
    assert not auth.is_authenticated(token)
