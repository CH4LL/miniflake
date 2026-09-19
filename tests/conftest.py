import os
from collections.abc import Generator
from typing import Any

import pytest


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    for key in list(os.environ):
        if key.startswith(
            (
                "APP_",
                "ENVIRONMENT",
                "LOG_LEVEL",
                "HEALTH_",
                "SNOWFLAKE_",
                "GCP_",
                "ANTHROPIC_",
                "AGENT_",
            )
        ):
            monkeypatch.delenv(key, raising=False)
    yield


def make_settings_env(**overrides: str) -> dict[str, str]:
    base: dict[str, str] = {
        "APP_NAME": "test-miniflake",
        "ENVIRONMENT": "test",
        "LOG_LEVEL": "INFO",
        "HEALTH_VERSION": "0.1.0-test",
        "SNOWFLAKE_ACCOUNT": "TEST-ACCOUNT",
        "SNOWFLAKE_USER": "TEST_USER",
        "SNOWFLAKE_ROLE": "TEST_ROLE",
        "SNOWFLAKE_WAREHOUSE": "TEST_WH",
        "SNOWFLAKE_DATABASE": "TEST_DB",
        "SNOWFLAKE_SCHEMA": "PUBLIC",
        "SNOWFLAKE_PRIVATE_KEY_PATH": "/tmp/test_key.p8",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
    }
    base.update(overrides)
    return base


@pytest.fixture
def settings_env(isolated_env: None, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    env = make_settings_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


@pytest.fixture
def apply_env(monkeypatch: pytest.MonkeyPatch) -> Any:
    def _apply(env: dict[str, str]) -> None:
        for key, value in env.items():
            monkeypatch.setenv(key, value)

    return _apply
