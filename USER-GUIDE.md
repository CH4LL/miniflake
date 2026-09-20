# User guide

Miniflake answers questions about the US population using American Community Survey data. This guide describes how to use the features that exist; it grows as stages in [docs/roadmap.md](docs/roadmap.md) are completed.

## Current state

The agent is available over the web chat page, HTTP API, and command-line runner. Multi-turn conversations preserve full turn transcripts server-side and inject resolved geography, variable, and vintage facts into follow-up turns. Demo authentication protects the API and chat page when enabled.

## Public demo

When deployed to Cloud Run, open https://miniflake-eowbm7u4ua-uk.a.run.app (or the URL printed by `scripts/deploy.sh`). Log in with the demo passphrase, available from the author on request. The chat page and API behave the same as locally; cookies are marked secure on HTTPS.

Cloud Run keeps one warm instance during the review window. Conversations are stored in memory on that instance and are lost if it restarts. The server runs a Snowflake warm-up query on startup so the first question after deploy completes within the response budget.

## Using the chat page

Open the application root URL in a browser (for example `http://localhost:8000/` when running locally). If demo auth is enabled, you will see a passphrase login form first.

The chat page provides:

- A message list showing your questions and the agent's answers
- An outcome badge on each assistant message (`answer`, `clarify`, `unanswerable`, `refuse`, or `error`)
- A collapsible provenance panel on each assistant message showing tool calls, variable and geography names, year, and the SQL with parameters
- A loading indicator with elapsed seconds while a request is in progress
- An error banner with the request id when something goes wrong
- A **New conversation** button to clear server-side history and start fresh

**Keyboard shortcuts:** Enter sends the message; Shift+Enter inserts a newline.

## Logging in to the demo

When `DEMO_AUTH_ENABLED` is true (the default), the chat page and protected API routes require a passphrase.

1. Open the application URL in a browser.
2. Enter the demo passphrase (configured as `DEMO_PASSPHRASE` in the environment).
3. Click **Log in**. A signed, HTTP-only cookie is set for the session.
4. You can now send messages and use **New conversation**.

Failed logins return a generic error without revealing whether the passphrase was wrong. The health endpoint (`/api/health`) stays open without authentication.

To disable auth for local development, set `DEMO_AUTH_ENABLED=false` in your `.env` file.

## Asking good questions

The agent answers US census questions backed by SafeGraph ACS 5-year block-group data.

- **Supported geographies:** block group (native), and nation, state, and county for **count** measures rolled up from block groups.
- **Median measures** (median income, median age, median rent, and similar) are available only at block-group level. Poverty is stored as counts, so poverty shares at state and county level are derived from summed counts.
- **Place and CBSA** levels are not supported in the current dataset.
- **Specify a year** when you need a particular ACS vintage; otherwise the latest available vintage is used.
- **Follow-up questions** reuse the last resolved geography, variable, and vintage from earlier turns in the same session.
- **Name the measure plainly** ("poverty line", "median household income", "how educated"): the catalog search matches every significant word in any order and knows common phrasings. A measure the catalog does not hold is reported as unavailable after a bounded number of searches.
- The agent refuses to invent numbers. If it cannot look up a value, it explains why and may ask for clarification.

## What the agent will and will not answer

**Will answer:** US population and demographic questions backed by SafeGraph ACS block-group data — lookups, comparisons, rankings, and trends within supported geography levels and vintages — and questions about its own coverage and data source.

**Will ask for clarification** when a question is plausible but missing a geography or an underspecified measure (for example, "How many people live in Washington?" or "What is the income in Ohio?"). Omitted year uses the latest ACS 5-year vintage; "population" means total population.

**Will refuse** without querying data:

- Off-topic requests (poems, coding help, non-US geography, general knowledge).
- Harmful or discriminatory requests, or requests for personal information about individuals.
- Prompt-injection and SQL-execution attempts caught by pre-check patterns.

**Outcome badges without data:** a reply that needed no data lookup is badged `unanswerable` (the agent explained a limit or could not find the measure), except for questions about the agent itself ("What can you answer?", "Where does the data come from?", "Which years do you cover?"), which are badged `answer` with an empty provenance panel.

Role-play overrides embedded in otherwise valid census questions are answered from data when possible; the agent ignores instructions to invent figures or reveal secrets.

## Reading provenance

Each assistant message has a **Provenance** expander. Click it to see:

- **Tool calls** — which tools ran, their inputs, and result kinds. For successful lookups, the resolved variable name, geography name, and vintage appear.
- **SQL queries** — the parametrized SQL executed against Snowflake, with parameters listed below the query text.
- **Aggregation** — for rolled-up geographies, the aggregation method (for example `sum` across block groups).

Use provenance to verify that every number in the answer traces back to a specific data query.

## Command-line runner

Run a single question against Snowflake and Anthropic:

```bash
uv run python scripts/chat_cli.py "What is the population of Texas?"
```

Or pipe a question from stdin:

```bash
echo "What kind of questions can you answer?" | uv run python scripts/chat_cli.py
```

Required environment variables are listed in `.env.example`. At minimum you need Snowflake credentials, `ANTHROPIC_API_KEY`, and a working `.env` file.

The CLI prints:

- the outcome class (`answer`, `clarify`, `unanswerable`, or `error`)
- the answer text
- each tool call with its result kind
- provenance records for successful data lookups

Adjust agent timeouts and iteration limits with the `AGENT_*` and `ANTHROPIC_*` settings in configuration.

## Local logs

When running the server or CLI locally, structured JSON lines are appended to the file named by `LOG_FILE` (gitignored). Open that file in the editor while the process is running. Search by `request_id`, `conversation_id`, `outcome`, or `stop_reason` to see why a turn failed (`timeout`, `iteration_cap`, or `llm_error`). An empty `LOG_FILE` disables the file sink; production keeps stderr-only logging for Cloud Logging.

## API

### Health

`GET /api/health` returns service status and version.

### Chat

`POST /api/chat` with JSON body `{"message": "your question"}`.

The response includes:

- `conversation_id` — server-side conversation identifier
- `text` — answer text
- `outcome` — `answer`, `clarify`, `unanswerable`, `refuse`, or `error`
- `provenance` — data-source records for successful lookups
- `tool_calls` — tool names and result kinds for this turn
- `latency_ms` — server-side latency

An HTTP session cookie identifies the conversation across turns. Send the cookie on each request; the server stores the full turn transcript and resolved context.

Example with curl (cookie jar):

```bash
curl -c cookies.txt -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the population of Texas?"}' \
  http://localhost:8000/api/chat
```

Follow up in the same session:

```bash
curl -b cookies.txt -c cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"message":"And in Florida?"}' \
  http://localhost:8000/api/chat
```

### Reset conversation

`POST /api/conversations/reset` clears server-side history and starts a fresh conversation. The response includes a new `conversation_id` and updates the session cookie.

### Errors

Errors return `{"error": {"code", "message", "request_id"}}`. Codes include `invalid_input`, `timeout`, `upstream_unavailable`, and `internal`. Every response includes an `X-Request-Id` header.

When the request exceeds the configured hard timeout, the API returns HTTP 200 with `outcome: "error"` and a timeout message rather than a 5xx.

### Authentication

`POST /api/login` with JSON body `{"passphrase": "your-passphrase"}` exchanges the passphrase for a signed auth cookie. Protected routes (`POST /api/chat`, `POST /api/conversations/reset`) return `401` with code `unauthorized` when the cookie is missing or invalid.

`GET /api/session` returns `{"auth_required": bool, "authenticated": bool}` so the chat page can decide whether to show the login form.

Required environment variables when auth is enabled: `DEMO_PASSPHRASE`, `AUTH_SIGNING_SECRET`. See `.env.example`.
