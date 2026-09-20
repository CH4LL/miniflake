# Reflection

Filled incrementally from [decision_log.md](decision_log.md), the stage specs, and the S8 evaluation report; finalised in S9. Each section should cite concrete artefacts (file paths, ADR numbers, decision log entries, eval item ids) rather than generalities.

## Development process and key architectural decisions

Placeholder. To cover:

- How the 24 hours were split across stages, with actual versus estimated hours from the roadmap.
- The decision to write the roadmap, specs and eval set before code, and what it cost and saved.
- Summary of each ADR with a one-paragraph justification: stack (ADR-001), LLM provider including the Cursor SDK dead end (ADR-002), SafeGraph listing as sole data source with counts-only rollup policy (ADR-003), typed tools over text-to-SQL with repository-side SUM rollups (ADR-004), conversation state (ADR-005), hosting and demo auth (ADR-006), layered guardrails (ADR-007), testing (ADR-008).
- Deviations from the plan, taken from decision log entries of type `deviation`.

## What I would improve or do differently with more time

Placeholder. Candidates already known at planning time:

- Constrained SQL tool for long-tail questions (roadmap optional extensions).
- Persistent conversation store and horizontal scaling.
- Streaming responses to improve perceived latency.
- Result caching for catalog lookups.
- Broader variable catalog curation and per-topic prompt guidance.
- Statistically valid median/rate rollups at state and county level (would require a different data product or published aggregate tables).

Discovered during S8:

- Terminal pseudo-tools (`declare_unanswerable`, `ask_clarification`) so the model states its outcome explicitly instead of the composer inferring it from tool traces and classifier intent. Dropped in S8 because the behaviour change could not be verified offline (decision log 2026-09-20).
- Report classifier token usage from `/api/chat` so the eval cost line covers both models instead of agent tokens only.
- Batch `available_vintages` for `compare`, the last per-geography lookup in the tools.
- Learned or LLM-generated variable aliases instead of the hand-curated list in `fixtures/variable_catalog_spec.yaml`.
- A second live run after the final report to measure variance; the plan reserves a single run.

Add any stage marked `cut` in the roadmap.

## Edge cases and failure modes identified but not fully addressed

Observed in the S8 baseline report ([evals/reports/20260919T133835Z.md](../evals/reports/20260919T133835Z.md)), in local `logs/app.jsonl`, and while writing the offline tests. Items are cited by golden-set id.

- **Outcome labels inferred from prose.** Six of the eleven strict-gate failures (L05, R02, MV01, MV02, UL01, UL02) were correct answers labelled `answer` because the composer only recognised a fixed list of "not supported" phrases, while M01 and M02 needed the opposite. The composer now labels a no-tool turn `unanswerable` unless the classifier marked it `capability` (decision log 2026-09-20). Remaining gap: a no-tool clarifying question written by the model ("which Washington?") is labelled `unanswerable`, not `clarify`; the classifier is expected to catch missing geography earlier, and the golden set treats the agent-written clarify as a pass only when a tool returned `ambiguous`.
- **Variable-search thrash.** L07 and AV02 spent six `find_variable` calls on phrases such as "population below poverty line" that no whole-phrase substring matched. Search is now token-based with catalog aliases and the loop caps search calls per turn (`AGENT_MAX_SEARCH_CALLS`); the golden set pins the count with `max_tool_calls`. Remaining gap: aliases are hand-curated per series; a measure phrased outside them still costs the full budget before the model gives up.
- **Latency tails from N+1 lookups.** F04 and AT02 pushed p95 to 49 s: one Snowflake session per query (fixed by `is_closed()` reuse) and one `get_geography` per ranked row (fixed by batch `get_geographies`). Remaining gap: `compare` still calls `available_vintages` per geography, and a cold warehouse adds seconds the harness attributes to the agent.
- **Classifier misroutes.** MV03 ("crime rate in Chicago") was refused as off-topic; UP01–UP03 and R03/AG03 were clarified for omitted vintage. Prompt changes moved these; the classifier remains a single cheap call with two turns of context and still fails open on error, so a burst of errors would let off-topic questions reach the agent.
- **Place substitution (L06).** Asked about a place with no place-level data, the model may pick a nearby county and answer. The prompt forbids silent level switching; the eval judges from the text. No deterministic guard exists because the substitution happens inside the model's reasoning.
- **Ambiguous place names (AG01, AG03).** "Orange County" exists in eight states in the fixtures alone. `find_geography` returns `ambiguous` with candidates, but the model sometimes chooses one when the user gave a hint that does not match a state name. Nicknames ("the Bay Area") and abbreviations beyond state codes are not resolved.
- **Measurement period confusion.** Users asking for "2020 population" receive the 2020 ACS 5-year estimate (2016–2020), which differs from the 2020 decennial count. The tool descriptions carry the note; the answer text does not always repeat it.
- **Budget exhaustion mid-loop.** When the LLM or Snowflake is slow, the loop stops dispatching tools below the per-call minimum and the composer returns the timeout template with the attempted tool list. The user gets an honest error, not a partial answer.
- **Injection coverage.** The pattern list covers the golden-set injection variants (I01–I03); paraphrased instructions in another language or split across turns are not matched and rely on the classifier and the tool-only data path.
- **Value checks on derived figures.** L07 states a share computed from two counts; the harness cannot verify it against a single reference value, so the item has no value check.

## Testing approach and what I would add

Placeholder. Summarise [testing-strategy.md](testing-strategy.md) and add:

- Coverage by layer at the end of the build.
- Eval pass rates by category and latency percentiles from the S8 report.
- What is missing: load testing, soak, broader red-teaming, exhaustive SQL correctness across the catalog, visual regression.

## How AI coding tools were used

Placeholder. Describe the planning-first workflow in [agent-workflow.md](agent-workflow.md), how specs and the eval set constrained generated code, where generated output was rejected or corrected, and how the decision log captured dead ends encountered with tool assistance.
