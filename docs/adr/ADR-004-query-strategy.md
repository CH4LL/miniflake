# ADR-004: Query strategy

Status: accepted, amended for the SafeGraph block-group schema and counts-only rollups

## Context

The agent must answer from data with visible provenance, never hallucinate, recognise unanswerable and ambiguous questions, and respond within a fixed budget. The dataset is SafeGraph's wide block-group tables plus metadata (ADR-003). The realistic question set is lookups, comparisons, rankings and trends over named geographies and measures, with geography rollups performed inside the repository for count fields only.

## Options

1. **Free-form text-to-SQL.** The LLM writes SQL against the schema. Maximum expressiveness; but provenance is "whatever SQL the model wrote", errors surface as SQL failures or silently wrong joins, ambiguity (which "Springfield", which "income" variable) is resolved implicitly inside the model, testing requires an LLM in the loop, and the safety story rests on SQL validation. Under a 24-hour budget the failure modes are hard to enumerate and the results hard to defend.
2. **Typed semantic tools over parametrized SQL templates.** The LLM selects a tool and fills typed parameters; the tool resolves names against the catalog, runs a fixed template, and returns typed results including explicit `Ambiguous`, `NotFound`, `PeriodUnavailable` and `UnsupportedRequest` outcomes. Provenance is exact (field, geography, vintage, SQL, parameters, aggregation method). The whole path is testable with a fake repository and a scripted LLM. Expressiveness is bounded by the tool set.
3. **Pre-aggregated cache or exported tables queried locally.** Fast and cheap; but duplicates data outside Snowflake, needs a refresh story, and weakens the "grounded in the Marketplace dataset" claim.
4. **Hybrid: typed tools plus a constrained SQL tool with an allow-list validator.** Extends option 2 for long-tail questions at the cost of a validator that must be right.

## Decision

Option 2 for the core. Six tools: `find_geography`, `find_variable`, `get_value`, `rank_geographies`, `get_trend`, `compare`.

**Aggregation inside the repository** (not left to the LLM):

| `aggregation_kind` | Block group | County / State / Nation (rolled up) |
| :--- | :--- | :--- |
| `count` | Direct column read | `SUM` across constituent block groups; provenance records `aggregation_method: sum` |
| `median`, `rate` | Direct column read | `UnsupportedRequest`: medians and rates cannot be validly derived from block-group values at aggregate geography |

Ranking and comparison tools apply the same rule: only count fields at rolled-up geography levels; median/rate fields at those levels return `UnsupportedRequest`.

Option 4 is recorded as an optional extension after the roadmap completes.

Name resolution (`find_geography`, `find_variable`) is a catalog search, not an LLM guess: geography names are matched against the FIPS metadata and variable phrases are matched token-wise against field titles plus curated aliases in `fixtures/variable_catalog_spec.yaml`. Both return `Ambiguous` with candidates rather than picking one. Per-turn search calls are capped (ADR-010).

## Consequences

- The LLM never writes SQL; the read-only role and the execute guard are defence in depth rather than the primary safety mechanism.
- Every "cannot answer" case is a typed value, which the composer can act on deterministically (ADR-011).
- Many natural-language questions about median income or poverty rates at state or county level are honestly unanswerable from this dataset; the agent explains why and offers a block-group reformulation or a count-based alternative where one exists.
- Some legitimate questions fall outside the tool set; the agent says so and suggests a supported reformulation. This is a deliberate tradeoff recorded for the reflection.
- Adding a question type means adding a tool, which is the documented extension path.
