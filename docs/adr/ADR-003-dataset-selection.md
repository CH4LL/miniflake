# ADR-003: Dataset selection

Status: accepted, amended after S0 discovery

## Context

The requirements call for the US Open Census dataset on the Snowflake Marketplace, accessed through a free trial account. The explicit listing is:

**[US Open Census Data & Neighborhood Insights - Free Dataset](https://app.snowflake.com/marketplace/listing/GZSNZ2UNN0/safegraph-us-open-census-data-neighborhood-insights-free-dataset)** (SafeGraph, listing `GZSNZ2UNN0`).

The dataset is American Community Survey 5-year estimates at census block group level, stored in wide tables (one row per block group, ACS field codes as column names such as `B01003e1`), with metadata tables for field descriptions, FIPS-to-state/county mapping, and geographic statistics. S0 discovery confirmed two vintages (2019 and 2020 ACS 5-year releases), the `{YEAR}_CBG_B{nn}` table naming, and the absence of any place or CBSA mapping in the metadata.

## Options

1. **Snowflake Public Data Products (Census Bureau / Cybersyn long-format tables).** Different Marketplace listing with native state, county, CBSA and place levels, a ready-made variable catalog and multi-year coverage. This was the first written default: block-group-only data forces aggregation that is invalid for medians and rates, and the long format is easier to query. Rejected the same day: it is not the dataset named in the requirements, and using it would require a loose reading of them.
2. **SafeGraph listing only.** The named dataset. Costs: rollups from block groups must be done by the application and are valid only for count fields; place and CBSA levels are unavailable.
3. **Both, SafeGraph as primary with the public-data listing as a supplement for place and CBSA.** Kept as an optional stage (S10) and later cut for time; recorded in the decision log.

## Decision

Option 2. The application reads ACS data at census block group grain and rolls up to higher geography levels under the counts-only policy defined in ADR-004.

**Native geography level:** `BlockGroup` (12-digit FIPS).

**Derived geography levels** (via FIPS prefix and metadata mapping, where available):

- `Nation`: sum all block groups.
- `State`: sum block groups sharing the state FIPS prefix.
- `County`: sum block groups sharing the county FIPS prefix; names from metadata.
- `Place`, `CBSA`: not supported. The share has no place or CBSA mapping in its metadata, and the optional supplement (option 3, stage S10) was cut.

**Variable catalog:** derived from the field-descriptions metadata table filtered to a curated list of series, each tagged by `aggregation_kind` (`count`, `median`, `rate`) for rollup decisions. The curated list is a fixture and is not verified against the metadata at build time; the S8 live run found that several listed series (poverty, housing, health insurance, commuting) have no estimate rows in the share.

**Vintages:** the ACS years present in the share; trend questions apply only to count fields with multiple vintages.

## Consequences

- SQL templates target wide ACS tables and metadata tables, not long-format timeseries.
- State- and county-level population questions are answered by summing block groups; median, rate and percentage questions at those levels are declared unanswerable.
- Median and rate questions at block group level are answered by direct column read.
- City and metro questions are unanswerable; the agent explains the supported levels. Tract and street-level questions remain out of scope.
- The actual table and column names are documented in [docs/data/dataset.md](../data/dataset.md) from the discovery script.
