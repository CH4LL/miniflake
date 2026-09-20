# Configuration reference

All application settings are read from environment variables (or `.env`) by `app/config.py`. This page lists names and purposes only; values live in `.env` (see [.env.example](../.env.example)) and in Secret Manager for the deployed service, never in documentation. Deploy-script variables are listed at the end.

## Application

| Variable | Purpose |
| :--- | :--- |
| `APP_NAME` | Service name returned by the health endpoint |
| `ENVIRONMENT` | Deployment environment label |
| `LOG_LEVEL` | Application log level |
| `LOG_FORMAT` | Log stream format (`json` for Cloud Logging, `text` for local stderr) |
| `LOG_FILE` | JSON lines file path; empty disables. Unset in the local environment writes under `logs/` |
| `LOG_MESSAGE_PREVIEW_CHARS` | Maximum characters logged for message content at info level |
| `HEALTH_VERSION` | Version string returned by the health endpoint |

## Snowflake

| Variable | Purpose |
| :--- | :--- |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier |
| `SNOWFLAKE_USER` | Service user name |
| `SNOWFLAKE_ROLE` | Read-only role |
| `SNOWFLAKE_WAREHOUSE` | Warehouse name |
| `SNOWFLAKE_DATABASE` | SafeGraph mounted database name |
| `SNOWFLAKE_SCHEMA` | Schema within the database |
| `SNOWFLAKE_PRIVATE_KEY_PATH` | Path to RSA private key PEM file |
| `SNOWFLAKE_PRIVATE_KEY` | RSA private key PEM content (alternative to path; provide one of the two) |
| `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` | Optional passphrase for the private key |
| `SNOWFLAKE_STATEMENT_TIMEOUT_SECONDS` | Per-statement timeout |
| `SNOWFLAKE_QUERY_TAG` | Query tag applied to Snowflake statements |
| `SNOWFLAKE_MAX_ROWS` | Row cap on repository results |
| `SNOWFLAKE_RETRY_ATTEMPTS` | Retry count for transient Snowflake errors |
| `SNOWFLAKE_RETRY_BACKOFF_SECONDS` | Backoff between retries |

## Data layer

| Variable | Purpose |
| :--- | :--- |
| `REPOSITORY_SEARCH_LIMIT` | Maximum catalog search hits returned to tools |
| `ACS_VINTAGES` | Comma-separated ACS 5-year vintages the repository may query |
| `NATION_GEO_ID` | Geography id used for nation-level rollups |
| `ACS_WIDE_TABLE_TEMPLATE` | Wide-table name pattern (`{vintage}`, `{series_prefix}`) |
| `METADATA_FIELD_DESCRIPTIONS_TEMPLATE` | Field-description metadata table pattern |
| `METADATA_FIPS_CODES_TEMPLATE` | FIPS metadata table pattern |
| `METADATA_GEOGRAPHIC_DATA_TEMPLATE` | Geographic metadata table pattern |
| `FIXTURES_DIR` | Directory of catalog snapshots used by the fake repository |
| `VARIABLE_CATALOG_SPEC_PATH` | Curated variable spec (topics, aggregation kinds, aliases) |
| `STATE_FIPS_NAMES_PATH` | State FIPS-to-name fixture |

## Tools

| Variable | Purpose |
| :--- | :--- |
| `TOOL_MAX_VARIABLE_CANDIDATES` | Cap on variable matches returned as ambiguous |
| `TOOL_MAX_GEOGRAPHY_CANDIDATES` | Cap on geography matches returned as ambiguous |
| `TOOL_RANK_LIMIT_MAX` | Maximum rows `rank_geographies` may request |
| `TOOL_COMPARE_MAX_GEOGRAPHIES` | Maximum geographies `compare` may take |
| `TOOL_SUGGESTION_LIMIT` | Suggestion count on `not_found` outcomes |
| `DISABLED_TOOLS` | Comma-separated tool names to omit from the registry |

## LLM and agent

| Variable | Purpose |
| :--- | :--- |
| `ANTHROPIC_API_KEY` | Anthropic API key (required for the live agent, classifier, and CLI) |
| `ANTHROPIC_MODEL` | Model id for the agent loop |
| `ANTHROPIC_CLASSIFIER_MODEL` | Model id for the intent classifier |
| `ANTHROPIC_MAX_TOKENS` | Maximum tokens requested per agent completion |
| `ANTHROPIC_EFFORT` | Effort setting for the agent model |
| `ANTHROPIC_THINKING` | Thinking mode for the agent model |
| `ANTHROPIC_TIMEOUT_SECONDS` | Per-call timeout for Anthropic requests |
| `AGENT_MAX_ITERATIONS` | Tool-use loop iteration cap |
| `AGENT_MAX_SEARCH_CALLS` | Per-turn cap on `find_variable` / `find_geography` dispatches |
| `AGENT_BUDGET_SECONDS` | Inner agent wall-clock budget |
| `AGENT_MIN_SECONDS_PER_LLM_CALL` | Minimum remaining time required to dispatch another LLM call |
| `AGENT_TIMEOUT_HANDOFF_SECONDS` | Margin subtracted from the remaining API window for the inner deadline |
| `AGENT_LLM_RETRY_ENABLED` | Whether retryable LLM errors are retried |

## Conversation, API, and guardrails

| Variable | Purpose |
| :--- | :--- |
| `RESPONSE_BUDGET_SECONDS` | Normal-conditions latency target (evals and system prompt) |
| `API_TIMEOUT_MARGIN_SECONDS` | Added to the agent budget to form the hard API timeout |
| `CONVERSATION_TTL_SECONDS` | Idle TTL for in-memory conversations |
| `CONVERSATION_MAX_TURNS` | Turn-boundary trim limit |
| `CONVERSATION_HISTORY_WINDOW_TURNS` | History window sent to the LLM |
| `CONVERSATION_MAX_CONVERSATIONS` | Cap on concurrent in-memory conversations |
| `MAX_MESSAGE_CHARS` | Maximum user message length |
| `SESSION_COOKIE_NAME` | Conversation session cookie name |
| `SESSION_COOKIE_SECURE` | Secure flag on the session cookie |
| `SESSION_COOKIE_SAMESITE` | SameSite attribute on the session cookie |
| `GUARDRAIL_CLASSIFIER_ENABLED` | Run the intent classifier after pre-checks |
| `GUARDRAIL_CLASSIFIER_CONFIDENCE_THRESHOLD` | Minimum classifier confidence to act on the intent |
| `GUARDRAIL_CLASSIFIER_TIMEOUT_SECONDS` | Classifier call timeout |
| `GUARDRAIL_CLASSIFIER_CONTEXT_TURNS` | Prior turns included in the classifier prompt |
| `GUARDRAIL_CLASSIFIER_THINKING` | Thinking mode for the classifier model |

## Demo auth

| Variable | Purpose |
| :--- | :--- |
| `DEMO_AUTH_ENABLED` | Require passphrase login for protected API routes |
| `DEMO_PASSPHRASE` | Shared demo passphrase |
| `AUTH_SIGNING_SECRET` | HMAC secret for the auth cookie |
| `AUTH_COOKIE_NAME` | Auth cookie name |
| `AUTH_COOKIE_MAX_AGE_SECONDS` | Auth cookie lifetime |

## Deployment (scripts and Cloud Run)

| Variable | Purpose |
| :--- | :--- |
| `GCP_PROJECT` | GCP project id |
| `GCP_REGION` | Cloud Run and Artifact Registry region |
| `GCP_ARTIFACT_REPO` | Artifact Registry repository name |
| `GCP_SERVICE_NAME` | Cloud Run service name |
| `GCP_RUN_SERVICE_ACCOUNT` | Optional override for the Cloud Run runtime service account |
| `WARMUP_ENABLED` | Run a Snowflake warm-up query on container startup |
| `SECRET_SNOWFLAKE_PRIVATE_KEY` | Secret Manager name for the Snowflake private key PEM |
| `SECRET_ANTHROPIC_API_KEY` | Secret Manager name for the Anthropic API key |
| `SECRET_AUTH_SIGNING_SECRET` | Secret Manager name for the auth cookie signing secret |
| `SECRET_DEMO_PASSPHRASE` | Secret Manager name for the demo passphrase |

Cloud Run instance settings (instance count, concurrency, request timeout, CPU, memory) are in `deploy/cloudrun.env` and applied by `scripts/deploy.sh`.
