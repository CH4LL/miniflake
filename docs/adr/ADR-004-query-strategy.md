# ADR-004: Query strategy

Status: accepted (2026-09-19)

## Context

The agent must answer from data with visible provenance, never hallucinate, recognise unanswerable and ambiguous questions, and respond within a fixed budget. The dataset is a long-format fact table with a variable catalog and a geography index; the realistic question set is lookups, comparisons, rankings and trends over named geographies and measures.

## Options

1. **Free-form text-to-SQL.** The LLM writes SQL against the schema. Maximum expressiveness; but provenance is "whatever SQL the model wrote", errors surface as SQL failures or silently wrong joins, ambiguity (which "Springfield", which "income" variable) is resolved implicitly inside the model, testing requires an LLM in the loop, and the safety story rests on SQL validation. Under a 24-hour budget the failure modes are hard to enumerate and the results hard to defend.
2. **Typed semantic tools over parametrized SQL templates.** The LLM selects a tool and fills typed parameters; the tool resolves names against the catalog, runs a fixed template, and returns typed results including explicit `Ambiguous`, `NotFound` and `PeriodUnavailable` outcomes. Provenance is exact (variable, geography, date, SQL, parameters). The whole path is testable with a fake repository and a scripted LLM. Expressiveness is bounded by the tool set.
3. **Pre-aggregated cache or exported tables queried locally.** Fast and cheap; but duplicates data outside Snowflake, needs a refresh story, and weakens the "grounded in the Marketplace dataset" claim.
4. **Hybrid: typed tools plus a constrained SQL tool with an allow-list validator.** Extends option 2 for long-tail questions at the cost of a validator that must be right.

## Decision

Option 2 for the core. Six tools: `find_geography`, `find_variable`, `get_value`, `rank_geographies`, `get_trend`, `compare`. Aggregation across geographies is never performed by the application; questions that would need it are declared unanswerable with an explanation. Option 4 is recorded as an optional extension after the roadmap completes.

## Consequences

- The LLM never writes SQL; the read-only role and the execute guard are defence in depth rather than the primary safety mechanism.
- Every "cannot answer" case is a typed value, which the composer and guardrails can act on deterministically.
- Some legitimate questions fall outside the tool set; the agent says so and suggests a supported reformulation. This is a deliberate tradeoff recorded for the reflection.
- Adding a question type means adding a tool, which is the documented extension path.
