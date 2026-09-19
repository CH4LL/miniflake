# ADR-003: Dataset selection

Status: accepted (2026-09-19)

## Context

The requirements call for the US Open Census dataset on the Snowflake Marketplace, accessed through a free trial account. The explicit listing is:

**[US Open Census Data & Neighborhood Insights - Free Dataset](https://app.snowflake.com/marketplace/listing/GZSNZ2UNN0/safegraph-us-open-census-data-neighborhood-insights-free-dataset)** (SafeGraph, listing `GZSNZ2UNN0`).

Public documentation describes the dataset as American Community Survey 5-year estimates at census block group level, stored in wide tables (one row per block group, ACS field codes as column names such as `B01003e1`), with metadata tables for field descriptions, FIPS-to-city/county mapping, and geographic statistics. Snowflake vintages include 2019 and 2020 ACS 5-year releases; exact table names are confirmed in S0 schema discovery.

## Rejected alternatives

- **Snowflake Public Data Products (Census Bureau / Cybersyn long-format tables).** Different Marketplace listing with native state/county geography levels and a long-format schema. Not the dataset named in the requirements; using it would require a loose reading of them.

## Decision

Use the SafeGraph listing only. The application reads ACS data at census block group grain and rolls up to higher geography levels under the counts-only policy defined in ADR-004.

**Native geography level:** `BlockGroup` (12-digit FIPS).

**Derived geography levels** (via FIPS prefix and metadata mapping, where available):

- `Nation`: sum all block groups.
- `State`: sum block groups sharing the state FIPS prefix.
- `County`: sum block groups sharing the county FIPS prefix; names from metadata.
- `Place`: sum block groups mapped to a place in the FIPS metadata table, if the mapping exists in the acquired share.
- `CBSA`: supported only if the metadata or discovery script confirms a block-group-to-CBSA mapping; otherwise declared unsupported.

**Variable catalog:** derived from the field-descriptions metadata table, with each field tagged by `aggregation_kind` (`count`, `median`, `rate`) for rollup decisions.

**Vintages:** ACS years present in the share (expected 2019 and 2020); trend questions apply only to count fields with multiple vintages.

If Marketplace acquisition of this listing fails, log a deviation in the decision log and halt S1 until resolved. Do not substitute a different listing.

## Consequences

- SQL templates in S1 target wide ACS tables and metadata tables, not long-format timeseries.
- State- and county-level population questions are answered by summing block groups; median, rate and percentage questions at those levels are declared unanswerable.
- Median and rate questions at block group level are answered by direct column read.
- Tract and street-level questions remain out of scope.
- S0 discovery script documents the actual Snowflake table and column names; assumptions in this ADR are revised only if discovery contradicts them.
