from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from app.api.deps import AppContainer
from app.config import Settings
from app.warmup import warm_up


class _FakeRepository:
    def __init__(self) -> None:
        self.calls = 0

    def get_geography(self, geo_id: str) -> None:
        self.calls += 1


def _settings(**overrides: object) -> Settings:
    base = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        "NATION_GEO_ID": "US",
        "WARMUP_ENABLED": True,
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def test_warm_up_calls_repository_once() -> None:
    repository = _FakeRepository()
    container = AppContainer(
        settings=_settings(),
        repository=repository,
        llm=MagicMock(),
        classifier_llm=MagicMock(),
        registry=MagicMock(),
        store=MagicMock(),
        service=MagicMock(),
    )
    warm_up(container)
    assert repository.calls == 1


def test_warm_up_tolerates_failure_without_raising(caplog: pytest.LogCaptureFixture) -> None:
    class _FailingRepository:
        def get_geography(self, geo_id: str) -> None:
            raise RuntimeError("warehouse unavailable")

    container = AppContainer(
        settings=_settings(),
        repository=_FailingRepository(),
        llm=MagicMock(),
        classifier_llm=MagicMock(),
        registry=MagicMock(),
        store=MagicMock(),
        service=MagicMock(),
    )
    caplog.set_level(logging.WARNING)
    warm_up(container)
    assert any("warm-up failed" in record.message for record in caplog.records)


def test_warm_up_disabled_skips_repository_call() -> None:
    repository = _FakeRepository()
    container = AppContainer(
        settings=_settings(WARMUP_ENABLED=False),
        repository=repository,
        llm=MagicMock(),
        classifier_llm=MagicMock(),
        registry=MagicMock(),
        store=MagicMock(),
        service=MagicMock(),
    )
    warm_up(container)
    assert repository.calls == 0
