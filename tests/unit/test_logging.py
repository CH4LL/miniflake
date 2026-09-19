from __future__ import annotations

import json
import logging
from collections.abc import Generator
from pathlib import Path

import pytest

from app.config import Settings
from app.logging import JsonFormatter, configure_logging, log_message_preview, preview


@pytest.fixture
def restore_logging() -> Generator[None, None, None]:
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    yield
    for handler in list(root.handlers):
        handler.close()
    root.handlers.clear()
    for handler in previous_handlers:
        root.addHandler(handler)
    root.setLevel(previous_level)


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        "ENVIRONMENT": "test",
        "LOG_FILE": "",
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def _file_handlers() -> list[logging.FileHandler]:
    return [
        handler for handler in logging.getLogger().handlers if type(handler) is logging.FileHandler
    ]


def _stream_handlers() -> list[logging.StreamHandler]:
    return [
        handler
        for handler in logging.getLogger().handlers
        if type(handler) is logging.StreamHandler
    ]


def test_json_formatter_emits_required_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.api.chat",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="chat turn completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    record.outcome = "answer"
    record.latency_ms = 1234.5
    record.tool_calls = [{"name": "get_value", "duration_ms": 42.0}]

    payload = json.loads(formatter.format(record))
    assert payload["severity"] == "INFO"
    assert payload["message"] == "chat turn completed"
    assert payload["logger"] == "app.api.chat"
    assert payload["request_id"] == "req-123"
    assert payload["outcome"] == "answer"
    assert payload["latency_ms"] == 1234.5
    assert payload["tool_calls"] == [{"name": "get_value", "duration_ms": 42.0}]
    assert "timestamp" in payload


def test_preview_truncates_long_text() -> None:
    text = "a" * 120
    truncated = preview(text, 80)
    assert len(truncated) == 81
    assert truncated.endswith("…")


def test_log_message_preview_redacts_at_info_level() -> None:
    logger = logging.getLogger("test.preview")
    captured: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = CaptureHandler()
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    long_text = "secret census answer " * 20
    log_message_preview(
        logger,
        level=logging.INFO,
        message=long_text,
        preview_chars=40,
        request_id="req-1",
    )
    assert len(captured) == 1
    record = captured[0]
    assert len(record.getMessage()) <= 41
    assert record.request_id == "req-1"


def test_configure_logging_writes_json_lines_to_file(tmp_path: Path, restore_logging: None) -> None:
    log_path = tmp_path / "nested" / "app.jsonl"
    configure_logging(_settings(LOG_FILE=str(log_path), LOG_FORMAT="text"))
    logging.getLogger("app.api.chat").info(
        "chat turn completed", extra={"request_id": "req-123", "outcome": "answer"}
    )

    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["severity"] == "INFO"
    assert payload["message"] == "chat turn completed"
    assert payload["logger"] == "app.api.chat"
    assert payload["request_id"] == "req-123"
    assert payload["outcome"] == "answer"
    assert "timestamp" in payload
    assert _stream_handlers()
    assert len(_file_handlers()) == 1


def test_configure_logging_appends_on_reconfigure(tmp_path: Path, restore_logging: None) -> None:
    log_path = tmp_path / "app.jsonl"
    settings = _settings(LOG_FILE=str(log_path))
    configure_logging(settings)
    logging.getLogger("app.test").info("first")
    configure_logging(settings)
    logging.getLogger("app.test").info("second")

    messages = [
        json.loads(line)["message"] for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert messages == ["first", "second"]


def test_empty_log_file_does_not_attach_file_handler(restore_logging: None) -> None:
    configure_logging(_settings(ENVIRONMENT="local", LOG_FILE=""))
    assert _file_handlers() == []
    assert _stream_handlers()


def test_production_without_log_file_does_not_attach_file_handler(
    restore_logging: None,
) -> None:
    configure_logging(_settings(ENVIRONMENT="production", LOG_FILE=None))
    assert _file_handlers() == []
    assert _stream_handlers()
