# Extending Miniflake

How to add capability without touching more than the layer concerned. Component boundaries are described in [ARCHITECTURE.md](../ARCHITECTURE.md). Each section is completed with concrete file paths when the corresponding stage lands (see [roadmap.md](roadmap.md)).

## Add a tool (completed in S2)

1. Create `app/tools/<name>.py` with:
   - A pydantic input model subclassing `ToolInput` from `app/tools/base.py` (`extra="forbid"` so schemas get `additionalProperties: false`).
   - A `Success` payload model for the happy path.
   - A class implementing the `Tool` protocol: `name`, `description`, `input_model`, and `run(repository, input) -> ToolResult`.
2. Add an LLM-facing description to `app/tools/descriptions.yaml`.
3. If the tool needs a query the repository does not offer, add a method to `CensusRepository`, a SQL template under `app/data/sql/`, and implementations in both repositories; extend `tests/component/data/test_repository_contract.py`.
4. Register the tool in `default_registry` in `app/tools/registry.py`.
5. Write component tests under `tests/component/tools/` covering `Success` and every applicable outcome type (`Ambiguous`, `NotFound`, `PeriodUnavailable`, `UnsupportedRequest`). Add eval items to `evals/questions.yaml` when the tool changes agent behaviour.

Return explicit outcome types rather than raising for ambiguity or absence. Collect provenance from every repository call in call order.

## Add a data source (completed in S1)

The current implementation reads the SafeGraph US Open Census listing: wide ACS tables at block group grain plus metadata tables for field descriptions and FIPS mapping. Rollup logic lives in `app/data/rollup.py`.

Outline for a different source:

1. Implement `CensusRepository` (or a new protocol if the domain differs) in `app/data/`.
2. Provide a fake implementation and fixture snapshot for tests; run the shared contract suite against both.
3. Select the implementation in `app/main.py` via a configuration value.
4. If the new source has different geography levels, vintages or aggregation rules, update the catalog fixtures, `aggregation_kind` tagging and the system prompt's rendered summary.

## Swap the LLM provider (completed in S3)

1. Implement `LLMClient` in `app/llm/<provider>_client.py`. Map the provider-neutral types in `app/llm/types.py` (`Message`, `ContentBlock`, `ToolSchema`, `LLMResponse`) to the provider API and back. Raise `LLMError(message, retryable=...)` from `app/llm/errors.py` on failures.
2. If the provider supports strict tool schemas with a limited JSON Schema subset, add sanitization in the provider client (see `app/llm/schema_sanitize.py` and `AnthropicLLMClient`) rather than changing `ToolRegistry.schemas()`.
3. Preserve opaque provider blocks (for example Anthropic `thinking` blocks) as `OpaqueBlock` and echo them back verbatim within a tool-use turn.
4. Wire the client in `scripts/chat_cli.py` and, from S4 onward, in `app/main.py` via a configuration value such as `LLM_PROVIDER`.
5. Reuse component tests with `FakeLLM`; add a unit test with a stubbed HTTP transport for request mapping, response mapping, error classification, and retry behaviour.

## Swap the conversation store (completed in S4)

Outline:

1. Implement `ConversationStore` in `app/conversation/<backend>_store.py`.
2. Run the store unit tests against it (TTL, max turns, reset).
3. Select it via configuration.

## Adjust guardrails (completed in S5)

Outline: patterns and templates are YAML files under `app/guardrails/`; classifier thresholds and model are configuration values.

## Change the system prompt (completed in S3)

1. Edit `app/agent/prompts/system.md` for role, grounding rules, and answer format.
2. Edit `app/agent/prompts/templates.yaml` for timeout, iteration-cap, and error messages.
3. If the prompt needs new runtime values, extend `build_system_prompt` in `app/agent/prompt.py`.
4. Run `tests/unit/agent/test_prompt.py`, `tests/component/agent/test_loop.py`, and the eval set; record prompt-engineering decisions in the decision log.
