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

Outline:

1. Implement `LLMClient` in `app/llm/<provider>_client.py`, mapping the provider-neutral `Message`, `ContentBlock` and `ToolSchema` types to the provider API and back, with `LLMError(retryable)` for failures.
2. Select it via configuration in `app/main.py`.
3. Reuse the existing component tests with `FakeLLM`; add a unit test for request and response mapping with a stubbed transport.

## Swap the conversation store (completed in S4)

Outline:

1. Implement `ConversationStore` in `app/conversation/<backend>_store.py`.
2. Run the store unit tests against it (TTL, max turns, reset).
3. Select it via configuration.

## Adjust guardrails (completed in S5)

Outline: patterns and templates are YAML files under `app/guardrails/`; classifier thresholds and model are configuration values; grounding matcher rules live in `app/guardrails/grounding.py` with unit tests that must be extended for any new rule.

## Change the system prompt (completed in S3)

Outline: edit `app/agent/prompts/system.md`; run the component tests and the eval set; record prompt-engineering decisions in the decision log.
