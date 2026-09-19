# User guide

Miniflake answers questions about the US population using American Community Survey data. This guide describes how to use the features that exist; it grows as stages in [docs/roadmap.md](docs/roadmap.md) are completed.

## Current state

The agent core is available via the command-line runner. It answers single-turn census questions using typed tools over Snowflake and composes grounded answers with provenance. The web chat page and HTTP API arrive in later stages.

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
- **Follow-up questions** that carry context from a prior turn require the conversation API in S4.
- The agent refuses to invent numbers. If it cannot look up a value, it explains why and may ask for clarification.

Intent classification and templated refusals for off-topic or harmful input arrive in S5.

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

Added in S4. Will document `POST /api/chat`, `POST /api/conversations/reset`, `POST /api/login`, `GET /api/health`, and the error envelope.
