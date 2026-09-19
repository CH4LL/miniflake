# Reflection

Filled incrementally from [decision_log.md](decision_log.md), the stage specs, and the S8 evaluation report; finalised in S9. Each section should cite concrete artefacts (file paths, ADR numbers, decision log entries, eval item ids) rather than generalities.

## Development process and key architectural decisions

Placeholder. To cover:

- How the 24 hours were split across stages, with actual versus estimated hours from the roadmap.
- The decision to write the roadmap, specs and eval set before code, and what it cost and saved.
- Summary of each ADR with a one-paragraph justification: stack (ADR-001), LLM provider including the Cursor SDK dead end (ADR-002), dataset interpretation (ADR-003), typed tools over text-to-SQL (ADR-004), conversation state (ADR-005), hosting and demo auth (ADR-006), layered guardrails (ADR-007), testing (ADR-008).
- Deviations from the plan, taken from decision log entries of type `deviation`.

## What I would improve or do differently with more time

Placeholder. Candidates already known at planning time:

- Constrained SQL tool for long-tail questions (roadmap optional extensions).
- Persistent conversation store and horizontal scaling.
- Streaming responses to improve perceived latency.
- Result caching for catalog lookups.
- Broader variable catalog curation and per-topic prompt guidance.
- Second `CensusRepository` implementation over the SafeGraph block-group tables, for sub-county questions with count-only aggregation.

Add items discovered during implementation and any stage marked `cut` in the roadmap.

## Edge cases and failure modes identified but not fully addressed

Placeholder. Populate from:

- Eval items that failed or passed weakly in the S8 report, by id.
- Grounding-check false negatives observed (legitimate derived figures rejected).
- Geography resolution limits (names shared across levels, abbreviations, nicknames).
- Measurement period confusion (1-year versus 5-year estimates) in user questions.
- Behaviour when Snowflake or the LLM is slow enough to exhaust the budget mid-loop.
- Injection variants not covered by the pattern list.

## Testing approach and what I would add

Placeholder. Summarise [testing-strategy.md](testing-strategy.md) and add:

- Coverage by layer at the end of the build.
- Eval pass rates by category and latency percentiles from the S8 report.
- What is missing: load testing, soak, broader red-teaming, exhaustive SQL correctness across the catalog, visual regression.

## How AI coding tools were used

Placeholder. Describe the planning-first workflow in [agent-workflow.md](agent-workflow.md), how specs and the eval set constrained generated code, where generated output was rejected or corrected, and how the decision log captured dead ends encountered with tool assistance.
