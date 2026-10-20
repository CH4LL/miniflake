# Changelog

All notable changes to this project. One entry per completed stage or feature; newest first.

## Unreleased

### Deployment: scale to zero by default

- `deploy/cloudrun.env`: `CLOUD_RUN_MIN_INSTANCES=0`, `CLOUD_RUN_CPU_ALWAYS_ALLOCATED=false`; `scripts/deploy.sh` passes `--no-cpu-boost --cpu-throttling` in that mode so a redeploy clears the previous boost setting.
- ARCHITECTURE, USER-GUIDE, README and ADR-006 updated for cold starts and conversation loss on scale-down; USER-GUIDE demo-auth wording corrected (page loads without auth, wrong passphrase shows "Invalid passphrase").

### S9: Documentation and reflection

- README: shipped-state status, example questions by eval category, full configuration reference (names and purposes), interpretations of ambiguous requirements.
- `REFLECTION.md` (repository root) filled: process and ADRs, more-time list including the S10 cut, edge cases, testing counts and eval reports, how Cursor was used.
- Testing strategy records default-suite counts; EXTENDING lists file paths that exist and wires extensions through `app/api/deps.py`.
- ARCHITECTURE and USER-GUIDE aligned (S0–S9, local port 8080, Place/CBSA cut).
- S10 marked `cut` on the roadmap; first decision-log `cut` entry.
- Documentation restructure: reflection moved to the repository root; README reorganised around demo evaluation, architecture summary, a key-decisions table and requirement interpretations, with the configuration reference moved to `docs/configuration.md`; decision log pruned to architecturally relevant entries without dates; ADR-003/004/005/007/008 brought up to the shipped state; ADR-009 (conversation context content), ADR-010 (time and tool budgets) and ADR-011 (outcome classification) added.

### S8: Evaluation and hardening

Eval harness
- `ItemResult` stores the raw `ChatObservation` and the golden note; failures are typed by kind (`outcome`, `clarify_slot`, `no_data_call`, `provenance`, `tool_budget`, `value`, `latency`).
- `run_evals.py --rescore <report.json>` re-scores a saved run offline against the current golden set and rules, reusing saved reference values (`--requery-values` refreshes them); the report records `rescored_from` and lists items no longer active.
- `--expected` filter alongside `--items` and `--categories`; `--questions` for an alternative golden set; `--workers N` runs root groups concurrently with one HTTP client each and records the worker count in the report header.
- Report groups failures by kind for triage, prints the golden note per item, and labels cost as agent tokens only.
- Runner accepts an injected HTTP client or client factory and question set; `tests/e2e/test_run_evals.py` runs it in-process against the app with fakes.
- Legacy report JSON without raw observations is rejected with a clear message.
- `evals/numbers.py` renamed to `evals/numeric.py` so running the script directly does not shadow the stdlib module.

Agent and guardrails
- New `capability` classifier intent; the pipeline returns a `proceed` decision carrying `ungrounded_answer_allowed`, which the service forwards to the agent loop and composer.
- `AnswerComposer` labels a turn with no tool traces `unanswerable` unless it is a capability turn; prose markers removed.
- `AGENT_MAX_SEARCH_CALLS` caps `find_variable` and `find_geography` dispatches per turn; past the cap the loop returns an `unsupported_request` result asking the model to explain what could not be found. The system prompt states the time and search budgets.
- Inner agent deadline is derived from the remaining API request window after guardrails, with a handoff margin; the loop skips tool dispatch when remaining time is below the per-LLM-call minimum. Hard agent, API, Cloud Run and eval HTTP timeouts sit above the response-budget target.
- Intent classifier no longer treats omitted ACS vintage as missing; named population questions do not clarify measure. System prompt defaults unspecified year to the latest 5-year vintage, maps population to B01003, steers multi-geography questions to `compare`, and asks for re-fetching on follow-ups.
- Removed output numeric grounding check; multi-turn answers may cite prior-turn figures.

Data layer
- Variable search is token-based: every significant query token must match the field title, label or id in any order; `fixtures/variable_catalog_spec.yaml` gains optional per-series `aliases` consulted by both repositories. SQL clauses are generated and parametrised.
- `CensusRepository.get_geographies(geo_ids)` batch lookup with SQL template and fake; `rank_geographies` and `compare` resolve names in one call.
- B17001 (poverty status) retagged `count`, enabling State and County rollups.
- `SnowflakeCensusRepository` reuses one Snowflake session per process via `is_closed()` and drops the session on a transient connection error.

Golden set
- Version 5: `max_tool_calls` per item; capability item M03; search-budget item MV04; `expected_missing` for clarify items; CF01 and L07 expect unanswerable, the latter because the field-description table exposes no poverty estimate rows.

Docs
- S8 spec rewritten as the offline-first plan; testing strategy documents harness modes, the committed run and its accepted failures; reflection edge cases and with-more-time items filled; architecture covers the eval harness, composer rules, search budget, token search and batch lookups; guardrails spec covers the capability intent.

Evaluation
- Golden-set run against the deployed service committed under `evals/reports/`, together with its offline re-score after the L07 correction; remaining failures are listed with reasons in the testing strategy.

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
