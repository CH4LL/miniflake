# S7: Deployment

Status: see [roadmap.md](../roadmap.md). Estimate: 1.5 h. Depends on S6.

## Goal

The full application runs on a public HTTPS URL on Google Cloud Run with secrets managed outside the image, observable enough to diagnose a failed evaluation request from logs alone.

## Scope

1. Hardened `Dockerfile`: multi-stage build with `uv`, non-root user, pinned base image, only runtime dependencies in the final layer.
2. Secrets in Secret Manager: Snowflake private key, Anthropic API key, cookie signing secret, demo passphrase. Mounted as environment variables in the Cloud Run service.
3. Cloud Run service configuration expressed in `deploy/service.yaml` (or `gcloud` flags in `scripts/deploy.sh`): min and max instances both one during the evaluation window, request timeout above the response budget, concurrency limit, CPU always allocated so background warm-up is possible, region matching the Snowflake region where possible.
4. Structured JSON logging with request id, conversation id, latency, outcome, tool call names and durations, LLM token usage, and Snowflake query duration. No message content beyond a truncated preview at info level; full content only at debug.
5. Startup warm-up: open the Snowflake connection and run a trivial query so the first user request does not pay warehouse resume time.
6. `scripts/deploy.sh`: build, push to Artifact Registry, deploy, run the smoke test.
7. `scripts/smoke_deployed.py`: logs in, sends a golden lookup question, asserts outcome `answer` and latency within budget.
8. README section with the public URL placeholder, login instructions and known operational limits.

## Out of scope

Custom domains, autoscaling tuning, CI-triggered deployment, persistent storage.

## Acceptance criteria

- Given the image, when it runs as a non-root user with only the documented environment variables, then the application starts and serves `/api/health`.
- Given the deployed service, when the smoke script runs, then it logs in, receives an `answer`, and completes within the budget.
- Given a request to the deployed service, then the Cloud Logging entry for it contains request id, outcome, latency and tool call names as structured fields.
- Given the Snowflake warehouse is suspended, when the first request arrives after deployment, then warm-up has already resumed it and the request completes within budget.
- Given a secret is missing from the service configuration, when the container starts, then it exits with a readable error naming the setting (from S0 behaviour).

## Tests to write first

1. `tests/unit/test_logging.py`: JSON formatter output fields; message content redaction at info level.
2. `tests/unit/test_warmup.py`: warm-up calls the repository once and tolerates failure without crashing startup.
3. `scripts/smoke_deployed.py` doubles as the deployed acceptance test; it is not part of the pytest suite.

## Files

- `Dockerfile`, `.dockerignore`, `deploy/service.yaml` or flags in `scripts/deploy.sh`, `scripts/smoke_deployed.py`
- `app/logging.py`, `app/warmup.py`, `app/main.py` lifespan wiring
- `README.md` access section

## Documentation updates at stage end

`README.md` (access instructions), `ARCHITECTURE.md` (runtime topology as deployed), `USER-GUIDE.md` (demo URL and login), `CHANGELOG.md`, `docs/roadmap.md`, `docs/decision_log.md` for any GCP-specific workaround.
