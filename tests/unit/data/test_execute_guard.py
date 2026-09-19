import pytest

from app.data.errors import ReadOnlyViolationError, RepositoryError, TransientRepositoryError
from app.data.execute_guard import assert_read_only, clamp_limit, execute_with_retry


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "  with cte as (select 1) select * from cte",
        "WITH data AS (SELECT 1) SELECT * FROM data LIMIT 10",
    ],
)
def test_assert_read_only_accepts_select_and_with(sql: str) -> None:
    assert_read_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET x = 1",
        "DELETE FROM t",
        "DROP TABLE t",
        "SELECT 1; DROP TABLE t",
    ],
)
def test_assert_read_only_rejects_non_select(sql: str) -> None:
    with pytest.raises(ReadOnlyViolationError):
        assert_read_only(sql)


def test_clamp_limit() -> None:
    assert clamp_limit(5, 10) == 5
    assert clamp_limit(100, 10) == 10
    assert clamp_limit(0, 10) == 1


def test_execute_with_retry_succeeds_after_transient_error() -> None:
    attempts = {"count": 0}

    def operation() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ConnectionError("connection is closed")
        return "ok"

    result = execute_with_retry(
        operation,
        attempts=3,
        backoff_seconds=0,
        is_transient=lambda exc: "connection is closed" in str(exc).lower(),
    )
    assert result == "ok"
    assert attempts["count"] == 2


def test_execute_with_retry_raises_repository_error_for_non_transient() -> None:
    def operation() -> None:
        raise ValueError("bad query")

    with pytest.raises(RepositoryError):
        execute_with_retry(
            operation,
            attempts=3,
            backoff_seconds=0,
            is_transient=lambda _exc: False,
        )


def test_execute_with_retry_exhausts_transient_attempts() -> None:
    def operation() -> None:
        raise ConnectionError("connection reset")

    with pytest.raises(TransientRepositoryError):
        execute_with_retry(
            operation,
            attempts=2,
            backoff_seconds=0,
            is_transient=lambda exc: "connection reset" in str(exc).lower(),
        )
