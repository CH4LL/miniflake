# Architecture

Miniflake is a data-grounded chat agent that answers natural-language questions about the US population using American Community Survey data served from Snowflake. This document describes the system's components and their boundaries. Which components exist at any moment is tracked in [docs/roadmap.md](docs/roadmap.md); the rationale behind each choice is in [docs/adr/](docs/adr/).

**Current implementation (S0–S3):** `app/config.py` (pydantic-settings), `app/main.py` (FastAPI app factory), `app/api/health.py` (`GET /api/health`), `app/data/` (`CensusRepository` protocol, `SnowflakeCensusRepository`, `FakeCensusRepository`, SQL templates, rollup logic), `app/tools/` (six typed tools, `ToolRegistry`, discriminated `ToolResult` outcomes, LLM descriptions in `descriptions.yaml`), `app/llm/` (`LLMClient` protocol, `AnthropicLLMClient`, `FakeLLM`, strict-schema sanitization), `app/agent/` (`AgentLoop`, file-based system prompt, `AnswerComposer`, error templates), `scripts/chat_cli.py`, `scripts/discover_schema.py`, `scripts/snapshot_catalog.py`, fixtures under `fixtures/`, Dockerfile, CI workflow, and deploy script. Conversation, guardrail, and web packages remain planned for later stages.

## Principles

- Answers come from data returned by tools, never from model memory. Every number in an answer traces back to a tool result and the provenance is returned with the answer.
- The LLM never writes SQL. It selects typed tools and fills their parameters; SQL is templated and parametrized inside the data layer.
- Every external dependency (LLM, database, conversation storage) sits behind a protocol with a fake implementation, so the whole request path is testable without network access.
- Adjustable values (model ids, timeouts, limits, warehouse names) live in configuration, never in code or documentation.

## Component overview

```mermaid
flowchart TB
    Browser["Static chat page (vanilla JS)"] --> API["FastAPI: /api/chat, /api/health, auth middleware"]
    API --> Conv["ConversationService"]
    Conv --> Store["ConversationStore (protocol) - InMemory impl"]
    Conv --> Guard["Guardrails: pre-checks, intent classifier, output grounding check"]
    Conv --> Agent["AgentLoop: system prompt, tool-use, iteration cap, time budget"]
    Agent --> LLM["LLMClient (protocol) - Anthropic impl / FakeLLM"]
    Agent --> Tools["ToolRegistry: find_geography, find_variable, get_value, rank_geographies, get_trend, compare"]
    Tools --> Repo["CensusRepository (protocol) - Snowflake impl / Fake impl"]
    Repo --> SF["Snowflake: SafeGraph Open Census"]
    Tools --> Prov["Provenance objects: variable, geography, period, SQL, rows"]
    Agent --> Composer["AnswerComposer: text + provenance + refusal templates"]
```

### Request lifecycle

1. The browser posts a message and a session cookie to `POST /api/chat`.
2. Auth middleware validates the demo session; the API layer wraps everything in a request-level time budget and a uniform error envelope.
3. `ConversationService` loads the conversation from `ConversationStore`, appends the user turn, and passes the history plus resolved context (last geography, measure, period) to the guardrails.
4. Guardrails run deterministic pre-checks, then an intent classification. Off-topic or harmful input is answered with a templated refusal without touching the data layer. Underspecified input is answered with a clarification.
5. `AgentLoop` calls the LLM with the system prompt, conversation history and tool schemas. The LLM either answers or requests tool calls; the loop executes tools through `ToolRegistry`, feeds results back, and repeats until the model answers, the iteration cap is hit, or the time budget expires.
6. Tools call `CensusRepository`, which runs parametrized SQL against Snowflake and returns typed rows plus a `Provenance` record. For count fields at state, county, place or nation level the repository sums block-group values; median and rate fields at those levels return `UnsupportedRequest`. Tools return typed results including explicit `Ambiguous`, `NotFound`, `PeriodUnavailable` and `UnsupportedRequest` outcomes.
7. `AnswerComposer` produces the final text, attaches provenance, and applies the output grounding check: numbers in the text must appear in tool results, otherwise the answer is replaced with a grounded degradation message.
8. The assistant turn and updated context are saved; the response is returned to the browser, which renders the text and an expandable provenance panel.

## Layers and boundaries

| Layer | Package | Responsibility | Depends on |
| :--- | :--- | :--- | :--- |
| Web UI | `web/` | Static chat page: message list, loading state, provenance expander, error display. | API contract only |
| API | `app/api/` | Routes, demo auth middleware, error envelope, request timeout. | Conversation |
| Conversation | `app/conversation/` | `ConversationStore` protocol, in-memory TTL implementation, `ConversationService` orchestrating guardrails and agent. | Guardrails, Agent |
| Guardrails | `app/guardrails/` | Pre-checks, intent classifier, output grounding check, refusal and clarification templates. | LLM |
| Agent | `app/agent/` | Tool-use loop, system prompt file, `AnswerComposer`. | LLM, Tools |
| LLM | `app/llm/` | `LLMClient` protocol, Anthropic implementation, scripted `FakeLLM`. | Provider SDK |
| Tools | `app/tools/` | Six typed tools (`find_geography`, `find_variable`, `get_value`, `rank_geographies`, `get_trend`, `compare`), `ToolRegistry`, discriminated `ToolResult` outcomes, provenance. | Data |
| Data | `app/data/` | `CensusRepository` protocol, Snowflake implementation, fake implementation, SQL templates, variable and geography catalog. | Snowflake connector |
| Config | `app/config.py` | pydantic-settings model holding every adjustable value. | Environment |

Dependencies point downward only. Nothing below the Agent layer imports from the Agent layer; nothing below Tools knows about the LLM.

## Extension points

- **New tool**: add a module in `app/tools/` with a pydantic input model, a result model and a `run(repository, input)` function, then register it in `ToolRegistry`. The LLM discovers it through the registry's generated schemas.
- **New data source**: implement `CensusRepository` (or a sibling protocol for a different domain) in `app/data/` and wire it in `app/main.py`.
- **Different LLM provider**: implement `LLMClient` in `app/llm/` and select it via configuration.
- **Persistent conversation storage**: implement `ConversationStore` and select it via configuration.

See [docs/EXTENDING.md](docs/EXTENDING.md) for step-by-step instructions.

## Package layout

```
app/
  main.py              FastAPI app factory, dependency wiring
  config.py            pydantic-settings (all adjustable values)
  api/                 routes, auth middleware, error envelope
  conversation/        ConversationStore protocol + in-memory impl, service
  agent/               loop, prompts/ (system prompt as file), composer
  llm/                 LLMClient protocol, anthropic client, fake
  tools/               one file per tool + registry
  data/                CensusRepository protocol, snowflake impl, fake impl, sql templates, catalog
  guardrails/          pre-checks, classifier, output checks
web/                   index.html, app.js, styles.css
tests/                 unit/, component/, e2e/, live/
evals/                 questions.yaml, run_evals.py, reports/
fixtures/              catalog snapshots, sample rows for fakes
scripts/               schema discovery, catalog snapshot, deploy
docs/                  requirements, roadmap, specs, ADRs, decision log
```

## Runtime topology

A single container runs FastAPI with uvicorn and serves both the API and the static UI. It is deployed to Google Cloud Run with secrets injected from Secret Manager. During evaluation the service is pinned to a single warm instance so the in-memory conversation store is coherent and cold starts do not consume the response budget. Snowflake is reached over the Python connector using a dedicated service user with key-pair authentication and a read-only role. The LLM is reached over the Anthropic Messages API.

## Data model

The agent works over the [SafeGraph US Open Census listing](https://app.snowflake.com/marketplace/listing/GZSNZ2UNN0/safegraph-us-open-census-data-neighborhood-insights-free-dataset) on Snowflake Marketplace. ACS 5-year estimates are stored at census block group grain in wide tables (one row per block group, ACS field codes as columns such as `B01003e1`), with metadata tables for field descriptions and FIPS-to-geography mapping. Exact Snowflake table names are documented in [docs/data/dataset.md](docs/data/dataset.md) after S0 discovery.

**Native geography level:** `BlockGroup` (12-digit FIPS).

**Derived levels** (via FIPS prefix and metadata): `Nation`, `State`, `County`. Place and CBSA are deferred to optional S10 (public-data supplement).

**Aggregation policy:**

| `aggregation_kind` | Block group | Rolled-up geography |
| :--- | :--- | :--- |
| `count` | Direct read | `SUM` across block groups; provenance records `aggregation_method: sum` |
| `median`, `rate` | Direct read | Not supported; returns `UnsupportedRequest` |

A snapshot of the variable catalog (with `aggregation_kind` tags) and supported geographies is stored under `fixtures/` and drives both the fake repository and the tool descriptions given to the LLM.

## Tool layer

Each tool returns a discriminated `ToolResult` with a `kind` field:

| Kind | Meaning |
| :--- | :--- |
| `success` | Data and provenance from repository calls |
| `ambiguous` | Multiple plausible matches; `hint` guides disambiguation |
| `not_found` | No match; optional `suggestions` from relaxed search |
| `period_unavailable` | Geography and variable exist but not for the requested vintage |
| `unsupported_request` | Well-formed but not expressible (e.g. median at county level) |
| `tool_error` | Repository failure; `retryable` indicates whether to retry |

`ToolRegistry.schemas()` emits provider-neutral JSON Schema for enabled tools. `dispatch` validates input, runs the tool, and maps repository errors to `ToolError` without propagating exceptions.

## LLM layer

`LLMClient` in `app/llm/client.py` defines a provider-neutral contract: `Message` with `TextBlock`, `ToolUseBlock`, `ToolResultBlock`, and `OpaqueBlock` (for passthrough of provider thinking blocks). `AnthropicLLMClient` uses the official Anthropic SDK with strict tool schemas, configurable model, effort, and thinking mode. Registry schemas are sanitized in the client before `strict: true` is applied. `FakeLLM` replays scripted responses for deterministic component tests.

## Agent core

`AgentLoop` in `app/agent/loop.py` builds the system prompt from `app/agent/prompts/system.md` plus rendered tool, geography, topic, and vintage summaries; calls the LLM with tool schemas from `ToolRegistry`; dispatches tool calls; echoes assistant content verbatim (including opaque thinking blocks); and stops on `end_turn`, iteration cap, or wall-clock budget. `AnswerComposer` in `app/agent/composer.py` classifies the outcome (`answer`, `clarify`, `unanswerable`, `error`) and replaces ungrounded numeric answers with a template from `app/agent/prompts/templates.yaml`. `scripts/chat_cli.py` runs a single turn against Snowflake and Anthropic for manual iteration.

## Testing

Four layers: unit tests with no network, component tests with `FakeCensusRepository` and `FakeLLM`, API end-to-end tests via `TestClient` with fakes injected, and opt-in live suites against Snowflake and Anthropic. A golden question set in `evals/questions.yaml` defines expected behaviour classes and is run against the deployed stack. See [docs/testing-strategy.md](docs/testing-strategy.md).
