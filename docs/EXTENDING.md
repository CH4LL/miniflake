# Extending Miniflake

How to add capability without touching more than the layer concerned. Component boundaries are described in [ARCHITECTURE.md](../ARCHITECTURE.md). Each section is completed with concrete file paths when the corresponding stage lands (see [roadmap.md](roadmap.md)).

## Add a tool (completed in S2)

Outline:

1. Create `app/tools/<name>.py` with a pydantic input model, a result data model, an LLM-facing description string, and a `run(repository, input) -> ToolResult` function that returns `Success` or one of the explicit outcome types (`Ambiguous`, `NotFound`, `PeriodUnavailable`, `UnsupportedRequest`).
2. If the tool needs a query the repository does not offer, add a method to the `CensusRepository` protocol, a SQL template under `app/data/sql/`, and implementations in both the Snowflake and fake repositories; extend the contract test.
3. Register the tool in `default_registry` in `app/tools/registry.py`. The system prompt lists tools from the registry automatically.
4. Write component tests under `tests/component/tools/` for the success path and each outcome type, and add eval items to `evals/questions.yaml` covering the new question type.

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
