# Decision log

Record of the decisions, dead ends and deviations that shaped the architecture, in the order they were made. Each entry states what was decided, why, and what was dropped. Entries that weighed alternative architectures link to an ADR in [adr/](adr/). Routine implementation work, verification runs and bug fixes are not logged here; the changelog and git history hold those.

Format:

```
## Short title
Stage: Sx | Type: decision | dead-end | deviation | cut
What: ...
Why: ...
Dropped: ...
Refs: ADR-00N, spec, eval item ids
```

---

## Planning approach: documentation before code
Stage: pre-S0 | Type: decision
What: Produce the architecture, roadmap, stage specs, ADRs and eval fixtures before writing application code.
Why: Judgment and defensibility matter as much as output, and the codebase is meant to be extended with AI tools; a navigable plan reduces re-analysis cost for every later session.
Dropped: Starting from a walking skeleton and documenting retrospectively.
Refs: roadmap.md, agent-workflow.md

## Python and FastAPI over Streamlit and Next.js
Stage: pre-S0 | Type: decision
What: Python 3.12, FastAPI, static vanilla-JS page in one container.
Why: Author fluency for live coding stages; pydantic models double as tool schemas; in-process end-to-end tests without a browser; single deploy artefact.
Dropped: Streamlit/Chainlit (framework owns process and state, weak boundaries); Next.js (author fluency, Snowflake Node driver risk); separate React frontend (two build systems for a plain chat page).
Refs: ADR-001

## Dead end: Cursor SDK as the LLM backend
Stage: pre-S0 | Type: dead-end
What: Investigated using the Cursor SDK (available via Cursor API key) as the inference layer for the chat agent. Rejected.
Why: The SDK is an agent runtime, not a completions API: it launches a coding agent with file and shell tools against a working directory or cloud VM; custom tools require MCP servers; no strict tool-schema or structured-output control; public beta; agent-run latency per turn; exposing it behind a public chat page would be a prompt-injection hazard. Not defensible under architectural interrogation.
Dropped: Cursor SDK and Cloud Agent API as inference backends. Cursor remains the coding tool for building the project.
Refs: ADR-002

## Anthropic Messages API as LLM provider
Stage: pre-S0 | Type: decision
What: Anthropic API behind an `LLMClient` protocol; Sonnet-tier agent model, Haiku-tier classifier model; identifiers in configuration.
Why: Strict tool use and structured outputs match the typed-tool design; cheap classifier model keeps guardrail latency low; provider swap is one file.
Dropped: Snowflake Cortex (trial daily credit cap on Cortex AI functions, region-dependent model availability, heavier tool-use integration, couples LLM to data platform); OpenAI (no advantage without an existing key).
Refs: ADR-002

## Dataset: Cybersyn default reversed to SafeGraph listing only
Stage: pre-S0 | Type: decision
What: The first plan acquired both free census listings and defaulted the application to the long-format Census Bureau tables from Snowflake Public Data Products, because they carry native State, County, CBSA and Place levels and a ready-made variable catalog. Reversed the same day: the application uses only the SafeGraph "US Open Census Data & Neighborhood Insights - Free Dataset" listing (GZSNZ2UNN0). Count fields roll up from block groups to county, state and nation via SUM; median and rate fields are answerable only at block-group level.
Why: The requirements name the SafeGraph listing explicitly, leaving no interpretation space; using a different Marketplace product would not comply. Count rollups are statistically valid; median and rate rollups are not.
Dropped: Snowflake Public Data Products (Cybersyn long-format) as the application source; weighted-median approximations at aggregate geography; scoping the agent to block-group questions only; exporting or caching data outside Snowflake.
Refs: ADR-003, ADR-004, evals/questions.yaml

## Typed semantic tools instead of text-to-SQL
Stage: pre-S0 | Type: decision
What: Six typed tools over parametrized SQL templates; the LLM never writes SQL; unanswerable cases are typed results.
Why: Exact provenance, deterministic handling of ambiguity and absence, testable without an LLM, bounded failure modes within the time budget.
Dropped: Free-form text-to-SQL (core); constrained SQL tool deferred to optional extensions.
Refs: ADR-004

## In-memory conversation store on a single warm instance
Stage: pre-S0 | Type: decision
What: `ConversationStore` protocol with an in-memory TTL implementation; Cloud Run pinned to one instance for the review window.
Why: Follow-up resolution needs server-held resolved context; persistence is not required for evaluation; protocol keeps Firestore/Redis a later swap.
Dropped: Client-side history; persistent store now.
Refs: ADR-005

## Cloud Run hosting, passphrase demo auth
Stage: pre-S0 | Type: decision
What: Google Cloud Run with Secret Manager; shared passphrase exchanged for a signed cookie.
Why: Existing GCP account and tooling; no setup time for a new provider; passphrase bounds LLM and warehouse spend with one secret to share.
Dropped: Fly.io/Render/Railway (new account setup, no offsetting benefit); AWS App Runner/ECS (more configuration surface); Streamlit in Snowflake (ADR-001); IAP/OAuth (disproportionate).
Refs: ADR-006

## Layered guardrails with output grounding check
Stage: pre-S0 | Type: decision
What: Pattern pre-checks, structured-output intent classifier, tool-only data access, numeric grounding check on the answer, YAML templates.
Why: Cheapest check first; only mechanism that enforces "numbers come from data" rather than advising it; each layer testable.
Dropped: Prompt-only; single moderation call; third-party guardrail framework.
Refs: ADR-007 (the grounding check was later removed; see below)

## Testing: protocol fakes, contract tests, opt-in live suites, golden evals
Stage: pre-S0 | Type: decision
What: Fakes behind every external protocol, shared contract tests, live suites gated by environment variable, `evals/questions.yaml` run against the deployed service.
Why: Credential-free deterministic CI; fakes kept honest by contract tests; model-behaviour regressions caught by evals and reported.
Dropped: Live-only testing; SDK-level mocks.
Refs: ADR-008, testing-strategy.md

## Snowflake access via service user with key-pair auth
Stage: pre-S0 | Type: decision
What: Dedicated `TYPE = SERVICE` user, RSA key pair, read-only role, dedicated XS warehouse.
Why: New Snowflake accounts enforce MFA on password logins for human users, which a server cannot satisfy; a service user with key-pair auth is the supported non-interactive path.
Dropped: Password auth for the application; using the trial's admin user.
Refs: specs/S0-foundations.md

## SafeGraph share schema differs from spec assumptions
Stage: S0 | Type: deviation
What: Discovery found ACS wide tables named `{YEAR}_CBG_B{nn}` (e.g. `2019_CBG_B01`), not `ACS{year}_5YR`. Metadata tables are `{YEAR}_METADATA_CBG_FIELD_DESCRIPTIONS`, `{YEAR}_METADATA_CBG_FIPS_CODES` and `{YEAR}_METADATA_CBG_GEOGRAPHIC_DATA`. No CBSA or place mapping exists in the FIPS table. Vintages present: 2019 and 2020.
Why: The spec was written before the share was inspected; the listing uses its own naming convention.
Dropped: Assuming `ACS2019_5YR`-style table names and CBSA support from metadata.
Refs: docs/data/dataset.md, specs/S1-data-layer.md

## Drop Place and CBSA geography levels
Stage: S1 | Type: deviation
What: `GeoLevel` supports only BlockGroup, Nation, State, County. Place and CBSA removed because the share has no place or CBSA mapping in metadata.
Why: `{YEAR}_METADATA_CBG_FIPS_CODES` has STATE/STATE_FIPS/COUNTY_FIPS/COUNTY only; block-group FIPS cannot resolve to cities without an external crosswalk.
Dropped: Place/CBSA rollups from block groups. Deferred to an optional supplement stage (S10), later cut.
Refs: ADR-003, specs/S10-public-data-supplement.md, evals L06, AG01, UL02, M01

## Variable catalog queried from Snowflake metadata at runtime
Stage: S1 | Type: decision
What: `search_variables` and `get_variable` use SQL templates against `{vintage}_METADATA_CBG_FIELD_DESCRIPTIONS` filtered to curated series; `aggregation_kind` derived in Python from `fixtures/variable_catalog_spec.yaml`.
Why: Keeps "every query is a template" true; fake repository loads snapshot JSON for CI parity.
Dropped: Loading the curated catalog only from fixtures in the Snowflake repository.
Refs: specs/S1-data-layer.md, ADR-004

## Aggregation dispatch lives in the data layer
Stage: S2 | Type: deviation
What: Extended `get_time_series` to roll up count fields at state, county and nation levels via a rollup template rather than looping per vintage in the `get_trend` tool.
Why: Eval T01 requires state-level trends; the tool layer should make one repository call and leave rollup semantics to the repository, where the counts-only policy is enforced.
Dropped: Per-vintage `get_observations` loop inside the tool.
Refs: specs/S1-data-layer.md, specs/S2-tool-layer.md, eval T01

## Tool descriptions in YAML, not inline strings
Stage: S2 | Type: decision
What: LLM-facing tool descriptions live in `app/tools/descriptions.yaml`; the registry raises at startup if a registered tool has no description.
Why: Adjustable prompt text belongs in configuration files; the system prompt is already a file.
Dropped: Hard-coded description strings in each tool module.
Refs: specs/S2-tool-layer.md

## Anthropic thinking blocks: opaque passthrough, stripped from prior turns
Stage: S3, S4 | Type: deviation
What: Added `OpaqueBlock(provider_type, payload)` to the provider-neutral `ContentBlock` union. The Anthropic client stores `thinking` and `redacted_thinking` blocks verbatim and re-serializes them unchanged within a tool-use turn. When building the LLM message list from stored history, thinking blocks from completed prior turns are dropped; they stay in storage.
Why: Anthropic requires thinking blocks to accompany tool_use blocks unmodified within a turn, and validates their signatures; prior-turn thinking risks 400 responses without adding follow-up value.
Dropped: A thinking-free message model; sending full stored transcripts verbatim to the provider.
Refs: specs/S3-agent-core.md, specs/S4-conversation-api.md, ADR-002, ADR-009

## Strict tool schema sanitization in the Anthropic client
Stage: S3 | Type: deviation
What: Registry JSON Schemas are sanitized inside `AnthropicLLMClient` before sending with `strict: true`: refs inlined, unsupported constraints dropped and folded into descriptions. `ToolRegistry.schemas()` stays provider-neutral.
Why: Tool input models emit constraints such as `minimum` and `minItems` that strict mode rejects; the provider's limits should not shape the tool models.
Dropped: Changing tool input models solely for Anthropic strict mode.
Refs: specs/S3-agent-core.md, app/llm/anthropic_client.py

## Adaptive thinking with configurable effort
Stage: S3 | Type: decision
What: Official `anthropic` SDK with `max_retries=0` (retry policy is the agent loop's); adaptive thinking on by default with a configurable effort level to protect the latency budget.
Why: Reliable tool selection needs thinking; effort controls cost and latency without disabling it.
Dropped: Raw httpx client; thinking disabled by default.
Refs: specs/S3-agent-core.md, ADR-002

## Full turn transcript for CF-3 conversation context
Stage: S4 | Type: decision
What: Store the complete per-turn transcript (user message, assistant tool_use, tool_result, final assistant text) and trim only whole turns. Inject resolved facts separately via `ResolvedContext` in the system prompt. To make this possible `AgentAnswer` carries the transcript and each `ToolCallTrace` carries the tool payload.
Why: CF-3 requires conversation context preserved across turns without qualifying scope. Text-only history (user plus final assistant text) is cheaper but drops ambiguous candidate lists, exact tool values and rejected vintages, so follow-ups like "the second one" or "why not that year?" cannot resolve. Without the ability to clarify with stakeholders, the conservative reading was chosen to avoid under-delivering.
Dropped: Text-only history with a summary block; re-deriving context by re-parsing tool JSON from stored messages.
Refs: specs/S4-conversation-api.md, requirements CF-3, ADR-005, ADR-009

## Hard outer request timeout with cancellation token
Stage: S4 | Type: decision
What: `POST /api/chat` runs the synchronous service in a worker thread under `asyncio.wait_for`. On expiry the route returns HTTP 200 with `outcome: error` and the timeout template. A cancellation token prevents a late-finishing turn from saving after the response is sent.
Why: The agent loop only checks its deadline between LLM calls; a hung provider or database call can overrun a soft budget alone.
Dropped: Soft deadline only at the route layer.
Refs: specs/S4-conversation-api.md, ADR-010

## Idle TTL for in-memory conversations
Stage: S4 | Type: decision
What: Conversation expiry uses idle time since the last update, not absolute age since creation.
Why: Session semantics match typical chat usage; an active long conversation should not expire mid-session.
Dropped: Absolute TTL from creation time.
Refs: specs/S4-conversation-api.md, ADR-005

## Classifier reuses LLMClient with constructor overrides
Stage: S5 | Type: decision
What: `AnthropicLLMClient` gained optional model, thinking and forced-tool overrides; `IntentClassifier` uses the same `LLMClient` protocol and `FakeLLM` scripting in tests.
Why: One provider integration path; classifier tests stay deterministic without a separate protocol.
Dropped: Dedicated classifier client protocol and implementation.
Refs: specs/S5-guardrails.md, ADR-007

## Role-play pre-check narrowed so embedded questions reach the agent
Stage: S5 | Type: deviation
What: Removed the broad "you are now an unrestricted ..." injection pattern from pre-checks; role-play framings that wrap a census question reach the agent loop, which ignores the override.
Why: Eval I03 expects a grounded answer that ignores the instruction; a pre-check refusal would contradict the behavioural definition and block a legitimate question.
Dropped: Catching all role-play overrides at the pre-check layer.
Refs: evals I03, specs/S5-guardrails.md, ADR-007

## Guardrail short-circuit turns persisted
Stage: S5 | Type: decision
What: Refusal and clarification responses from guardrails are saved as user plus assistant messages before returning.
Why: A follow-up that answers a clarification needs its antecedent in history (evals AG02, AV01, CF02).
Dropped: Ephemeral guardrail responses not stored in the conversation.
Refs: specs/S5-guardrails.md, ADR-005

## Demo auth on by default, secrets validated at startup
Stage: S6 | Type: decision
What: `DEMO_AUTH_ENABLED` defaults to true; `DemoAuth` raises at app construction if the passphrase or signing secret is missing. Tests disable auth explicitly.
Why: Fail-closed for the public demo; a misconfigured deploy refuses to start rather than serving an open endpoint.
Dropped: Validating auth secrets inside the pydantic `Settings` model (would break credential-free unit tests).
Refs: app/api/auth.py, app/config.py, ADR-006

## Warm-up on a background thread
Stage: S7 | Type: decision
What: FastAPI lifespan starts a Snowflake warm-up on a daemon thread so Cloud Run readiness is not blocked while the warehouse resumes.
Why: Synchronous warm-up would delay the startup probe; the requirement is warm-up before the first user request, not before the process listens.
Dropped: Blocking lifespan warm-up before accepting traffic.
Refs: app/warmup.py, app/main.py, specs/S7-deployment.md

## Omitted vintage is not a clarification
Stage: S8 | Type: decision
What: The classifier prompt treats an omitted year as the latest ACS 5-year vintage; the pipeline ignores `missing=vintage`; population phrasing does not short-circuit `missing=measure`.
Why: Tools already default the vintage; "population of Oregon" is a complete question. Asking which vintage produced false clarifications (AG03, UP01–UP03) and blocked answerable lookups.
Dropped: Requiring the user to name a vintage; relying on the classifier prompt alone without a pipeline backstop.
Refs: app/guardrails/classifier.py, app/guardrails/pipeline.py, evals AG03, L01, UP01–UP03

## Output numeric grounding check removed
Stage: S8 | Type: decision
What: Removed the post-answer numeric grounding check and the composer's no-tools-with-numbers guard. Number extraction survives only in the eval harness for value-check scoring. The check had earlier been widened to accept sums and differences of returned values (evals AT02, C02); that widening was not enough.
Why: Per-turn payload matching rejected legitimate multi-turn answers such as vintage comparisons and follow-ups citing a prior turn's figure. Tool-only data access and prompt discipline are the grounding mechanism; eval value checks catch regressions without blocking users.
Dropped: Runtime verification that every numeric token matches this turn's tool payloads.
Refs: ADR-007 amendment, specs/S5-guardrails.md, evals F01–F03

## Time budgets: 60 s is the target, hard timeouts are longer
Stage: S8 | Type: decision
What: `RESPONSE_BUDGET_SECONDS` is the CF-4 normal-conditions target used for eval latency scoring and the system-prompt time hint. The hard agent budget and the API `wait_for` sit above it, and Cloud Run and eval HTTP timeouts above those. The agent loop's deadline is derived per turn from the remaining API window after guardrails, minus a handoff margin, and the loop refuses to dispatch another tool when remaining time is below the per-LLM-call minimum.
Why: CF-4 requires complete responses within 60 seconds under normal conditions, not that every request is killed at 60 s. A follow-up turn was observed stopping on a fixed inner cap while the API window still had headroom, and a late tool call was observed running past the deadline because time was only checked before LLM calls.
Dropped: Using the response budget as the hard API timeout; a fixed inner cap independent of the API window; ungated tool dispatch.
Refs: requirements CF-4, specs/S3-agent-core.md, specs/S4-conversation-api.md, app/config.py, ADR-010

## S8 spec superseded: offline-first hardening
Stage: S8 | Type: deviation
What: Rewrote the S8 spec. The 22 failures in the baseline report were triaged by cause before any change: six were correct "not supported" replies mislabelled by the composer's phrase list, two were capability answers needing `answer` without tools, five were search thrash, two were latency tails from N+1 lookups, five were grounding false negatives, six were classifier prompt issues, two were model behaviour. Behaviour fixes are then proven against fakes; the harness gains raw-observation storage, offline re-scoring and an in-process end-to-end test; one live run at the end produces the committed report.
Why: The planned run-fix-rerun loop over the live golden set took over ten minutes and several dollars per iteration and surfaced one fixation at a time. Grouping by cause showed most strict-gate failures were deterministic and testable without an LLM.
Dropped: Iterative live eval runs as the development loop; fixing items one at a time from the report.
Refs: specs/S8-evaluation-hardening.md, evals/reports/20260919T133835Z.md, ADR-008 amendment

## Outcomes typed from tool results and classifier intent, never from prose
Stage: S8 | Type: decision
What: Removed the composer's "not supported" phrase list. A turn without tool traces is `unanswerable`; it is `answer` only when the guardrail pipeline marked the turn `capability` and passed `ungrounded_answer_allowed` through to the agent loop. Added the `capability` intent to the classifier and a `proceed` guardrail decision that does not short-circuit.
Why: The phrase list caused six strict-gate failures and could never be complete. The system prompt requires tool calls before any figure, so a no-tool reply is by construction not a data answer; capability questions are the one legitimate exception and the classifier already had to recognise them.
Dropped: Terminal pseudo-tools (`declare_unanswerable`, `ask_clarification`) that the model would call to state its outcome, a behaviour change that could not be verified against `FakeLLM` without scripting the new tool in every test; inferring `clarify` from a question mark in no-tool text.
Refs: app/agent/composer.py, app/guardrails/pipeline.py, app/conversation/service.py, evals M01–M03, MV01, UL01, ADR-011

## Search-call budget in the agent loop
Stage: S8 | Type: decision
What: `AGENT_MAX_SEARCH_CALLS` counts `find_variable` and `find_geography` dispatches per turn. Past the cap the loop records an `UnsupportedRequest` telling the model to stop searching and explain what could not be found. The system prompt states the budget.
Why: Poverty and education queries (L07, AV02) spent the whole time budget on six catalog searches with no data call. A hard cap bounds the cost of a bad query regardless of prompt compliance; the composer already maps a trace set with no data-tool success to `unanswerable`.
Dropped: Counting all tool calls (data tools are bounded by the iteration cap); returning `ToolError` (would label the turn `error`).
Refs: app/agent/loop.py, app/config.py, app/agent/prompts/system.md, evals L07, AV02, MV04, ADR-010

## Token-based variable search with curated aliases
Stage: S8 | Type: decision
What: `search_variables` splits the query into significant tokens and requires every token to appear in title, field label or id, in any order; generated parametrised `LIKE` clauses in SQL, the same rule in Python for the fake. `variable_catalog_spec.yaml` gains optional `aliases` per series, OR-ed into the result when their tokens overlap the query. Contract tests hold fake and live to parity.
Why: Whole-phrase substring matching made "population below poverty line" and "how educated" match nothing, which was the root cause of the search thrash. Aliases cover phrasings no token of the ACS title contains.
Dropped: Full-text or semantic search in Snowflake (not available on the shared listing without extra objects); matching on `TABLE_TOPICS` (too broad); LLM-generated aliases (kept curated and reviewable).
Refs: app/data/search_utils.py, app/data/sql/search_variables.sql, fixtures/variable_catalog_spec.yaml, tests/component/data/test_repository_contract.py

## Batch geography names
Stage: S8 | Type: decision
What: Added `CensusRepository.get_geographies(geo_ids)`; `rank_geographies` and `compare` resolve names in one call instead of one `get_geography` per row, which S2 had accepted as a known cost.
Why: A ten-row ranking issued ten metadata queries, visible in the latency tails of F04 and AT02.
Dropped: Caching names in process (batching removes the need); a name column on the rollup query (would join the wide table to metadata on every ranking).
Refs: app/data/repository.py, app/data/sql/get_geographies.sql, app/tools/rank_geographies.py, app/tools/compare.py

## Eval harness stores raw observations and re-scores offline
Stage: S8 | Type: decision
What: Each eval result carries the raw `/api/chat` observation and typed failures; `evals/rescore.py` rebuilds observations from a saved report and re-scores against the current golden set and rules. The runner accepts filters and a worker pool, and its HTTP client and question set are injectable so it is tested end to end against the app with fakes.
Why: Every scoring-rule change previously forced a live rerun. Stored observations make a report self-describing and re-scorable for free; typed failure kinds allow grouping for triage.
Dropped: Re-scoring legacy reports by heuristics; sharing one HTTP client across workers (cookies would mix conversations).
Refs: evals/scoring.py, evals/rescore.py, evals/run_evals.py, tests/e2e/test_run_evals.py, ADR-008 amendment

## Final live run: two outcome failures accepted
Stage: S8 | Type: decision
What: One live run of the full golden set against the deployed service (`20260920T002700Z`) and its offline re-score (`20260920T004303Z`). 51 of 53 items pass. AG01 and UL02 fail on outcome and are accepted.
Why: Both ask about a geography the dataset cannot express (an ambiguous place, a street address) and the classifier asks which geography is meant before the agent can explain the limit. Separating "ambiguous" from "below the smallest supported grain" needs a place and address catalogue the dataset does not carry.
Dropped: Fixing and re-running; widening pre-checks to catch street addresses by pattern, which would guess at a limit the data layer cannot confirm.
Refs: evals/reports/20260920T002700Z.md, evals/reports/20260920T004303Z.md, testing-strategy.md

## Curated catalogue advertises series the share does not populate
Stage: S8 | Type: deviation
What: `B17001` (poverty) was retagged from `rate` to `count`, because its fields are counts that roll up via SUM, and aliases were added so it is findable. The live run then showed that the marketplace field-description table returns no estimate rows for the poverty, housing, health insurance and commuting series the catalogue spec lists. L07 therefore expects `unanswerable`; the tag and aliases stay.
Why: The S1 catalog snapshot had already produced no fields for those topics, and the alias search adds the series by id, so nothing can make the measure findable. An `answer` expectation would pin behaviour the data cannot produce.
Dropped: Trimming the catalogue spec to reachable series (needs a live metadata query to verify; recorded as remaining work in the reflection); a value check for a ratio of two fields.
Refs: fixtures/variable_catalog_spec.yaml, evals L07, testing-strategy.md

## Cut S10 public data supplement
Stage: S9 | Type: cut
What: S10 (Place and CBSA via `SNOWFLAKE_PUBLIC_DATA_FREE`) is cut. The SafeGraph share remains the sole data source. Eval items L05, L06, R03 and AG01 keep `expected: unanswerable`.
Why: The core roadmap through S9 (never-cut documentation) consumed the remaining window. S10 was always an optional extension after S9, not in the original cut order.
Dropped: A second `CensusRepository` over public-data native Place/CBSA tables; restoring those eval items to `answer`.
User-visible consequence: city and metro questions stay unanswerable; the agent explains the supported geography levels instead of looking up Denver, Springfield as a place, Seattle metro, or metro rankings.
Refs: specs/S10-public-data-supplement.md, roadmap.md, ADR-003, evals L05 L06 R03 AG01

## Default deployment scales to zero
Stage: post-S9 | Type: change
What: `deploy/cloudrun.env` sets minimum instances to 0 and CPU always allocated to false; `scripts/deploy.sh` then deploys with `--no-cpu-boost --cpu-throttling`. Maximum instances stays at 1.
Why: The review window is over; an always-on instance costs money while idle.
Dropped: Keeping a pinned warm instance with always-allocated CPU and startup boost (still available by editing `deploy/cloudrun.env`).
User-visible consequence: the first question after an idle period pays the container cold start and warehouse resume; conversations are lost when the instance scales down.
Refs: deploy/cloudrun.env, scripts/deploy.sh, ADR-006
