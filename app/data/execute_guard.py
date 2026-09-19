from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.data.errors import ReadOnlyViolationError, RepositoryError, TransientRepositoryError

READ_ONLY_PATTERN = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE | re.DOTALL)
MULTI_STATEMENT_PATTERN = re.compile(r";\s*\S")


def assert_read_only(sql: str) -> None:
    if not READ_ONLY_PATTERN.match(sql):
        raise ReadOnlyViolationError("Only SELECT and WITH statements are allowed")
    if MULTI_STATEMENT_PATTERN.search(sql.rstrip(";")):
        raise ReadOnlyViolationError("Multiple SQL statements are not allowed")


def clamp_limit(limit: int, maximum: int) -> int:
    if limit < 1:
        return 1
    return min(limit, maximum)


def execute_with_retry(
    operation: Callable[[], Any],
    *,
    attempts: int,
    backoff_seconds: float,
    is_transient: Callable[[Exception], bool],
) -> Any:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except ReadOnlyViolationError:
            raise
        except Exception as exc:
            last_error = exc
            if not is_transient(exc) or attempt == attempts - 1:
                if is_transient(exc):
                    raise TransientRepositoryError(str(exc)) from exc
                raise RepositoryError(str(exc)) from exc
            time.sleep(backoff_seconds * (2**attempt))
    if last_error is not None:
        raise RepositoryError(str(last_error))
    raise RepositoryError("Operation failed without an exception")


def is_transient_snowflake_error(exc: Exception) -> bool:
    message = str(exc).lower()
    transient_markers = (
        "connection is closed",
        "connection reset",
        "timeout",
        "temporarily unavailable",
        "service unavailable",
        "57014",
        "08001",
        "08003",
        "08006",
    )
    return any(marker in message for marker in transient_markers)


def build_provenance(
    *,
    sql: str,
    parameters: dict[str, Any],
    row_count: int,
    source: str,
    duration_ms: float,
    aggregation_method: str,
    block_groups_aggregated: int | None = None,
) -> dict[str, Any]:
    return {
        "sql": sql,
        "parameters": parameters,
        "row_count": row_count,
        "source": source,
        "executed_at": datetime.now(UTC),
        "duration_ms": duration_ms,
        "aggregation_method": aggregation_method,
        "block_groups_aggregated": block_groups_aggregated,
    }
