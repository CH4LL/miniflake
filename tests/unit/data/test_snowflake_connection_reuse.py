from __future__ import annotations

from unittest.mock import patch

from app.config import Settings
from app.data.snowflake_repository import SnowflakeCensusRepository

GEOGRAPHY_ROW = ("US", "United States", "Nation", None, None)


class FakeCursor:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection
        self._rows: list[tuple[object, ...]] = []

    def execute(self, sql: str, params: object | None = None) -> None:
        self._connection.executes.append(sql)
        if sql.startswith("ALTER SESSION"):
            return
        self._connection.query_count += 1
        if self._connection.fail_next_query:
            self._connection.fail_next_query = False
            raise ConnectionError("connection is closed")
        self._rows = [GEOGRAPHY_ROW]

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows

    def close(self) -> None:
        return None


class FakeConnection:
    def __init__(self) -> None:
        self._closed = False
        self.close_calls = 0
        self.executes: list[str] = []
        self.query_count = 0
        self.fail_next_query = False

    def is_closed(self) -> bool:
        return self._closed

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def close(self) -> None:
        self.close_calls += 1
        self._closed = True


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        "NATION_GEO_ID": "US",
        "SNOWFLAKE_RETRY_ATTEMPTS": 3,
        "SNOWFLAKE_RETRY_BACKOFF_SECONDS": 0,
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def test_reuses_open_connection_across_queries() -> None:
    connections: list[FakeConnection] = []

    def connect(_settings: Settings) -> FakeConnection:
        connection = FakeConnection()
        connections.append(connection)
        return connection

    with patch("app.data.snowflake_repository.connect_snowflake", side_effect=connect):
        repo = SnowflakeCensusRepository(_settings())
        first = repo.get_geography("US")
        second = repo.get_geography("US")

    assert len(connections) == 1
    assert first.rows[0].geo_id == "US"
    assert second.rows[0].geo_id == "US"
    alters = [sql for sql in connections[0].executes if sql.startswith("ALTER SESSION")]
    assert len(alters) == 2
    assert connections[0].query_count == 2


def test_reconnects_when_connection_is_closed() -> None:
    connections: list[FakeConnection] = []

    def connect(_settings: Settings) -> FakeConnection:
        connection = FakeConnection()
        connections.append(connection)
        return connection

    with patch("app.data.snowflake_repository.connect_snowflake", side_effect=connect):
        repo = SnowflakeCensusRepository(_settings())
        repo.get_geography("US")
        connections[0]._closed = True
        repo.get_geography("US")

    assert len(connections) == 2
    assert connections[0] is not connections[1]


def test_close_closes_open_connection_and_is_idempotent() -> None:
    connections: list[FakeConnection] = []

    def connect(_settings: Settings) -> FakeConnection:
        connection = FakeConnection()
        connections.append(connection)
        return connection

    with patch("app.data.snowflake_repository.connect_snowflake", side_effect=connect):
        repo = SnowflakeCensusRepository(_settings())
        repo.get_geography("US")
        repo.close()
        repo.close()

    assert len(connections) == 1
    assert connections[0].close_calls == 1
    assert connections[0].is_closed()


def test_retries_closed_connection_error_on_a_new_session() -> None:
    connections: list[FakeConnection] = []

    def connect(_settings: Settings) -> FakeConnection:
        connection = FakeConnection()
        if not connections:
            connection.fail_next_query = True
        connections.append(connection)
        return connection

    with patch("app.data.snowflake_repository.connect_snowflake", side_effect=connect):
        repo = SnowflakeCensusRepository(_settings())
        result = repo.get_geography("US")

    assert result.rows[0].geo_id == "US"
    assert len(connections) == 2
    assert connections[0].query_count == 1
    assert connections[1].query_count == 1
