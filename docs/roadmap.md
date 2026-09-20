# Roadmap

Single source of truth for what has been built and what comes next. An agent picking up work reads this file, finds the first stage whose status is not `done` or `cut`, and opens its spec under [specs/](specs/). The procedure is described in [agent-workflow.md](agent-workflow.md).

Status values: `todo`, `in-progress`, `done`, `cut`. Update the status field and the "Last updated" line whenever a stage changes state. Never reorder stages; if priorities change, record the reason in [decision_log.md](decision_log.md).

Total budget: 24 h. Estimates below sum to 22.5 h plus 1.5 h buffer.

Last updated: 2026-09-20 (S8 done; S9 next).

## Stages

| Stage | Name | Est. | Status | Spec |
| :--- | :--- | ---: | :--- | :--- |
| S0 | Foundations and walking skeleton | 3.0 h | done | [S0-foundations.md](specs/S0-foundations.md) |
| S1 | Data access layer | 3.0 h | done | [S1-data-layer.md](specs/S1-data-layer.md) |
| S2 | Tool layer | 2.0 h | done | [S2-tool-layer.md](specs/S2-tool-layer.md) |
| S3 | Agent core | 3.0 h | done | [S3-agent-core.md](specs/S3-agent-core.md) |
| S4 | Conversation and API | 2.0 h | done | [S4-conversation-api.md](specs/S4-conversation-api.md) |
| S5 | Guardrails | 2.0 h | done | [S5-guardrails.md](specs/S5-guardrails.md) |
| S6 | Web UI and demo auth | 2.0 h | done | [S6-web-ui-auth.md](specs/S6-web-ui-auth.md) |
| S7 | Deployment | 1.5 h | done | [S7-deployment.md](specs/S7-deployment.md) |
| S8 | Evaluation and hardening | 3.0 h | done | [S8-evaluation-hardening.md](specs/S8-evaluation-hardening.md) |
| S9 | Documentation and reflection | 2.0 h | todo | [S9-docs-reflection.md](specs/S9-docs-reflection.md) |
| S10 | Public data supplement | 2.0 h | todo | [S10-public-data-supplement.md](specs/S10-public-data-supplement.md) |

## Stage summaries

### S0 Foundations and walking skeleton

Goal: remove every external unknown before writing product code. Snowflake trial account with the SafeGraph Open Census listing acquired, service user with key-pair auth, discovery script that documents the share schema, Python project skeleton with configuration and health endpoint, container image, CI, and a hello-world deployment to Cloud Run.

Exit criteria: `GET /api/health` returns OK locally and on the Cloud Run URL; CI lint and tests green; `docs/data/dataset.md` filled from the discovery script with SafeGraph table layout.

### S1 Data access layer

Goal: a `CensusRepository` protocol with a Snowflake implementation over SafeGraph wide tables and metadata (read-only guard, timeouts, row caps, retry, counts-only rollup from block groups). SQL templates for geography lookup, variable search, value lookup, ranking and time series. Catalog snapshot script producing fixtures with `aggregation_kind` tags.

Exit criteria: every SQL template answers its fixture question in unit tests; fake repository passes the same contract tests as the Snowflake implementation; opt-in live smoke test passes.

### S2 Tool layer

Goal: typed tools over the repository with explicit outcome types (`Ambiguous`, `NotFound`, `PeriodUnavailable`), a `ToolRegistry` that emits LLM tool schemas, and a `Provenance` record per tool result. Tool descriptions written for the LLM.

Exit criteria: each tool has tests for the success path and each outcome type against the fake repository; registry emits valid JSON Schema for every tool.

### S3 Agent core

Goal: `LLMClient` protocol with Anthropic implementation and scripted `FakeLLM`; agent loop with iteration cap and wall-clock budget; system prompt as a file; `AnswerComposer` producing text, provenance and grounded refusals; CLI runner.

Exit criteria: FakeLLM-scripted tests cover happy path, clarification, unanswerable, timeout and tool error; one live CLI run answers a lookup question with provenance.

### S4 Conversation and API

Goal: `ConversationStore` protocol with in-memory TTL implementation, `ConversationService`, `POST /api/chat`, session cookie, uniform error envelope, request timeout, follow-up resolution from stored context.

Exit criteria: end-to-end tests with fakes cover a multi-turn follow-up, expired session, malformed input and internal error shapes.

### S5 Guardrails

Goal: deterministic pre-checks, intent classifier with structured output, refusal and clarification templates.

Exit criteria: every `refuse` item in `evals/questions.yaml` is refused without a data call; `clarify` items produce a clarification.

### S6 Web UI and demo auth

Goal: static chat page with message list, loading state, provenance expander and error display; passphrase login exchanged for a signed cookie; auth middleware protecting the API.

Exit criteria: browser smoke test against the local server completes a two-turn conversation; unauthenticated `POST /api/chat` is rejected.

### S7 Deployment

Goal: hardened container image, Secret Manager wiring, Cloud Run configuration (single warm instance, request timeout above the answer budget), structured JSON logging, deploy script, post-deploy smoke test, README access instructions.

Exit criteria: the public URL answers a golden lookup question end to end within the response budget; logs show request id, latency, tool calls and token usage.

### S8 Evaluation and hardening

Goal: make the eval harness cheap to iterate on without live runs (raw observations stored, offline re-scoring, in-process self-test), fix the deterministic causes behind the baseline report's failures with tests against fakes, curate the golden set, and record one honest live measurement for the reflection. The spec was superseded on 2026-09-20 (decision log); live runs are a measurement, not a development loop.

Exit criteria: suite green including the runner self-test; report from current `main` committed; strict-gate status recorded and every failure listed in the testing strategy with a reason; roadmap, changelog, architecture, testing strategy, reflection and decision log updated.


### S9 Documentation and reflection

Goal: final README, `docs/reflection.md`, `docs/testing-strategy.md`, `docs/EXTENDING.md`; ARCHITECTURE, USER-GUIDE and CHANGELOG synchronized.

Exit criteria: a reader with no context can run the project locally, access the demo and understand every architectural decision from the README and linked documents.

## Cut policy

If the remaining time is insufficient, cut in this order and record each cut in [decision_log.md](decision_log.md) and in the reflection:

1. S8 depth (run the golden set once, fix only blockers).
2. Provenance expander polish in the UI (fall back to a raw JSON block).
3. `get_trend` tool (time series answers).
4. `compare` tool (the model can call `get_value` twice).
Never cut: S0 to S4, the pre-checks and intent classifier of S5, S7, S9.

## Optional extensions (only after S9)

- **S10 Public data supplement**: Place and CBSA questions via `SNOWFLAKE_PUBLIC_DATA_FREE`; see [S10-public-data-supplement.md](specs/S10-public-data-supplement.md) for deferred eval items (L06, AG01, L05, R03).
- Constrained free-SQL tool with an allow-list validator, for questions the typed tools cannot express.
- Persistent `ConversationStore` (Firestore or Redis).
- Streaming responses.
- Result caching for repeated catalog lookups.
