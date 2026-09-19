from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.config import Settings


def preview(text: str, chars: int) -> str:
    normalized = text.strip()
    if len(normalized) <= chars:
        return normalized
    return f"{normalized[:chars]}…"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        for key, value in record.__dict__.items():
            if key.startswith("_"):
                continue
            if key in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "taskName",
            }:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
        if isinstance(existing, logging.FileHandler):
            existing.close()
    stream_handler = logging.StreamHandler()
    if settings.log_format == "json":
        stream_handler.setFormatter(JsonFormatter())
    else:
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    root.addHandler(stream_handler)

    log_path = settings.log_file_path()
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        file_handler.setFormatter(JsonFormatter())
        root.addHandler(file_handler)

    root.setLevel(settings.log_level.upper())

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True


def log_message_preview(
    logger: logging.Logger,
    *,
    level: int,
    message: str,
    preview_chars: int,
    **fields: Any,
) -> None:
    if logger.isEnabledFor(logging.DEBUG):
        logger.log(level, message, extra=fields)
        return
    logger.log(
        level,
        preview(message, preview_chars),
        extra={**fields, "message_preview": preview(message, preview_chars)},
    )
