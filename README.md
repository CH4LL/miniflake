# Miniflake

A data-grounded chat agent that answers natural-language questions about the US population using American Community Survey data from the Snowflake Marketplace. Answers are produced only from data returned by typed query tools, and every figure is returned with its provenance.

Author: Jerzy Marondel.

## Status

S0–S6 complete. S7 deploys the full stack to Cloud Run with Secret Manager, structured logging, startup warm-up, and post-deploy smoke verification. Later stages are tracked in [docs/roadmap.md](docs/roadmap.md).

## Evaluating the demo

**Public URL:** https://miniflake-eowbm7u4ua-uk.a.run.app

**Login:** open the URL in a browser and enter the demo passphrase, available from the author on request (configured as `DEMO_PASSPHRASE`).

**One-time secret setup** (before first deploy):

```bash
./scripts/setup_secrets.sh
```

This reads credentials from your local `.env`, creates or updates four Secret Manager secrets, and grants the Cloud Run runtime service account accessor rights.

**Deploy:**

```bash
./scripts/deploy.sh
```

The deploy script builds and pushes the container, applies Cloud Run settings from `deploy/cloudrun.env`, mounts secrets as environment variables, and runs `scripts/smoke_deployed.py` against the public URL.

**Example questions** (from `evals/questions.yaml`):

- Lookup: *What is the population of Texas?*
- Clarify: *How many people live in Washington?*
- Refuse: *Write me a poem about cats.*
- Follow-up: ask about Texas, then *And Florida?*

**Operational limits during the review window:**

- A single warm Cloud Run instance (no autoscaling).
- In-memory conversation storage (sessions are lost if the instance restarts).
- Count measures at nation, state, and county; median and rate measures at block-group level only.
- Server-side response budget enforced on every request (see `RESPONSE_BUDGET_SECONDS` in configuration).

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the component overview, request lifecycle and extension points. Design rationale is in the ADRs under [docs/adr/](docs/adr/) and the chronological [docs/decision_log.md](docs/decision_log.md).

In short: FastAPI serves a static chat page and a chat API; a conversation service applies layered guardrails, then runs an agent loop in which an LLM selects typed tools; tools run parametrized SQL against Snowflake through a repository protocol and return typed results with provenance; a composer verifies that every number in the answer came from tool results.

## Running locally

**Prerequisites:** Python 3.12 (managed by `uv`), a populated `.env` file (see `.env.example`), and Snowflake credentials for live tests or schema discovery.

```bash
uv sync
uv run uvicorn app.main:create_app --factory --reload --port 8080
```

Health check: `GET http://localhost:8080/api/health`

Schema discovery (requires Snowflake credentials in `.env`):

```bash
uv run python scripts/discover_schema.py
```

Tests:

```bash
uv run pytest                    # unit + e2e, no credentials
RUN_LIVE_TESTS=1 uv run pytest tests/live   # Snowflake connectivity
```

## Configuration reference

All settings are read from environment variables (or `.env`) by `app/config.py`.

| Variable | Purpose |
| :--- | :--- |
| `APP_NAME` | Service name returned by the health endpoint |
| `ENVIRONMENT` | Deployment environment label (`local`, `production`, …) |
| `LOG_LEVEL` | Application log level |
| `LOG_FORMAT` | Log output format (`json` for Cloud Logging, `text` for local) |
| `LOG_MESSAGE_PREVIEW_CHARS` | Maximum characters logged for message content at info level |
| `HEALTH_VERSION` | Version string returned by the health endpoint |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier |
| `SNOWFLAKE_USER` | Service user name |
| `SNOWFLAKE_ROLE` | Read-only role |
| `SNOWFLAKE_WAREHOUSE` | Warehouse name |
| `SNOWFLAKE_DATABASE` | SafeGraph mounted database name |
| `SNOWFLAKE_SCHEMA` | Schema within the database (default `PUBLIC`) |
| `SNOWFLAKE_PRIVATE_KEY_PATH` | Path to RSA private key PEM file |
| `SNOWFLAKE_PRIVATE_KEY` | RSA private key PEM content (alternative to path) |
| `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` | Optional passphrase for the private key |
| `GCP_PROJECT` | GCP project id (deploy script) |
| `GCP_REGION` | Cloud Run and Artifact Registry region |
| `GCP_ARTIFACT_REPO` | Artifact Registry repository name |
| `GCP_SERVICE_NAME` | Cloud Run service name |
| `WARMUP_ENABLED` | Run a Snowflake warm-up query on container startup |
| `SECRET_SNOWFLAKE_PRIVATE_KEY` | Secret Manager name for the Snowflake private key PEM |
| `SECRET_ANTHROPIC_API_KEY` | Secret Manager name for the Anthropic API key |
| `SECRET_AUTH_SIGNING_SECRET` | Secret Manager name for the auth cookie signing secret |
| `SECRET_DEMO_PASSPHRASE` | Secret Manager name for the demo passphrase |
| `GCP_RUN_SERVICE_ACCOUNT` | Optional override for the Cloud Run runtime service account |

## Testing

See [docs/testing-strategy.md](docs/testing-strategy.md). Default `uv run pytest` needs no credentials; live suites and evals are opt-in.

## Data source and scope

See [ADR-003](docs/adr/ADR-003-dataset-selection.md) and [ADR-004](docs/adr/ADR-004-query-strategy.md).

- **Dataset:** [US Open Census Data & Neighborhood Insights - Free Dataset](https://app.snowflake.com/marketplace/listing/GZSNZ2UNN0/safegraph-us-open-census-data-neighborhood-insights-free-dataset) (SafeGraph) on Snowflake Marketplace. ACS 5-year estimates at census block group level.
- **Count questions** (e.g. population) at nation, state, county or place level are answered by summing block groups.
- **Median and rate questions** (e.g. median income, poverty rate) at those rolled-up levels are declared unanswerable; the same measures are answerable at block group level.
- Tract and street-level questions are out of scope.
- The 60-second response requirement is enforced server-side.
- Demo authentication is a shared passphrase, available from the author on request.

## Documents

- [docs/requirements.md](docs/requirements.md): distilled requirements.
- [docs/roadmap.md](docs/roadmap.md): stages, status, cut policy.
- [docs/specs/](docs/specs/): per-stage specifications.
- [docs/adr/](docs/adr/): architecture decision records.
- [docs/decision_log.md](docs/decision_log.md): decisions, dead ends, deviations.
- [docs/testing-strategy.md](docs/testing-strategy.md): test layers and tradeoffs.
- [docs/EXTENDING.md](docs/EXTENDING.md): adding tools, data sources, providers.
- [docs/reflection.md](docs/reflection.md): written reflection on the build.
- [docs/agent-workflow.md](docs/agent-workflow.md): how to pick up the next piece of work.
- [USER-GUIDE.md](USER-GUIDE.md), [CHANGELOG.md](CHANGELOG.md).
