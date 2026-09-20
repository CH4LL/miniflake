# Extending Miniflake

How to add capability without touching more than the layer concerned. Component boundaries are described in [ARCHITECTURE.md](../ARCHITECTURE.md).

There is no provider-switch configuration flag. Production wiring is `build_container` in `app/api/deps.py`; the CLI constructs the same types in `scripts/chat_cli.py`. Tests inject fakes through the `create_app(container=...)` factory in `app/main.py`.

## Add a tool

1. Create `app/tools/<name>.py` with:
   - A pydantic input model subclassing `ToolInput` from `app/tools/base.py` (`extra="forbid"` so schemas get `additionalProperties: false`).
   - A `Success` payload model for the happy path.
   - A class with `name`, `description`, `input_model`, and `run(repository, input) -> ToolResult` (see `GetValueTool` in `app/tools/get_value.py`). The `Tool` protocol is in `app/tools/base.py`.
2. Add an LLM-facing description to `app/tools/descriptions.yaml`.
3. If the tool needs a query the repository does not offer, add a method to `CensusRepository` in `app/data/repository.py`, a SQL template under `app/data/sql/`, and implementations in `app/data/snowflake_repository.py` and `app/data/fake_repository.py`; extend `tests/component/data/test_repository_contract.py`.
4. Register the tool in `default_registry` in `app/tools/registry.py`.
5. Write component tests under `tests/component/tools/` covering `Success` and every applicable outcome type (`Ambiguous`, `NotFound`, `PeriodUnavailable`, `UnsupportedRequest`). Add eval items to `evals/questions.yaml` when the tool changes agent behaviour.

Return explicit outcome types rather than raising for ambiguity or absence. Collect provenance from every repository call in call order. A tool can be omitted at runtime via `DISABLED_TOOLS` without deleting it.

## Add a data source

The current implementation reads the SafeGraph US Open Census listing: wide ACS tables at block group grain plus metadata tables for field descriptions and FIPS mapping. Rollup logic lives in `app/data/rollup.py`. Variable search (token match plus aliases) lives in `app/data/search_utils.py` and `app/data/sql/search_variables.sql`.

For a different source:

1. Implement `CensusRepository` from `app/data/repository.py` (or a new protocol if the domain differs) as `app/data/<source>_repository.py`.
2. Provide a fake implementation (`app/data/fake_repository.py` is the pattern) and a fixture snapshot under `fixtures/`; run `tests/component/data/test_repository_contract.py` against both.
3. Construct the new class in `build_container` in `app/api/deps.py` (and in `scripts/chat_cli.py` if the CLI should use it).
4. If the new source has different geography levels, vintages or aggregation rules, update `fixtures/variable_catalog_spec.yaml`, `aggregation_kind` tagging, and the summaries rendered by `app/agent/prompt.py`.

Place and CBSA support was specified as optional S10 and is cut; a second repository for `SNOWFLAKE_PUBLIC_DATA_FREE` would follow this section. See [specs/S10-public-data-supplement.md](specs/S10-public-data-supplement.md) and the cut entry in [decision_log.md](decision_log.md).

## Swap the LLM provider

1. Implement `LLMClient` from `app/llm/client.py` in `app/llm/<provider>_client.py`. Map the provider-neutral types in `app/llm/types.py` (`Message`, `ContentBlock`, `ToolSchema`, `LLMResponse`) to the provider API and back. Raise `LLMError(message, retryable=...)` from `app/llm/errors.py` on failures.
2. If the provider supports strict tool schemas with a limited JSON Schema subset, add sanitization in the provider client (see `app/llm/schema_sanitize.py` and `AnthropicLLMClient` in `app/llm/anthropic_client.py`) rather than changing `ToolRegistry.schemas()`.
3. Preserve opaque provider blocks (for example Anthropic `thinking` blocks) as `OpaqueBlock` and echo them back verbatim within a tool-use turn.
4. Construct the new client in `build_container` (`app/api/deps.py`) for both the agent `llm` and the classifier `classifier_llm` (the classifier currently reuses `AnthropicLLMClient` with a different model and `forced_tool_name="classify_intent"`). Update `scripts/chat_cli.py` the same way.
5. Reuse component tests with `FakeLLM` in `app/llm/fake.py`; add a unit test with a stubbed HTTP transport for request mapping, response mapping, error classification, and retry behaviour (see `tests/unit/llm/test_anthropic_client.py`).

## Swap the conversation store

1. Implement `ConversationStore` from `app/conversation/store.py` as `app/conversation/<backend>_store.py`. The in-memory reference is `app/conversation/memory_store.py`.
2. Run `tests/unit/conversation/test_store.py` against it (TTL, max turns, max conversations, reset).
3. Change the `store` field type on `AppContainer` and the constructor call in `build_container` (`app/api/deps.py`) from `InMemoryConversationStore` to the new class (or to the `ConversationStore` protocol).

## Adjust guardrails

- Pre-check patterns: `app/guardrails/patterns.yaml`, logic in `app/guardrails/prechecks.py`.
- Refusal and clarification texts: `app/guardrails/templates.yaml`.
- Classifier: `app/guardrails/classifier.py`; pipeline composition in `app/guardrails/pipeline.py`.
- Thresholds, timeouts, model, and enable flag: `GUARDRAIL_*` and `ANTHROPIC_CLASSIFIER_MODEL` in `app/config.py`.
- Tests: `tests/unit/guardrails/` and `tests/e2e/test_guardrails_api.py`. Add or adjust items in `evals/questions.yaml` when behaviour changes (never delete items; retire with `status: retired`).

## Change the system prompt

1. Edit `app/agent/prompts/system.md` for role, grounding rules, and answer format.
2. Edit `app/agent/prompts/templates.yaml` for timeout, iteration-cap, and error messages.
3. If the prompt needs new runtime values, extend `build_system_prompt` in `app/agent/prompt.py`.
4. Run `tests/unit/agent/test_prompt.py`, `tests/component/agent/test_loop.py`, and the eval set; record prompt-engineering decisions in [decision_log.md](decision_log.md).
