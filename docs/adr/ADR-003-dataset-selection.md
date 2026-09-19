# ADR-003: Dataset selection

Status: proposed (2026-09-19). To be set to `accepted` at the end of S0 after schema inspection, or revised if inspection contradicts the assumptions below.

## Context

The requirements name the US Open Census dataset on the Snowflake Marketplace as the data source. Two free listings plausibly match:

- **SafeGraph: "US Open Census Data & Neighborhood Insights - Free Dataset."** Exact name match. Contents as documented publicly: American Community Survey 5-year estimates at census block group level only, wide tables with coded column names (one column per ACS variable), a metadata table mapping codes to descriptions, block-group geometry and city/county mappings.
- **Snowflake Public Data Products: Census Bureau source (formerly Cybersyn).** Long-format tables: `AMERICAN_COMMUNITY_SURVEY_TIMESERIES` (variable, geography, date, value), `AMERICAN_COMMUNITY_SURVEY_ATTRIBUTES` (variable catalog with series, measurement type and period, unit), `GEOGRAPHY_INDEX` (geographies with a `level` such as State, County, CBSA, Place, Tract, Block Group). Multiple ACS releases over time.

Both listings are free and take minutes to acquire.

## Options

1. **SafeGraph listing only.** Honours the literal name. State- or county-level questions require aggregating thousands of block groups; sums are valid for counts but not for medians, means or rates, which are the bulk of interesting questions (median income, poverty rate, median age). Coded column names make the variable catalog harder to expose to the LLM. Single ACS vintage limits trend questions.
2. **Snowflake Public Data census tables only.** Native geography levels match how people ask questions. The attributes table is a ready-made variable catalog. Multi-year coverage enables trends. Long format means one SQL template shape for every variable. Risk: the name does not literally match the requirements.
3. **Acquire both, inspect, default to option 2, document the interpretation.** Costs a few minutes in S0, records the literal listing as considered, and lets the `CensusRepository` protocol accommodate the SafeGraph tables later as a second implementation if a reviewer asks.

## Decision

Option 3. The application defaults to the Snowflake Public Data census tables at the Nation, State, County, CBSA and Place levels. The README states the interpretation: the requirement is read as "US Census data from the Snowflake Marketplace", the literal SafeGraph listing was acquired and inspected, and the long-format source was preferred because it answers the realistic question set without invalid aggregation. Block group and tract questions are declared out of scope with a clear message.

## Consequences

- SQL templates in S1 are written against the three long-format tables.
- The curated variable catalog is derived from the attributes table via a hand-maintained series allow-list.
- Adding the SafeGraph tables later is a second `CensusRepository` implementation, not a redesign.
- If S0 inspection shows the Public Data census tables are unavailable in the chosen region or listing, this ADR is revised to option 1 with an aggregation-safety rule (counts only) before S1 begins.
