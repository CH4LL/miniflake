# User guide

Miniflake answers questions about the US population using American Community Survey data. This guide describes how to use the features that exist; it grows as stages in [docs/roadmap.md](docs/roadmap.md) are completed.

## Current state

The agent is available over HTTP and via the command-line runner. Multi-turn conversations preserve full turn transcripts server-side and inject resolved geography, variable, and vintage facts into follow-up turns. The web chat page and demo login arrive in later stages.

## Using the chat page

Added in S6.

## Logging in to the demo

Added in S6 and S7.

## Asking good questions

The agent answers US census questions backed by SafeGraph ACS 5-year block-group data.

- **Supported geographies:** block group (native), and nation, state, and county for **count** measures rolled up from block groups.
- **Median and rate measures** (income, age, poverty rate, and similar) are available only at block-group level.
- **Place and CBSA** levels are not supported in the current dataset.
- **Specify a year** when you need a particular ACS vintage; otherwise the latest available vintage is used.
- **Follow-up questions** reuse the last resolved geography, variable, and vintage from earlier turns in the same session.
- The agent refuses to invent numbers. If it cannot look up a value, it explains why and may ask for clarification.

## What the agent will and will not answer

**Will answer:** US population and demographic questions backed by SafeGraph ACS block-group data — lookups, comparisons, rankings, and trends within supported geography levels and vintages.

**Will ask for clarification** when a question is plausible but missing a geography, measure, or vintage (for example, "How many people live in Washington?" or "What is the income in Ohio?").

**Will refuse** without querying data:

- Off-topic requests (poems, coding help, non-US geography, general knowledge).
- Harmful or discriminatory requests, or requests for personal information about individuals.
- Prompt-injection and SQL-execution attempts caught by pre-check patterns.

**Ungrounded answers:** if the agent produces numbers that cannot be verified against tool results, the response is replaced with an explanation and the provenance panel still shows what was fetched.

Role-play overrides embedded in otherwise valid census questions are answered from data when possible; the agent ignores instructions to invent figures or reveal secrets.

## Reading provenance

Added in S6. Will explain the provenance panel: which variable, geography and year backed each figure, and the query that produced it.

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

When the request exceeds the configured response budget, the API returns HTTP 200 with `outcome: "error"` and a timeout message rather than a 5xx.

Demo authentication for the API arrives in S6.
