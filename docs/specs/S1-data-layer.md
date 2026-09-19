# S1: Data access layer

Status: see [roadmap.md](../roadmap.md). Estimate: 3 h. Depends on S0.

## Goal

A `CensusRepository` protocol that exposes exactly the queries the tools need, implemented once against Snowflake and once against local fixtures. Every SQL statement the application ever runs is a parametrized template that lives in this layer.

## Scope

1. `CensusRepository` protocol and domain models.
2. `SnowflakeCensusRepository` with connection management, read-only guard, statement timeout, row cap, and bounded retry on transient errors.
3. SQL templates, one file per query, with named bind parameters.
4. Catalog snapshot script producing fixtures.
5. `FakeCensusRepository` loading those fixtures.
6. Contract tests run against both implementations.

## Out of scope

Tool schemas, LLM interaction, any ranking or comparison logic that is not a direct query.

## Domain models (`app/data/models.py`)

- `Geography`: `geo_id`, `name`, `level` (enum: `Nation`, `State`, `County`, `CBSA`, `Place`), optional `parent_geo_id`, optional `state_abbreviation`.
- `Variable`: `variable_id`, `name`, `series_id`, `topic` (curated grouping), `unit`, `measurement_type`, `measurement_period` (enum `1YR`, `5YR`), optional `description`.
- `Observation`: `geo_id`, `variable_id`, `date`, `value`.
- `Provenance`: `sql`, `parameters`, `row_count`, `source` (database and table names), `executed_at`, `duration_ms`.
- `QueryResult[T]`: `rows: list[T]`, `provenance: Provenance`.

## Protocol (`app/data/repository.py`)

```python
class CensusRepository(Protocol):
    def search_geographies(self, query: str, level: GeoLevel | None, limit: int) -> QueryResult[Geography]: ...
    def get_geography(self, geo_id: str) -> QueryResult[Geography]: ...
    def search_variables(self, query: str, topic: str | None, limit: int) -> QueryResult[Variable]: ...
    def get_variable(self, variable_id: str) -> QueryResult[Variable]: ...
    def get_observations(self, variable_id: str, geo_ids: list[str], date: date | None) -> QueryResult[Observation]: ...
    def get_latest_date(self, variable_id: str, level: GeoLevel) -> date | None: ...
    def rank_geographies(self, variable_id: str, level: GeoLevel, date: date, parent_geo_id: str | None, descending: bool, limit: int) -> QueryResult[Observation]: ...
    def get_time_series(self, variable_id: str, geo_id: str) -> QueryResult[Observation]: ...
    def available_dates(self, variable_id: str, geo_id: str) -> list[date]: ...
```

`search_*` methods do case-insensitive matching on names with a deterministic ordering (exact match first, then prefix, then contains) so ambiguity handling in S2 is predictable.

## Snowflake implementation

- One connection per process, opened lazily, re-opened on a closed-connection error.
- Session parameters set at connect: `STATEMENT_TIMEOUT_IN_SECONDS`, `QUERY_TAG` with the application name.
- Read-only guard: every statement passes through a single `execute` helper that rejects anything not starting with `SELECT` or `WITH` and rejects multiple statements. This is a defence in depth; the role is read-only anyway.
- Row cap: every template ends with `LIMIT %(limit)s`; the helper clamps `limit` to the configured maximum.
- Retry: transient network and warehouse-resume errors are retried a configured number of times with backoff; everything else surfaces as `RepositoryError` with the original message attached and the SQL redacted from user-facing paths.
- Provenance captures the rendered SQL with bind parameter names, the parameter values, row count, duration, and the fully qualified table names.

## SQL templates (`app/data/sql/`)

`search_geographies.sql`, `get_geography.sql`, `search_variables.sql`, `get_variable.sql`, `get_observations.sql`, `get_latest_date.sql`, `rank_geographies.sql`, `get_time_series.sql`, `available_dates.sql`. Fully qualified table names are injected from configuration at load time; bind parameters are used for every user-influenced value.

## Catalog snapshot (`scripts/snapshot_catalog.py`)

Writes:

- `fixtures/geographies.json`: all geographies at the supported levels (Nation, State, County, CBSA, Place).
- `fixtures/variables.json`: the curated variable catalog. Curation is a hand-maintained allow-list in `fixtures/variable_catalog_spec.yaml` naming series ids and topics to include (population totals, age and sex, race and ethnicity, households, income, poverty, education, employment, housing, commuting). The script expands series ids to variables using the attributes table and attaches topic and friendly names.
- `fixtures/sample_observations.json`: observations for a small set of geographies and variables across all available dates, used by the fake repository and by S2/S3 tests.

## Fake implementation

`FakeCensusRepository` loads the three fixture files and implements the protocol in memory with the same ordering rules as the SQL. Provenance is produced with `source` set to `fixtures` and a synthetic SQL string naming the method and parameters so higher layers can assert on provenance shape.

## Acceptance criteria

- Given the fake and the Snowflake repository, when the shared contract test suite runs, then both pass the same assertions (the Snowflake run is opt-in).
- Given the query `"Texas"` with level `State`, when `search_geographies` runs, then the first result is the state of Texas.
- Given the query `"Springfield"` with no level, when `search_geographies` runs, then multiple results are returned across states, ordered deterministically.
- Given a variable id and a list of geo ids, when `get_observations` runs with no date, then observations for the latest available date are returned and the provenance names the date used.
- Given a non-`SELECT` statement, when the execute helper is called, then it raises before contacting Snowflake.
- Given a `limit` above the configured maximum, when any search runs, then the effective limit equals the maximum.
- Given a transient connection error on the first attempt, when a query runs, then it is retried and succeeds; given a syntax error, then it is not retried and `RepositoryError` is raised.
- Given the snapshot script has run, when the fixture files are loaded, then each contains at least one entry per supported geography level and per curated topic.

## Tests to write first

1. `tests/unit/data/test_models.py`: model validation, enum parsing of geography levels and measurement periods.
2. `tests/unit/data/test_execute_guard.py`: read-only guard, multi-statement rejection, limit clamping.
3. `tests/unit/data/test_retry.py`: retry on transient errors with a stubbed cursor, no retry on other errors.
4. `tests/unit/data/test_sql_templates.py`: every template file loads, renders with table names, and contains a bind for every documented parameter.
5. `tests/component/data/test_repository_contract.py`: parametrized over `fake` and (live-only) `snowflake`; covers each protocol method.
6. `tests/unit/data/test_fake_repository.py`: ordering rules and fixture loading.
7. `tests/live/test_snowflake_repository.py`: opt-in smoke for each template.

## Files

- `app/data/__init__.py`, `models.py`, `repository.py`, `snowflake_repository.py`, `fake_repository.py`, `sql_loader.py`, `errors.py`
- `app/data/sql/*.sql`
- `scripts/snapshot_catalog.py`, `fixtures/variable_catalog_spec.yaml`, generated `fixtures/*.json`
- tests listed above

## Documentation updates at stage end

- `docs/data/dataset.md`: section on the curated catalog (topics and counts, without quoting configuration values).
- `ARCHITECTURE.md`: Data layer row reflects the implemented protocol.
- `CHANGELOG.md`, `docs/roadmap.md`, `docs/decision_log.md` if any template needed a workaround for the dataset shape.
