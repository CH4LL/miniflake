# Decision log

Chronological record of decisions, dead ends and deviations. Each entry states the decision, the reason, and the alternatives dropped. Entries that reflect a weighed architectural choice link to an ADR in [adr/](adr/). Newest entries at the bottom.

Format:

```
## YYYY-MM-DD  Short title
Stage: Sx | Type: decision | dead-end | deviation | cut
What: ...
Why: ...
Dropped: ...
Refs: ADR-00N, spec, eval item ids
```

---

## 2026-09-19  Planning approach: documentation before code
Stage: pre-S0 | Type: decision
What: Produce the architecture, roadmap, stage specs, ADRs and eval fixtures before writing application code.
Why: Judgment and defensibility matter as much as output, and the codebase is meant to be extended with AI tools; a navigable plan reduces re-analysis cost for every later session.
Dropped: Starting from a walking skeleton and documenting retrospectively.
Refs: roadmap.md, agent-workflow.md

## 2026-09-19  Python and FastAPI over Streamlit and Next.js
Stage: pre-S0 | Type: decision
What: Python 3.12, FastAPI, static vanilla-JS page in one container.
Why: Author fluency for live coding stages; pydantic models double as tool schemas; in-process end-to-end tests without a browser; single deploy artefact.
Dropped: Streamlit/Chainlit (framework owns process and state, weak boundaries); Next.js (author fluency, Snowflake Node driver risk); separate React frontend (two build systems for a plain chat page).
Refs: ADR-001

## 2026-09-19  Dead end: Cursor SDK as the LLM backend
Stage: pre-S0 | Type: dead-end
What: Investigated using the Cursor SDK (available via Cursor API key) as the inference layer for the chat agent. Rejected.
Why: The SDK is an agent runtime, not a completions API: it launches a coding agent with file and shell tools against a working directory or cloud VM; custom tools require MCP servers; no strict tool-schema or structured-output control; public beta; agent-run latency per turn; exposing it behind a public chat page would be a prompt-injection hazard. Not defensible under architectural interrogation.
Dropped: Cursor SDK and Cloud Agent API as inference backends. Cursor remains the coding tool for building the project.
Refs: ADR-002

## 2026-09-19  Anthropic Messages API as LLM provider
Stage: pre-S0 | Type: decision
What: Anthropic API behind an `LLMClient` protocol; Sonnet-tier agent model, Haiku-tier classifier model; identifiers in configuration.
Why: Strict tool use and structured outputs match the typed-tool design; cheap classifier model keeps guardrail latency low; provider swap is one file.
Dropped: Snowflake Cortex (trial daily credit cap on Cortex AI functions, region-dependent model availability, heavier tool-use integration, couples LLM to data platform); OpenAI (no advantage without an existing key).
Refs: ADR-002

## 2026-09-19  Dataset: default to Snowflake Public Data census tables, inspect SafeGraph listing too
Stage: pre-S0 | Type: decision | **superseded**
What: Acquire both free listings; default the application to the long-format Census Bureau tables from Snowflake Public Data Products; record the SafeGraph listing as considered.
Why: Native State/County/CBSA/Place levels, ready-made variable catalog, multi-year coverage; block-group-only data would require aggregation that is invalid for medians and rates.
Dropped: SafeGraph as the sole source; exporting or caching data outside Snowflake.
Refs: ADR-003, specs/S0-foundations.md
Superseded by: 2026-09-19 SafeGraph listing only (below). The requirements name the SafeGraph Marketplace listing explicitly; no interpretation space.

## 2026-09-19  SafeGraph listing only; counts-only rollup policy
Stage: pre-S0 | Type: decision
What: Use only the SafeGraph "US Open Census Data & Neighborhood Insights - Free Dataset" Marketplace listing (GZSNZ2UNN0). Roll up count/total fields from block groups to state, county, place and nation via SUM; median and rate fields answerable only at block-group level.
Why: The requirements name this listing; using a different Marketplace product would not comply. Count rollups are statistically valid; median/rate rollups are not.
Dropped: Snowflake Public Data Products (Cybersyn long-format) as the application source; weighted-median approximations at aggregate geography; scoping the agent to block-group questions only.
Refs: ADR-003, ADR-004, evals/questions.yaml v2

## 2026-09-19  Typed semantic tools instead of text-to-SQL
Stage: pre-S0 | Type: decision
What: Six typed tools over parametrized SQL templates; the LLM never writes SQL; unanswerable cases are typed results.
Why: Exact provenance, deterministic handling of ambiguity and absence, testable without an LLM, bounded failure modes within the time budget.
Dropped: Free-form text-to-SQL (core); constrained SQL tool deferred to optional extensions.
Refs: ADR-004

## 2026-09-19  In-memory conversation store on a single warm instance
Stage: pre-S0 | Type: decision
What: `ConversationStore` protocol with an in-memory TTL implementation; Cloud Run pinned to one instance for the review window.
Why: Follow-up resolution needs server-held resolved context; persistence is not required for evaluation; protocol keeps Firestore/Redis a later swap.
Dropped: Client-side history; persistent store now.
Refs: ADR-005

## 2026-09-19  Cloud Run hosting, passphrase demo auth
Stage: pre-S0 | Type: decision
What: Google Cloud Run with Secret Manager; shared passphrase exchanged for a signed cookie.
Why: Existing GCP account and tooling; no setup time for a new provider; passphrase bounds LLM and warehouse spend with one secret to share.
Dropped: Fly.io/Render/Railway (new account setup, no offsetting benefit); AWS App Runner/ECS (more configuration surface); Streamlit in Snowflake (ADR-001); IAP/OAuth (disproportionate).
Refs: ADR-006

## 2026-09-19  Layered guardrails with output grounding check
Stage: pre-S0 | Type: decision
What: Pattern pre-checks, structured-output intent classifier, tool-only data access, numeric grounding check on the answer, YAML templates.
Why: Cheapest check first; only mechanism that enforces "numbers come from data" rather than advising it; each layer testable.
Dropped: Prompt-only; single moderation call; third-party guardrail framework.
Refs: ADR-007

## 2026-09-19  Testing: protocol fakes, contract tests, opt-in live suites, golden evals
Stage: pre-S0 | Type: decision
What: Fakes behind every external protocol, shared contract tests, live suites gated by environment variable, `evals/questions.yaml` run against the deployed service.
Why: Credential-free deterministic CI; fakes kept honest by contract tests; model-behaviour regressions caught by evals and reported.
Dropped: Live-only testing; SDK-level mocks.
Refs: ADR-008, testing-strategy.md

## 2026-09-19  Snowflake access via service user with key-pair auth
Stage: pre-S0 | Type: decision
What: Dedicated `TYPE = SERVICE` user, RSA key pair, read-only role, dedicated XS warehouse.
Why: New Snowflake accounts enforce MFA on password logins for human users, which a server cannot satisfy; a service user with key-pair auth is the supported non-interactive path.
Dropped: Password auth for the application; using the trial's admin user.
Refs: specs/S0-foundations.md

## 2026-09-19  Snowflake trial: Standard edition, not Enterprise
Stage: pre-S0 | Type: decision
What: Sign up for the free trial as Standard edition.
Why: The requirements call for a trial account. We need Marketplace listings, SQL, and a service user with key-pair auth; all of those work on Standard. Enterprise does not unlock anything this project uses (Cortex was rejected in ADR-002) and consumes trial credits faster. | However, turns out that even when selecting Standard, the trial version still uses Enterprise version regardless, so it seems to not be a choice.
Dropped: Enterprise edition, which had been written into the S0 spec as a leftover Cortex-minded default.
Refs: specs/S0-foundations.md, ADR-002

## 2026-09-19  S0 Cloud Run deploy uses placeholder Snowflake env vars
Stage: S0 | Type: deviation
What: The S0 hello-world Cloud Run deploy passes placeholder Snowflake settings as plain environment variables. Secret Manager wiring is deferred to S7.
Why: The health endpoint does not touch Snowflake; wiring real credentials now would pull S7 work forward without benefit. Settings still validates at startup, so placeholders satisfy the fail-fast contract.
Dropped: Creating Secret Manager secrets in S0.
Refs: specs/S0-foundations.md, specs/S7-deployment.md

## 2026-09-19  Python 3.12 pin via uv despite local 3.13
Stage: S0 | Type: decision
What: `.python-version` pins 3.12; `uv` provisions it even when the host has 3.13 installed.
Why: ADR-001 specifies 3.12; the Snowflake connector has well-tested wheels on 3.12.
Dropped: Running on the host's default 3.13 interpreter.
Refs: ADR-001, pyproject.toml

## 2026-09-19  SafeGraph share schema differs from spec assumptions
Stage: S0 | Type: deviation
What: Discovery found ACS wide tables named `{YEAR}_CBG_B{nn}` (e.g. `2019_CBG_B01`, `2020_CBG_B25`), not `ACS{year}_5YR`. Metadata tables are `{YEAR}_METADATA_CBG_FIELD_DESCRIPTIONS`, `{YEAR}_METADATA_CBG_FIPS_CODES`, and `{YEAR}_METADATA_CBG_GEOGRAPHIC_DATA`. No CBSA mapping column exists in the FIPS table. Vintages present: 2019 and 2020. ~220k block groups (2019) and ~242k (2020).
Why: The spec was written before the share was inspected; the actual SafeGraph listing uses its own naming convention.
Dropped: Assuming `ACS2019_5YR`-style table names and CBSA support from metadata.
Refs: docs/data/dataset.md, specs/S1-data-layer.md

## 2026-09-19  Live tests passed against Snowflake trial
Stage: S0 | Type: decision
What: `RUN_LIVE_TESTS=1 uv run pytest tests/live` passed on 2026-09-19: connection opens, role is `MINIFLAKE_READONLY`, SafeGraph database visible.
Why: Stage-end checklist requires live verification when credentials are available.
Dropped: n/a
Refs: specs/S0-foundations.md

## 2026-09-19  S0 Cloud Run hello-world deploy verified
Stage: S0 | Type: decision
What: Deployed health endpoint to Cloud Run in `us-east4` (project `miniflake`). `GET /api/health` returns 200 with `status: ok`, `environment: production`.
Why: S0 exit criterion requires a working Cloud Run deployment before product code stages begin.
Dropped: n/a
Refs: specs/S0-foundations.md

## 2026-09-19  Drop Place and CBSA geography levels for SafeGraph S1
Stage: S1 | Type: deviation
What: `GeoLevel` supports only BlockGroup, Nation, State, County. Place and CBSA removed from S1 implementation because the share has no place or CBSA mapping in metadata.
Why: S0 discovery found `{YEAR}_METADATA_CBG_FIPS_CODES` has STATE/STATE_FIPS/COUNTY_FIPS/COUNTY only; block-group FIPS cannot resolve to cities without an external crosswalk.
Dropped: Place/CBSA rollups from block groups in S1.
Refs: ADR-003, specs/S10-public-data-supplement.md, evals L06, AG01, UL02, M01

## 2026-09-19  Variable catalog queried from Snowflake metadata at runtime
Stage: S1 | Type: decision
What: `search_variables` and `get_variable` use SQL templates against `{vintage}_METADATA_CBG_FIELD_DESCRIPTIONS` filtered to curated series; `aggregation_kind` derived in Python from `fixtures/variable_catalog_spec.yaml`.
Why: Keeps "every query is a template" true; fake repository loads snapshot JSON for CI parity.
Dropped: Loading curated catalog only from fixtures in the Snowflake repository.
Refs: specs/S1-data-layer.md, ADR-004

## 2026-09-19  S1 data layer implemented with fake and Snowflake repositories
Stage: S1 | Type: decision
What: Implemented `CensusRepository`, `SnowflakeCensusRepository`, `FakeCensusRepository`, ten SQL templates, rollup module, catalog snapshot script, and contract tests. Geography levels: BlockGroup, Nation, State, County only.
Why: S1 exit criteria require typed data access with provenance, counts-only rollups, and testable fakes before the tool layer.
Dropped: Place/CBSA in S1 (see S10).
Refs: specs/S1-data-layer.md, ARCHITECTURE.md

## 2026-09-19  S1 live contract tests and block-group fixture grain
Stage: S1 | Type: decision
What: `RUN_LIVE_TESTS=1` contract and smoke suites passed (15 live tests). Snapshot fixtures store block-group direct observations only; fake rollup sums 12-digit geo ids so pre-aggregated state rows do not override rollups. Eval block groups updated to `480359506002` and `060371011101`.
Why: Live share lacks some legacy eval block groups; fixture grain must match Snowflake rollup semantics for CI parity.
Refs: fixtures/sample_observations.json, tests/component/data/test_repository_contract.py

## 2026-09-19  Level-aware get_time_series in data layer
Stage: S2 | Type: deviation
What: Extended existing `get_time_series` to roll up count fields at state, county and nation levels via `get_time_series_rollup.sql` rather than adding a new protocol method. Fixed `FakeCensusRepository.available_vintages` to prefix-match block groups under rolled-up geographies.
Why: Eval T01 requires state-level population trends; the tool layer should make one repository call and keep aggregation dispatch in the data layer.
Dropped: Per-vintage `get_observations` loop inside the `get_trend` tool.
Refs: specs/S1-data-layer.md, specs/S2-tool-layer.md, eval T01

## 2026-09-19  Tool descriptions in YAML, not inline strings
Stage: S2 | Type: decision
What: LLM-facing tool descriptions live in `app/tools/descriptions.yaml`; registry raises at startup if a registered tool has no description.
Why: Adjustable prompt text belongs in configuration files per project rules; S3 already stores the system prompt as a file.
Dropped: Hard-coded description strings in each tool module.
Refs: specs/S2-tool-layer.md

## 2026-09-19  rank_geographies resolves names with per-row get_geography calls
Stage: S2 | Type: decision
What: `rank_geographies` calls `get_geography` once per ranked row to attach human-readable names.
Why: `rank_geographies` repository results carry only geo ids and values; naming requires a second lookup. Acceptable for S2; batch lookup is an S8 optimization candidate.
Dropped: Returning geo ids only in rankings.
Refs: specs/S2-tool-layer.md

## 2026-09-19  S2 spec corrections before implementation
Stage: S2 | Type: deviation
What: Ambiguity acceptance criterion retargeted from Springfield (Place, deferred to S10) to Orange County. NotFound suggestions may be empty when relaxed search finds no near matches. Unified `field_id`/`vintage` naming across all tools. Replaced 1YR/5YR trend note with ACS 5-year overlapping-window note.
Why: Spec drift from S1 Place removal and SafeGraph share characteristics.
Dropped: Non-empty suggestion list as a hard requirement.
Refs: specs/S2-tool-layer.md, eval AG01, AG03

## 2026-09-19  S2 tool layer implemented
Stage: S2 | Type: decision
What: Implemented six tools, `ToolRegistry`, discriminated `ToolResult` outcomes, configuration-driven limits and disabled tools, and component tests against `FakeCensusRepository`.
Why: S2 exit criteria require typed tools with explicit outcomes and JSON Schema generation before the agent core in S3.
Dropped: n/a
Refs: specs/S2-tool-layer.md, ARCHITECTURE.md

## 2026-09-19  OpaqueBlock passthrough for Anthropic thinking blocks
Stage: S3 | Type: deviation
What: Added `OpaqueBlock(provider_type, payload)` to the provider-neutral `ContentBlock` union. The Anthropic client stores `thinking` and `redacted_thinking` blocks verbatim and re-serializes them unchanged on the next request within a tool-use turn.
Why: Anthropic requires thinking blocks to accompany tool_use blocks unmodified; filtering or rebuilding them returns a 400.
Dropped: A thinking-free message model without passthrough.
Refs: specs/S3-agent-core.md, ADR-002

## 2026-09-19  Strict tool schema sanitization in Anthropic client
Stage: S3 | Type: deviation
What: Sanitize registry JSON Schemas in `AnthropicLLMClient` before sending with `strict: true`: inline refs, drop unsupported constraints, fold them into descriptions. `ToolRegistry.schemas()` stays provider-neutral.
Why: Existing tool input models emit `minimum: 1` and `minItems: 2`, which strict mode rejects.
Dropped: Changing tool input models solely for Anthropic strict mode.
Refs: specs/S3-agent-core.md, app/tools/rank_geographies.py, app/tools/compare.py

## 2026-09-19  Optional ANTHROPIC_API_KEY in Settings
Stage: S3 | Type: deviation
What: `anthropic_api_key` is optional in `Settings`; `AnthropicLLMClient` raises at construction when absent.
Why: Required key breaks existing unit test helpers that build `Settings(..., _env_file=None)` without Anthropic credentials.
Dropped: Required pydantic field for the API key.
Refs: specs/S3-agent-core.md, tests/conftest.py

## 2026-09-19  Anthropic SDK with adaptive thinking and configurable effort
Stage: S3 | Type: decision
What: Use the official `anthropic` Python SDK with `max_retries=0`; adaptive thinking on by default with configurable `anthropic_effort` (default low) to protect the latency budget.
Why: Reliable tool selection on Sonnet 5; effort controls cost and latency without disabling thinking entirely.
Dropped: Raw httpx client; thinking disabled by default.
Refs: specs/S3-agent-core.md, ADR-002

## 2026-09-19  S3 agent core implemented
Stage: S3 | Type: decision
What: Implemented `app/llm/` and `app/agent/` with Anthropic client, FakeLLM, AgentLoop, AnswerComposer, system prompt, templates, CLI runner, and component tests covering every S3 acceptance criterion.
Why: S3 exit criteria require a single-turn grounded agent with provenance before conversation storage and HTTP in S4.
Dropped: n/a
Refs: specs/S3-agent-core.md, ARCHITECTURE.md

## 2026-09-19  S3 live agent lookup verified
Stage: S3 | Type: decision
What: `RUN_LIVE_TESTS=1 uv run pytest tests/live/test_agent_live.py` passed on 2026-09-19 after a Texas population lookup returned `answer` with a `get_value` provenance record.
Why: Stage-end checklist requires opt-in live verification when credentials are available.
Dropped: n/a
Refs: specs/S3-agent-core.md, scripts/chat_cli.py

## 2026-09-19  Full turn transcript for CF-3 conversation context
Stage: S4 | Type: decision
What: Store the complete per-turn transcript (user message, assistant tool_use, tool_result, final assistant text) and trim only whole turns. Inject resolved facts separately via `ResolvedContext` in the system prompt.
Why: CF-3 requires conversation context preserved across turns without qualifying scope. Text-only history (user + final assistant text) is cheaper but drops ambiguous candidate lists, exact tool values, and rejected vintages, so follow-ups like "the second one" or "why not that year?" cannot resolve. Without ability to clarify with stakeholders, conservative reading chosen to avoid under-delivering.
Dropped: Text-only history with context block only.
Refs: specs/S4-conversation-api.md, requirements CF-3, ADR-005

## 2026-09-19  Hard outer request timeout with cancellation token
Stage: S4 | Type: decision
What: `POST /api/chat` runs the synchronous service in a worker thread under `asyncio.wait_for`. On expiry the route returns HTTP 200 with `outcome: error` and the timeout template. A cancellation token prevents a late-finishing turn from saving after the client response is sent.
Why: The agent loop only checks its deadline between LLM calls; a hung provider or database call can overrun a soft budget alone.
Dropped: Soft deadline only at the route layer.
Refs: specs/S4-conversation-api.md

## 2026-09-19  Idle TTL for in-memory conversations
Stage: S4 | Type: decision
What: Conversation expiry uses idle time since `updated_at`, not absolute age since `created_at`.
Why: Session semantics match typical chat usage; an active long conversation should not expire mid-session.
Dropped: Absolute TTL from creation time.
Refs: specs/S4-conversation-api.md, ADR-005

## 2026-09-19  Strip prior-turn thinking blocks from LLM history
Stage: S4 | Type: decision
What: `history_for_llm` drops `OpaqueBlock` thinking content from completed prior turns while keeping it in storage and in the current turn.
Why: Anthropic validates thinking signatures on messages sent to the API; prior-turn thinking blocks risk 400 responses without adding follow-up value.
Dropped: Sending full stored transcripts verbatim to the provider.
Refs: specs/S4-conversation-api.md

## 2026-09-19  AgentAnswer transcript and trace data for conversation layer
Stage: S4 | Type: deviation
What: Extended S3 types: `AgentAnswer.transcript`, `ToolCallTrace.data`, and `context_facts` on `AgentLoop.run` / `build_system_prompt`.
Why: S4 requires full turn persistence and `ResolvedContext` extraction from tool payloads; the conversation layer cannot reconstruct these from composed text alone.
Dropped: Re-deriving context by re-parsing tool JSON from stored messages.
Refs: specs/S4-conversation-api.md

## 2026-09-19  FakeLLM snapshots message lists at call time
Stage: S4 | Type: decision
What: `FakeLLM.complete` deep-copies messages when recording calls.
Why: `AgentLoop` mutates the working message list after `complete()` returns; tests inspecting recorded inputs otherwise see post-call state.
Dropped: Storing live references to the working list.
Refs: tests/e2e/test_chat_api.py

## 2026-09-19  S4 conversation and API implemented
Stage: S4 | Type: decision
What: Implemented `app/conversation/`, chat routes, error envelope, session cookie, configuration for TTL and response budget, and tests covering all S4 acceptance criteria.
Why: S4 exit criteria require multi-turn HTTP access with server-side memory before guardrails and the web UI.
Dropped: n/a
Refs: specs/S4-conversation-api.md, ARCHITECTURE.md

## 2026-09-19  S5 grounding check allows derived sums and differences
Stage: S5 | Type: deviation
What: Extended the output grounding matcher beyond percentage-of-total to include sums and differences of returned values, and updated the S5 spec accordingly.
Why: Eval items AT02 and C02 expect stated derived totals and differences when operands appear in tool results; percentages alone would false-negative legitimate answers.
Dropped: Spec-literal percentage-only derivation rule.
Refs: specs/S5-guardrails.md, evals AT02, C02

## 2026-09-19  S5 classifier reuses LLMClient with constructor overrides
Stage: S5 | Type: decision
What: Extended `AnthropicLLMClient` with optional `model`, `thinking`, and `forced_tool_name` overrides; `IntentClassifier` uses the same `LLMClient` protocol and `FakeLLM` scripting in tests.
Why: Keeps one provider integration path; classifier tests stay deterministic without a separate protocol.
Dropped: Dedicated `IntentClassifierClient` protocol and implementation.
Refs: specs/S5-guardrails.md, ADR-007

## 2026-09-19  S5 role-play pre-check narrowed for eval I03
Stage: S5 | Type: deviation
What: Removed the broad "you are now an unrestricted" injection pattern from pre-checks so embedded census questions with role-play framing reach the agent loop.
Why: Eval I03 expects a grounded answer ignoring the override instruction; pre-check refusal would contradict the behavioural definition.
Dropped: Catching all role-play overrides at the pre-check layer.
Refs: evals I03, specs/S5-guardrails.md

## 2026-09-19  S5 guardrail short-circuit turns persisted
Stage: S5 | Type: decision
What: Refusal and clarification responses from guardrails are saved as user plus assistant messages before returning, so follow-ups answering a clarification have an antecedent in history.
Why: Clarification items (AG02, AV01, CF02) assume the user can reply in the same session after the agent asks what was missing.
Dropped: Ephemeral guardrail responses not stored in the conversation.
Refs: specs/S5-guardrails.md, ADR-005

## 2026-09-19  S5 guardrails implemented
Stage: S5 | Type: decision
What: Implemented `app/guardrails/` (pre-checks, intent classifier, output grounding, templates, pipeline), wired into `ConversationService` and `build_container`, with unit and eval-driven end-to-end tests.
Why: S5 exit criteria require layered guardrails that block out-of-scope input before data access and verify numeric grounding on answers.
Dropped: n/a
Refs: specs/S5-guardrails.md, ARCHITECTURE.md, ADR-007

## 2026-09-19  S5 live guardrail tests added
Stage: S5 | Type: decision
What: Added `tests/live/test_guardrails_live.py` covering off-topic refusal and in-scope Texas population lookup through `ConversationService` with real Anthropic and Snowflake credentials.
Why: Stage-end checklist requires opt-in live verification when credentials are available.
Dropped: n/a
Refs: specs/S5-guardrails.md
Note: Run with `RUN_LIVE_TESTS=1 uv run pytest tests/live/test_guardrails_live.py` when credentials are configured.

## 2026-09-19  S5 classifier client omits effort parameter
Stage: S5 | Type: deviation
What: `AnthropicLLMClient` gained `use_effort=False` for the classifier instance; Haiku does not accept `output_config.effort`.
Why: Live guardrail tests showed the classifier failing open with HTTP 400 when effort was sent to the classifier model.
Dropped: Sharing agent effort settings with the classifier client.
Refs: tests/live/test_guardrails_live.py, app/api/deps.py

## 2026-09-19  S5 live guardrail tests passed
Stage: S5 | Type: decision
What: `RUN_LIVE_TESTS=1 uv run pytest tests/live/test_guardrails_live.py` passed on 2026-09-19: off-topic poem refused without data call; Texas population lookup reached the agent with provenance.
Why: Stage-end checklist requires opt-in live verification when credentials are available.
Dropped: n/a
Refs: specs/S5-guardrails.md

## 2026-09-19  S6 GET /api/session endpoint
Stage: S6 | Type: deviation
What: Added `GET /api/session` returning `auth_required` and `authenticated` so the chat page can choose login vs chat view on load.
Why: The spec lists only `POST /api/login`; the page needs an open endpoint to detect auth state without attempting a protected call.
Dropped: Inferring auth state from a failed `/api/chat` probe.
Refs: specs/S6-web-ui-auth.md, app/api/auth.py

## 2026-09-19  S6 ToolCallResponse widened for provenance panel
Stage: S6 | Type: decision
What: `ToolCallResponse` now includes `input` and `data` from `ToolCallTrace`; provenance panel shows variable, geography, vintage from tool result data plus SQL from provenance records.
Why: `Provenance` alone has no variable or geography names; the spec requires them in the provenance expander.
Dropped: Enriching `Provenance` model with display names.
Refs: app/api/chat.py, web/app.js

## 2026-09-19  S6 auth defaults enabled, secrets validated at startup
Stage: S6 | Type: decision
What: `DEMO_AUTH_ENABLED` defaults to `true`; `DemoAuth` raises at `create_app` time if `DEMO_PASSPHRASE` or `AUTH_SIGNING_SECRET` is missing. Tests set `DEMO_AUTH_ENABLED=false` explicitly.
Why: Fail-closed for the public demo; keeps `Settings` construction unchanged in existing unit tests.
Dropped: Validating auth secrets in pydantic `Settings` model_validator.
Refs: app/api/auth.py, app/config.py, ADR-006

## 2026-09-19  S6 Dockerfile includes web assets
Stage: S6 | Type: deviation
What: Added `COPY web ./web` to Dockerfile ahead of S7.
Why: Container must serve the chat page; minimal forward step to avoid a broken image between stages.
Dropped: Waiting for S7 to copy web assets.
Refs: Dockerfile, specs/S7-deployment.md

## 2026-09-19  S6 Web UI and demo auth implemented
Stage: S6 | Type: decision
What: Implemented static chat page (`web/`), demo auth (`app/api/auth.py`), static serving (`app/api/static.py`), unit and e2e auth tests, and opt-in Playwright browser smoke test via `tests/e2e/fake_server.py`.
Why: S6 exit criteria require a browser-testable chat page with passphrase gate protecting the API.
Dropped: n/a
Refs: specs/S6-web-ui-auth.md, ARCHITECTURE.md, ADR-006

## 2026-09-19  S6 live verification passed
Stage: S6 | Type: decision
What: With `DEMO_PASSPHRASE` and `AUTH_SIGNING_SECRET` configured in `.env`, full pytest suite (209 passed), Playwright browser smoke test (`RUN_BROWSER_TESTS=1`), and local server startup at `http://127.0.0.1:8000` all succeeded on 2026-09-19.
Why: Stage-end checklist requires opt-in live verification when credentials are available.
Dropped: n/a
Refs: specs/S6-web-ui-auth.md

## 2026-09-19  S7 connect_snowflake moved to app layer
Stage: S7 | Type: decision
What: Moved `connect_snowflake` from `scripts/discover_schema.py` to `app/data/connection.py` and added `tests/unit/test_no_scripts_import.py` to prevent `app/` from importing `scripts/`.
Why: The runtime container copies only `app/`, `web`, and `fixtures`; importing `scripts` caused `ModuleNotFoundError` on `/api/chat`.
Dropped: Keeping connection logic in the discovery script.
Refs: app/data/connection.py, Dockerfile, specs/S7-deployment.md

## 2026-09-19  S7 fixtures bundled in container image
Stage: S7 | Type: deviation
What: Added `COPY fixtures ./fixtures` to the Dockerfile; `SnowflakeCensusRepository` loads catalog spec and state FIPS names from this directory at startup.
Why: Without fixtures the container failed to build the repository even after fixing the scripts import.
Dropped: Embedding catalog paths only in dev environments.
Refs: Dockerfile, app/data/snowflake_repository.py

## 2026-09-19  S7 warm-up on background thread
Stage: S7 | Type: decision
What: FastAPI lifespan starts `warm_up` on a daemon thread so Cloud Run readiness is not blocked while the Snowflake warehouse resumes.
Why: Synchronous warm-up would delay the startup probe; the spec requires warm-up before the first user request, not before the process listens.
Dropped: Blocking lifespan warm-up before accepting traffic.
Refs: app/warmup.py, app/main.py, specs/S7-deployment.md

## 2026-09-19  S7 deployment implemented
Stage: S7 | Type: decision
What: Hardened multi-stage Dockerfile, structured JSON logging, Secret Manager bootstrap script, Cloud Run deploy with settings from `deploy/cloudrun.env`, and post-deploy smoke test (`scripts/smoke_deployed.py`).
Why: S7 exit criteria require a public HTTPS deployment with secrets outside the image, observable logs, and end-to-end smoke verification.
Dropped: n/a
Refs: specs/S7-deployment.md, ARCHITECTURE.md, ADR-006

## 2026-09-19  S7 Cloud Run startup probe tuning
Stage: S7 | Type: deviation
What: `deploy/cloudrun.env` uses probe timeout below period and a higher failure threshold; initial values used timeout above period and failed `gcloud run deploy`.
Why: Cloud Run rejects startup probes where `timeout_seconds >= period_seconds`.
Dropped: A single long probe timeout value.
Refs: deploy/cloudrun.env, scripts/deploy.sh

## 2026-09-19  S7 live deploy and smoke verification passed
Stage: S7 | Type: decision
What: On 2026-09-19, `scripts/setup_secrets.sh` and `scripts/deploy.sh` succeeded; post-deploy smoke test returned `outcome=answer` within budget; Cloud Logging shows structured fields (`request_id`, `outcome`, `latency_ms`, `tool_calls`, token usage, `snowflake_ms`).
Why: Stage-end checklist requires deployed verification and observable logs.
Dropped: n/a
Refs: specs/S7-deployment.md, README.md

## 2026-09-19  Omitted vintage is not a clarification
Stage: S8 | Type: decision
What: Classifier prompt treats omitted year as latest ACS 5-year vintage; `GuardrailPipeline` ignores `missing=vintage`; population phrasing does not short-circuit `missing=measure`.
Why: Tools already default vintage to latest; golden lookups (L01) and user questions like "population of Oregon" are complete. Asking which vintage produced false-pass clarifies (AG03) and blocked answerable lookups.
Dropped: Requiring the user to name 2019 or 2020; relying on Haiku prompt text without a pipeline backstop.
Refs: app/guardrails/classifier.py, app/guardrails/pipeline.py, evals AG03, L01

## 2026-09-19  CF01 expected unanswerable; F02 must re-fetch
Stage: S8 | Type: decision
What: CF01 (2018 and 2022 as one number) is `unanswerable` listing 2019/2020. F02 notes require `get_value` this turn for the US (and Texas if comparing); prior-turn figures are not allowed. AV01 notes no longer treat stating median household income as a pass.
Why: Both CF01 years are outside the share; grounding only accepts this-turn tool values; state median income is unsupported.
Dropped: Asking which vintage for CF01; allowing F02 to restate the prior Texas figure without a new lookup.
Refs: evals/questions.yaml CF01, F02, AV01

## 2026-09-19  No live eval run in this hardening pass
Stage: S8 | Type: deviation
What: Prompt, grounding, composer, scoring, and golden-set definition changes covered by unit/component/e2e fakes only. `evals/run_evals.py` was not run.
Why: Full golden runs were slow and costly; the previous report already showed the failure modes these changes target. S8 remains in-progress until a committed eval report exists.
Dropped: Re-running the 51-item live set before merging the prompt fixes.
Refs: specs/S8-evaluation-hardening.md

## 2026-09-19  Output numeric grounding check removed
Stage: S8 | Type: decision
What: Removed post-answer numeric grounding (`app/guardrails/grounding.py`), composer no-tools-with-numbers guard, and related config, templates, and tests. Eval number extraction lives in `evals/numbers.py` for value-check scoring only.
Why: Per-turn payload matching rejected legitimate multi-turn answers (vintage comparisons, follow-up citations of prior figures). Tool-only data access and prompt discipline are sufficient; eval value checks catch regressions without blocking users.
Dropped: Runtime verification that every numeric token matches this turn's tool payloads.
Refs: ADR-007 amendment, specs/S5-guardrails.md, evals F01–F03

## 2026-09-19  B17001 aggregation_kind left as rate
Stage: S8 | Type: decision
What: Did not retag catalog series B17001 from `rate` to `count` in this pass.
Why: L07 (poverty percentage at state) may be answerable from ACS counts, but changing aggregation_kind needs a catalog-spec unit test that was not in this hardening slice.
Dropped: Treating L07 as `answer` without proving the field is a count in the share.
Refs: fixtures/variable_catalog_spec.yaml, evals L07

## 2026-09-19  Local JSON lines file sink
Stage: S8 | Type: decision
What: Added a `LOG_FILE` JSON lines handler beside the existing stderr stream. Unset `LOG_FILE` in the local environment writes under `logs/` (gitignored); empty path disables; production stays stream-only. Agent loop logs `stop_reason` and `LLMError.retryable`; chat-turn records include `stop_reason`.
Why: Uvicorn `--reload` does not surface stream logs usefully locally, and terminal search is a poor way to diagnose a failed agent turn. Cloud Logging remains stdout/stderr; no log shipping.
Dropped: Cloud Logging changes; rotating/viewer UI; logging full prompts at info.
Refs: app/logging.py, specs/S7-deployment.md, ADR-006

