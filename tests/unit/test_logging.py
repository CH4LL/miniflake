from __future__ import annotations

import json
import logging

from app.logging import JsonFormatter, log_message_preview, preview


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
