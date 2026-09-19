# Changelog

All notable changes to this project. One entry per completed stage or feature; newest first.

## Unreleased

### S8: Agent timeout alignment
- Inner agent deadline is derived from the remaining API request window after guardrails, with a handoff margin so the loop timeout template wins over the outer route timeout.
- The response budget remains the normal-conditions target for evals and the system prompt; the hard agent/API timeout is longer so complex lookups can finish.
- Cloud Run and eval HTTP timeouts sit above that hard window.
- The agent loop skips further tool dispatch when remaining time is below the per-LLM-call minimum.
- Eval scoring asserts the eval latency budget default matches the product response budget.

### S8: Prompt and guardrail hardening
- Intent classifier no longer treats omitted ACS vintage as missing; the pipeline ignores `missing=vintage` and named population questions do not clarify measure.
- System prompt defaults unspecified year to the latest 5-year vintage, maps population to B01003, and steers multi-geography questions to `compare`.
- Removed output numeric grounding check and composer no-tools-with-numbers guard; multi-turn answers may cite prior-turn figures.
- Number extraction for eval value checks moved to `evals/numbers.py`.
- Golden set schema adds `expected_missing` for clarify items; CF01 expects unanswerable.

### Local JSON lines logging
- `configure_logging` appends JSON lines to `LOG_FILE` (gitignored `logs/` by default locally) while keeping the stderr stream handler for Cloud Logging.
- Agent loop logs `stop_reason` and `LLMError` details; chat-turn records include `stop_reason`.
- CLI runner (`scripts/chat_cli.py`) uses the same logging setup.

### Fixes
- Health endpoint reads settings from the injected application container so container-based e2e tests run in CI without Snowflake environment variables.

### S7: Deployment
- Multi-stage Dockerfile with digest-pinned base image, non-root user, runtime-only dependencies, and fixtures bundled for catalog loading.
- `connect_snowflake` moved from `scripts/` to `app/data/connection.py`; container no longer imports from `scripts/`.
- Structured JSON logging (`app/logging.py`) with request and chat-turn fields for Cloud Logging.
- Startup Snowflake warm-up on a background thread (`app/warmup.py`, `WARMUP_ENABLED`).
- `scripts/setup_secrets.sh` for idempotent Secret Manager bootstrap from `.env`.
- `scripts/deploy.sh` extended with Cloud Run settings from `deploy/cloudrun.env`, secret mounting, and post-deploy smoke test.
- `scripts/smoke_deployed.py` validates health, login, golden lookup question, and latency budget on the public URL.

### S6: Web UI and demo auth
- Static chat page at `/` with message list, outcome badges, provenance expander, loading indicator, error banner, and new-conversation button.
- `POST /api/login` and `GET /api/session` for passphrase-based demo authentication with HMAC-signed HTTP-only cookie.
- Auth middleware protecting `/api/chat` and `/api/conversations/*`; disabled via `DEMO_AUTH_ENABLED=false`.
- `ToolCallResponse` extended with `input` and `data` for provenance display.
- Unit, API end-to-end, and opt-in Playwright browser smoke tests.

### S5: Guardrails
- Layered guardrails: deterministic pre-checks (`patterns.yaml`), intent classifier on the cheap model, and output numeric grounding check.
- `GuardrailPipeline` wired into `ConversationService` before and after the agent loop; guardrail refusals and clarifications are persisted as turns.
- Refusal and clarification templates in `app/guardrails/templates.yaml`; adjustable `GUARDRAIL_*` settings.
- `AnthropicLLMClient` supports per-instance model, thinking mode, and forced tool choice for the classifier.
- Unit and eval-driven end-to-end tests for refuse, clarify, fail-open, and ungrounded-answer degradation.

### S4: Conversation and API
- `ConversationStore` protocol with `InMemoryConversationStore` (idle TTL, turn-boundary trimming, max conversations).
- `ConversationService` orchestrating load, optional guardrail hook, agent loop, and save with full turn transcripts.
- `ResolvedContext` derived from successful tool results and injected into the system prompt as recently discussed facts.
- `POST /api/chat` and `POST /api/conversations/reset` with session cookie, uniform error envelope, request-id middleware, and hard request timeout.
- End-to-end API tests covering multi-turn follow-ups, TTL expiry, validation, internal errors, timeout, and reset.
- Eval follow-up items in `evals/questions.yaml` (F01–F04) are now runnable against the HTTP API.

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
