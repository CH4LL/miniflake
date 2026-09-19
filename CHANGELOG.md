# Changelog

All notable changes to this project. One entry per completed stage or feature; newest first.

## Unreleased

### S0: Foundations and walking skeleton
- Python project skeleton with `uv`, pydantic-settings configuration, and `GET /api/health`.
- SafeGraph schema discovery script (`scripts/discover_schema.py`) generating `docs/data/dataset.md`.
- Dockerfile, GitHub Actions CI (ruff + pytest), and minimal Cloud Run deploy script.
- Live Snowflake connectivity verified; 2019 and 2020 ACS block-group wide tables discovered.

### Planning
- Architecture overview, stage roadmap (S0 to S9) with cut policy, per-stage specifications, ADR-001 to ADR-008, decision log, agent workflow, testing strategy, and the v1 golden question set in `evals/questions.yaml`.

### Dataset pivot
- Retargeted all documentation to the SafeGraph [US Open Census Data & Neighborhood Insights - Free Dataset](https://app.snowflake.com/marketplace/listing/GZSNZ2UNN0/safegraph-us-open-census-data-neighborhood-insights-free-dataset) as the sole Marketplace source (ADR-003 accepted).
- Adopted counts-only rollup policy: SUM for count fields from block groups to state/county/place/nation; median and rate fields at rolled-up geography declared unanswerable (ADR-004 amended).
- Revised S0/S1 specs for wide-table schema and metadata catalog; updated `evals/questions.yaml` to v2 with block-group median examples and unanswerable median/rate items at aggregate geography.
