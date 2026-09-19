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
Stage: pre-S0 | Type: decision (provisional until S0)
What: Acquire both free listings; default the application to the long-format Census Bureau tables from Snowflake Public Data Products; record the SafeGraph listing as considered.
Why: Native State/County/CBSA/Place levels, ready-made variable catalog, multi-year coverage; block-group-only data would require aggregation that is invalid for medians and rates.
Dropped: SafeGraph as the sole source; exporting or caching data outside Snowflake.
Refs: ADR-003, specs/S0-foundations.md

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
