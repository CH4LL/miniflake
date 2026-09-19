# Miniflake

A data-grounded chat agent that answers natural-language questions about the US population using American Community Survey data from the Snowflake Marketplace. Answers are produced only from data returned by typed query tools, and every figure is returned with its provenance.

Author: Jerzy Marondel.

## Status

Planning complete; implementation follows the stages in [docs/roadmap.md](docs/roadmap.md). Sections marked "added in Sx" are completed when that stage lands.

## Evaluating the demo

Added in S7. Will contain: the public URL, how to log in (credentials are supplied separately), example questions by category drawn from `evals/questions.yaml`, and known operational limits during the review window.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the component overview, request lifecycle and extension points. Design rationale is in the ADRs under [docs/adr/](docs/adr/) and the chronological [docs/decision_log.md](docs/decision_log.md).

In short: FastAPI serves a static chat page and a chat API; a conversation service applies layered guardrails, then runs an agent loop in which an LLM selects typed tools; tools run parametrized SQL against Snowflake through a repository protocol and return typed results with provenance; a composer verifies that every number in the answer came from tool results.

## Running locally

Added in S0 and extended through S7. Will contain: prerequisites, environment variables (names and purposes; values live in your `.env`), `uv` commands to install, run the server, run the CLI, and run tests.

## Configuration reference

Added in S0. Lists every setting in `app/config.py` with its purpose. Values are never documented here.

## Testing

See [docs/testing-strategy.md](docs/testing-strategy.md). Default `uv run pytest` needs no credentials; live suites and evals are opt-in.

## Interpretations of ambiguous requirements

Recorded as decided; see ADR-003 and ADR-006 for detail.

- "US Open Census dataset" is read as US Census data from the Snowflake Marketplace. Both the SafeGraph "US Open Census Data & Neighborhood Insights" listing and the Census Bureau source of Snowflake Public Data Products were acquired and inspected; the application defaults to the latter because it provides state, county, metro and place levels natively and a multi-year catalog. Rationale in [ADR-003](docs/adr/ADR-003-dataset-selection.md).
- "Questions about the US population" is scoped to ACS measures at Nation, State, County, CBSA and Place levels. Tract and block-group questions are declared out of scope with a clear message.
- The 60-second response requirement is enforced server-side: the agent answers or degrades gracefully within the budget rather than exceeding it.
- Authentication for the demo is a shared passphrase, available from the author on request.
- Aggregation across geographies is never performed by the application; questions that require it are answered with an explanation and the nearest supported figure.

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
