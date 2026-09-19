# S10: Public data supplement

Status: see [roadmap.md](../roadmap.md). Estimate: 2.0 h. Depends on S9. Optional; only if time remains after the core roadmap.

## Goal

Answer geography-level questions the SafeGraph block-group share cannot serve by adding a second `CensusRepository` implementation backed by `SNOWFLAKE_PUBLIC_DATA_FREE` (Census Bureau / Cybersyn long-format tables with native state, county, place and CBSA levels).

## Motivation

S0 discovery confirmed the SafeGraph share has no place-to-block-group mapping and no CBSA column in `{YEAR}_METADATA_CBG_FIPS_CODES`. S1 therefore supports only `BlockGroup`, `Nation`, `State`, and `County`. Several golden eval items and natural user questions require city (place) or metro (CBSA) geography; those are deferred here rather than deleted.

## Questions deferred from the golden set

| Eval id | Question | SafeGraph outcome | Public-data target |
| :--- | :--- | :--- | :--- |
| L06 | How many people live in the city of Denver? | unanswerable (no Place level) | Place population via native place table |
| AG01 | What is the population of Springfield? | unanswerable (place ambiguity) | Place search with state disambiguation |
| L05 | Median gross rent in the Seattle metro area? | unanswerable (no CBSA) | CBSA median if available in public data |
| R03 | Top 3 metro areas by median home value? | unanswerable (no CBSA) | CBSA ranking if available |

Other items that mention place or metro in notes (`UL02`, `M01`) remain answerable or descriptive at state/county level until S10 extends capability.

## Scope

1. Inspect `SNOWFLAKE_PUBLIC_DATA_FREE` schema for ACS tables with native Place and CBSA geography.
2. Implement `PublicDataCensusRepository` (or a composite router) behind the existing `CensusRepository` protocol.
3. Geography search and observation queries for Place and CBSA only; SafeGraph remains the source for block-group reads and count rollups at state/county.
4. Configuration to select primary and supplement sources.
5. Contract tests for the supplement repository; update affected eval items to `expected: answer` when S10 is done.

## Out of scope

Replacing SafeGraph as the primary source; median/rate rollups at aggregate geography (still invalid statistically); tract or street level.

## Acceptance criteria

- Given `find_geography("Denver", level=Place)`, when the supplement repository runs, then a Colorado place match is returned.
- Given population for a named place, when `get_observations` runs via the supplement, then a direct value is returned without block-group SUM.
- Given a question answerable only from SafeGraph (block-group median), when routed, then SafeGraph is used.
- Given eval item L06 against the deployed stack after S10, then outcome is `answer` with provenance at Place level.

## Tests to write first

1. `tests/unit/data/test_public_data_router.py`: routing logic by geography level.
2. `tests/component/data/test_public_data_repository.py`: place lookup and observation against fixtures.
3. `tests/live/test_public_data_repository.py`: opt-in smoke against `SNOWFLAKE_PUBLIC_DATA_FREE`.

## Files

- `app/data/public_data_repository.py`, `app/data/repository_router.py`
- `fixtures/public_data_*.json` (snapshot from public database)
- tests listed above

## Documentation updates at stage end

- `evals/questions.yaml`: restore L06, AG01, L05, R03 to `expected: answer` where public data supports them.
- `ARCHITECTURE.md`: dual-source topology.
- `CHANGELOG.md`, `docs/roadmap.md`, `docs/decision_log.md`.
