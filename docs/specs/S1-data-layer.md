# S1: Data access layer

Status: see [roadmap.md](../roadmap.md). Estimate: 3 h. Depends on S0.

## Goal

A `CensusRepository` protocol that exposes exactly the queries the tools need, implemented once against the SafeGraph Snowflake share and once against local fixtures. Every SQL statement the application ever runs is a parametrized template that lives in this layer. Count fields roll up from block groups via `SUM`; median and rate fields do not roll up beyond block group (ADR-004).

## Scope

1. `CensusRepository` protocol and domain models.
2. `SnowflakeCensusRepository` with connection management, read-only guard, statement timeout, row cap, bounded retry, and rollup logic.
3. SQL templates, one file per query, with named bind parameters.
4. Catalog snapshot script producing fixtures with `aggregation_kind` tags.
5. `FakeCensusRepository` loading those fixtures.
6. Contract tests run against both implementations.

## Out of scope

Tool schemas, LLM interaction, ranking or comparison logic that is not a direct query or rollup.

## Domain models (`app/data/models.py`)

- `GeoLevel` enum: `BlockGroup`, `Nation`, `State`, `County`. (`Place` and `CBSA` deferred to S10.)
- `AggregationKind` enum: `count`, `median`, `rate`.
- `AggregationMethod` enum: `direct`, `sum`.
- `Geography`: `geo_id`, `name`, `level`, optional `parent_geo_id`, optional `state_abbreviation`.
- `Variable`: `field_id` (e.g. `B01003e1`), `table_id` / `series_id` (e.g. `B01003`), `name`, `topic`, `aggregation_kind`, optional `description`, `acs_table_name` (wide table to query).
- `Observation`: `geo_id`, `field_id`, `vintage` (ACS year), `value`.
- `Provenance`: `sql`, `parameters`, `row_count`, `source`, `executed_at`, `duration_ms`, `aggregation_method`, `block_groups_aggregated` (count, when rolled up).
- `QueryResult[T]`: `rows: list[T]`, `provenance: Provenance`.

## Protocol (`app/data/repository.py`)

```python
class CensusRepository(Protocol):
    def search_geographies(
        self, query: str, level: GeoLevel | None, limit: int
    ) -> QueryResult[Geography]: ...
    def get_geography(self, geo_id: str) -> QueryResult[Geography]: ...
    def search_variables(
        self, query: str, topic: str | None, limit: int
    ) -> QueryResult[Variable]: ...
    def get_variable(self, field_id: str) -> QueryResult[Variable]: ...
    def get_observations(
        self, field_id: str, geo_ids: list[str], vintage: int | None
    ) -> QueryResult[Observation]: ...
    def get_latest_vintage(self, field_id: str) -> int | None: ...
    def rank_geographies(
        self,
        field_id: str,
        level: GeoLevel,
        vintage: int,
        parent_geo_id: str | None,
        descending: bool,
        limit: int,
    ) -> QueryResult[Observation]: ...
    def get_time_series(self, field_id: str, geo_id: str) -> QueryResult[Observation]: ...
    def available_vintages(self, field_id: str, geo_id: str) -> list[int]: ...
```

`get_observations` and `rank_geographies` check `aggregation_kind` against the requested geography level:

- `count` at `BlockGroup`: direct column read.
- `count` at `State`, `County`, `Place`, `Nation`: `SUM` grouped by FIPS prefix or metadata mapping; provenance records `aggregation_method: sum`.
- `median` or `rate` at `BlockGroup`: direct column read.
- `median` or `rate` at any rolled-up level: raise `UnsupportedAggregationError` (mapped to `UnsupportedRequest` in S2).

`search_*` methods do case-insensitive matching on names with deterministic ordering (exact, prefix, contains).

## Observed share layout (from S0 discovery)

ACS wide tables are named `{YEAR}_CBG_B{nn}` (e.g. `2019_CBG_B01`, `2020_CBG_B25`), not `ACS{year}_5YR`. Each has a `CENSUS_BLOCK_GROUP` primary key. Metadata tables: `{YEAR}_METADATA_CBG_FIELD_DESCRIPTIONS` (columns include `TABLE_ID`, `TABLE_TITLE`, `FIELD_LEVEL_*`), `{YEAR}_METADATA_CBG_FIPS_CODES` (state/county FIPS, no CBSA column), `{YEAR}_METADATA_CBG_GEOGRAPHIC_DATA`. Vintages present: 2019 and 2020. See [docs/data/dataset.md](../data/dataset.md).

## Snowflake implementation

- One connection per process, opened lazily, re-opened on a closed-connection error. Closed-ness is `connection.is_closed()` (callable).
- Session parameters set at connect: `STATEMENT_TIMEOUT_IN_SECONDS`, `QUERY_TAG`.
- Read-only guard: every statement passes through a single `execute` helper that rejects anything not starting with `SELECT` or `WITH` and rejects multiple statements.
- Row cap: every template ends with `LIMIT`; the helper clamps `limit` to the configured maximum.
- Retry: transient errors retried with backoff; everything else surfaces as `RepositoryError`.
- Wide-table reads: resolve `field_id` to `(acs_table_name, column_name)` via the variable catalog; filter by block group FIPS or group by FIPS prefix for rollups.
- Geography index built from metadata FIPS table plus derived state/county entries from FIPS prefixes.

## SQL templates (`app/data/sql/`)

`search_geographies.sql`, `get_geography.sql`, `search_variables.sql`, `get_variable.sql`, `get_observation_block_group.sql`, `get_observation_rollup.sql`, `get_latest_vintage.sql`, `rank_geographies_rollup.sql`, `get_time_series.sql`, `get_time_series_rollup.sql`, `available_vintages.sql`. Table and column names are injected from configuration and the variable catalog at load time; bind parameters are used for every user-influenced value.

`get_time_series` is level-aware: block-group reads use `get_time_series.sql`; count fields at rolled-up geography use `get_time_series_rollup.sql` (SUM per vintage). Median and rate fields at rolled-up geography raise `UnsupportedAggregationError`.

## Catalog snapshot (`scripts/snapshot_catalog.py`)

Writes:

- `fixtures/geographies.json`: block groups (sample), derived states, counties, places (from metadata), nation.
- `fixtures/variables.json`: curated catalog from field-descriptions metadata. Curation via `fixtures/variable_catalog_spec.yaml` (series ids and topics). Each variable tagged with `aggregation_kind` (`count` for total/estimate count fields; `median` for median fields; `rate` for percentage fields).
- `fixtures/sample_observations.json`: observations for a small set of geographies and variables across available vintages.

## Fake implementation

`FakeCensusRepository` loads the three fixture files and implements the protocol in memory with the same ordering and aggregation rules as the SQL implementation.

## Acceptance criteria

- Given the fake and the Snowflake repository, when the shared contract test suite runs, then both pass the same assertions (Snowflake run is opt-in).
- Given the query `"Texas"` with level `State`, when `search_geographies` runs, then the first result is the state of Texas.
- Given `B01003e1` (total population) and Texas, when `get_observations` runs, then the value equals the sum of block-group populations and provenance records `aggregation_method: sum`.
- Given `B19013e1` (median household income) and Cook County, when `get_observations` runs, then `UnsupportedAggregationError` is raised.
- Given `B19013e1` and a specific block group id, when `get_observations` runs, then a direct value is returned with `aggregation_method: direct`.
- Given a non-`SELECT` statement, when the execute helper is called, then it raises before contacting Snowflake.
- Given a transient connection error on the first attempt, when a query runs, then it is retried and succeeds.

## Tests to write first

1. `tests/unit/data/test_models.py`: model validation, enum parsing, `aggregation_kind` tagging.
2. `tests/unit/data/test_rollup.py`: count SUM rollup logic, median/rate rejection at aggregate level.
3. `tests/unit/data/test_execute_guard.py`: read-only guard, limit clamping.
4. `tests/unit/data/test_sql_templates.py`: every template loads and contains required binds.
5. `tests/component/data/test_repository_contract.py`: parametrized over `fake` and (live-only) `snowflake`.
6. `tests/unit/data/test_fake_repository.py`: ordering rules and fixture loading.
7. `tests/live/test_snowflake_repository.py`: opt-in smoke for each template.

## Files

- `app/data/__init__.py`, `models.py`, `repository.py`, `snowflake_repository.py`, `fake_repository.py`, `rollup.py`, `sql_loader.py`, `errors.py`
- `app/data/sql/*.sql`
- `scripts/snapshot_catalog.py`, `fixtures/variable_catalog_spec.yaml`, generated `fixtures/*.json`
- tests listed above

## Documentation updates at stage end

- `docs/data/dataset.md`: curated catalog section (topics and counts).
- `ARCHITECTURE.md`: data layer reflects implemented protocol.
- `CHANGELOG.md`, `docs/roadmap.md`, `docs/decision_log.md` if any template needed a workaround for the SafeGraph schema.
