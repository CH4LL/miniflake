# Changelog

All notable changes to this project. One entry per completed stage or feature; newest first.

## Unreleased

### S3: Agent core
- `LLMClient` protocol with provider-neutral messages, `AnthropicLLMClient` (strict tools, adaptive thinking, configurable effort), and scripted `FakeLLM`.
- `AgentLoop` with iteration cap, wall-clock budget, tool dispatch, and opaque thinking-block passthrough.
- File-based system prompt and error templates; `AnswerComposer` with grounded outcome classification.
- `scripts/chat_cli.py` for manual single-turn runs; opt-in live lookup test against Snowflake and Anthropic.

### S2: Tool layer
- Six typed tools over `CensusRepository` with discriminated `ToolResult` outcomes (`Success`, `Ambiguous`, `NotFound`, `PeriodUnavailable`, `UnsupportedRequest`, `ToolError`).
- `ToolRegistry` emitting JSON Schema tool definitions and dispatching calls with validation and error wrapping.
- LLM tool descriptions in `app/tools/descriptions.yaml`; tools disableable via configuration for cut policy.
- Level-aware `get_time_series` rollup in the data layer for state and county trends.

### Tooling
- Pre-commit hooks for Ruff format and lint; agent workflow documents explicit local checks matching CI.

### S1: Data access layer
- `CensusRepository` protocol with domain models, provenance, and counts-only rollup policy.
- `SnowflakeCensusRepository` with read-only SQL guard, row caps, retry, and parametrized templates under `app/data/sql/`.
- `FakeCensusRepository` backed by committed fixtures; shared contract tests in `tests/component/data/`.
- Catalog snapshot script (`scripts/snapshot_catalog.py`), curated variable spec, and state FIPS name fixture.
- Place and CBSA geography deferred to optional S10; affected eval items retargeted to `unanswerable`.
- Live Snowflake contract and smoke tests pass with `RUN_LIVE_TESTS=1`; snapshot fixtures use block-group grain for fake rollup parity.

### S0: Foundations and walking skeleton
- Python project skeleton with `uv`, pydantic-settings configuration, and `GET /api/health`.
- SafeGraph schema discovery script (`scripts/discover_schema.py`) generating `docs/data/dataset.md`.
- Dockerfile, GitHub Actions CI (ruff + pytest), and minimal Cloud Run deploy script.
- Live Snowflake connectivity verified; 2019 and 2020 ACS block-group wide tables discovered.

### Planning
- Architecture overview, stage roadmap (S0 to S9) with cut policy, per-stage specifications, ADR-001 to ADR-008, decision log, agent workflow, testing strategy, and the v1 golden question set in `evals/questions.yaml`.

### Dataset pivot
- Retargeted all documentation to the SafeGraph [US Open Census Data & Neighborhood Insights - Free Dataset](https://app.snowflake.com/marketplace/listing/GZSNZ2UNN0/safegraph-us-open-census-data-neighborhood-insights-free-dataset) as the sole Marketplace source (ADR-003 accepted).
- Adopted counts-only rollup policy: SUM for count fields from block groups to state/county/place/nation; median and rate fields at rolled-up geography declared unanswerable (ADR-004 amended).
- Revised S0/S1 specs for wide-table schema and metadata catalog; updated `evals/questions.yaml` to v2 with block-group median examples and unanswerable median/rate items at aggregate geography.
