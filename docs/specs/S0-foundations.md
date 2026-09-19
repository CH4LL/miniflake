# S0: Foundations and walking skeleton

Status: see [roadmap.md](../roadmap.md). Estimate: 3 h.

## Goal

Remove every external unknown (Snowflake access, dataset shape, GCP deployment) and stand up a project skeleton that later stages fill in. Nothing product-facing is built here; the value is that S1 to S7 can proceed without surprises.

## Scope

1. Snowflake trial account, both candidate listings acquired, dedicated service user with key-pair authentication and a read-only role.
2. Discovery script that inspects both listings and writes [docs/data/dataset.md](../data/dataset.md).
3. Dataset decision confirmed: ADR-003 status set to `accepted` with the inspection findings.
4. Python project skeleton: `pyproject.toml` managed by `uv`, `app/config.py`, `app/main.py` with `GET /api/health`, ruff and pytest configured.
5. `Dockerfile` and `.dockerignore`.
6. GitHub Actions workflow running lint and tests on push.
7. Hello-world deployment of the health endpoint to Cloud Run.
8. Documentation skeletons exist (created together with this spec).

## Out of scope

Any data query beyond schema inspection, any LLM call, any UI.

## Manual steps (human, before the coding part)

These require a browser and account credentials and cannot be done by an agent.

1. Sign up for a Snowflake trial (Enterprise edition, AWS or GCP region close to the Cloud Run region). Record the account identifier.
2. In Marketplace, acquire both free listings: "Snowflake Public Data (Free)" from Snowflake Public Data Products, and "US Open Census Data & Neighborhood Insights - Free Dataset" from SafeGraph. Record the database names they mount under.
3. Create an XS warehouse dedicated to the app with a short auto-suspend.
4. Create a read-only role granted `USAGE` on the warehouse and `IMPORTED PRIVILEGES` on both mounted databases.
5. Generate an RSA key pair locally; create a user with `TYPE = SERVICE`, assign the public key and the role. Service users are exempt from the MFA enforcement applied to password logins.
6. Store account, user, role, warehouse, database names and the private key path in a local `.env` (never committed; `.env.example` documents the keys).
7. Confirm a GCP project id with billing enabled, Cloud Run, Artifact Registry and Secret Manager APIs enabled, and `gcloud` authenticated locally.

## Behaviour

### Configuration

`app/config.py` defines a pydantic-settings `Settings` model. Every adjustable value used by any stage is declared here as it is introduced. For S0: application name, environment name, log level, Snowflake connection fields (account, user, role, warehouse, database, schema, private key path or PEM content), and the health endpoint version string. Missing required values fail fast at startup with a readable message.

### Health endpoint

`GET /api/health` returns HTTP 200 with a JSON body containing service name, version and environment. It does not touch Snowflake or the LLM; a separate readiness check is introduced in S7 if needed.

### Discovery script

`scripts/discover_schema.py` connects with the service user and, for each mounted database, lists schemas, tables, row counts, and columns. For the Snowflake Public Data census tables it additionally reports: distinct `level` values in `GEOGRAPHY_INDEX` with counts, distinct `measurement_period` and `measurement_type` values in the attributes table, the min and max `date` in the timeseries table, and the number of distinct variables. It renders these into `docs/data/dataset.md` from a template so the document can be regenerated.

## Acceptance criteria

- Given a fully populated `.env`, when the application starts, then `Settings` loads without error and `GET /api/health` returns 200 with the expected body.
- Given a `.env` missing a required Snowflake field, when the application starts, then it exits with an error naming the missing field.
- Given valid credentials, when `scripts/discover_schema.py` runs, then `docs/data/dataset.md` is written and contains the sections listed above for both databases.
- Given the repository on `main`, when CI runs, then ruff and pytest both pass.
- Given the built container image, when it runs locally with the health port exposed, then `GET /api/health` returns 200.
- Given the image deployed to Cloud Run, when the public URL is requested at `/api/health`, then it returns 200.

## Tests to write first

1. `tests/unit/test_config.py`: settings load from environment; missing required field raises with the field name; defaults apply for optional fields.
2. `tests/e2e/test_health.py`: `TestClient` request to `/api/health` returns 200 and the documented body shape.
3. `tests/unit/test_discover_render.py`: the dataset document renderer produces the expected sections from a fixed inspection result (the Snowflake call itself is not unit-tested).
4. `tests/live/test_snowflake_connection.py` (skipped unless `RUN_LIVE_TESTS=1`): connection opens, `SELECT CURRENT_ROLE()` returns the read-only role, both databases are visible.

## Files

- `pyproject.toml`, `uv.lock`, `.python-version`, `ruff.toml` (or `[tool.ruff]` section), `.env.example`, `.gitignore`
- `app/__init__.py`, `app/config.py`, `app/main.py`, `app/api/__init__.py`, `app/api/health.py`
- `scripts/discover_schema.py`, `scripts/templates/dataset.md.j2`
- `Dockerfile`, `.dockerignore`
- `.github/workflows/ci.yml`
- `scripts/deploy.sh` (minimal version, extended in S7)
- `tests/conftest.py`, tests listed above

## Documentation updates at stage end

- `docs/data/dataset.md` generated.
- ADR-003 status updated with findings; if the SafeGraph listing turns out to be preferable, revise ADR-003 and the roadmap before starting S1.
- `CHANGELOG.md` entry.
- `docs/roadmap.md` status for S0.
- `docs/decision_log.md` entry for any deviation encountered (region choice, listing availability, Cloud Run issues).
