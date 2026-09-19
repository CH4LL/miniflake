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
