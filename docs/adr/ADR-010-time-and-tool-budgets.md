# ADR-010: Time and tool budgets

Status: accepted

## Context

CF-4 requires "complete responses within 60 seconds under normal conditions". A turn is a sequence of paid, network-bound calls whose count the model decides: a classifier call, then an agent loop of LLM calls interleaved with Snowflake queries. Three things can burn the budget: a slow provider or warehouse, a model that keeps searching the catalog without finding a variable, and a model that keeps calling tools without finishing. The API must return something useful in every case rather than hang, and the eval harness needs a definition of "within 60 seconds" it can score.

## Options

1. **60 seconds as a hard kill everywhere.** One number for the agent budget, the API timeout, Cloud Run and the eval client. Simple; but a legitimate complex lookup (rank ten counties, resolve their names, compare two vintages) that finishes at 65 seconds is cut and reported as an error, and the eval and the runtime disagree about nothing while the user gets less than the system could deliver.
2. **60 seconds as the normal-conditions target, with a longer hard cutoff.** The response budget is what evals score and what the system prompt tells the model to aim for; the agent budget, the API timeout and the Cloud Run request timeout sit above it in that order, so a slow turn finishes and is scored as slow rather than killed. The hard cutoff is the safety net.
3. **No inner budget; rely on the API timeout only.** The route's `wait_for` cuts the worker thread's result, but the agent loop keeps running until its next check, so a late tool call and a late save can happen after the response has gone out.

Bounding model thrash is a separate axis:

- **Iteration cap only.** Bounds the number of LLM round trips. Does not stop a turn from spending all of them on `find_variable`.
- **Iteration cap plus a per-turn search-call cap.** Catalog searches (`find_variable`, `find_geography`) are counted separately; past the cap the loop does not dispatch the call and returns an `unsupported_request` result telling the model to stop searching and explain what it could not find.

## Decision

Option 2 with the search-call cap.

- `RESPONSE_BUDGET_SECONDS` is the CF-4 target: eval latency scoring and the time hint in the system prompt.
- The agent loop's deadline for a turn is derived when the loop starts: the remaining API window after guardrails, minus a handoff margin. A fixed inner cap was tried first and stopped a follow-up turn while the API still had headroom.
- The loop checks the deadline before every LLM call and before every tool dispatch, and refuses to dispatch when less than a per-LLM-call minimum remains, so a late query cannot run past the deadline.
- `POST /api/chat` wraps the service in `asyncio.wait_for` at the hard API timeout (agent budget plus a margin). On expiry it returns a normal envelope with `outcome: error` and the timeout template listing the tools attempted; a cancellation token stops the late-finishing turn from saving. Cloud Run's request timeout is above the API timeout.
- `AGENT_MAX_ITERATIONS` bounds LLM round trips; `AGENT_MAX_SEARCH_CALLS` bounds catalog searches per turn. Both are stated to the model in the system prompt.

All values are configuration; the ordering (target below agent budget below API timeout below platform timeout) is the invariant.

## Consequences

- A turn that ends by timeout, iteration cap or search cap is an honest `error` or `unanswerable` with the attempted tools listed, never a partial answer or a hang.
- Evals can report p50 and p95 against the target and count a slow answer as a latency failure rather than an outcome failure.
- The system prompt states both budgets, which reduced search thrash in the final measurement; the caps are what hold when the prompt is ignored.
- Time spent in the classifier counts against the API window, not the agent budget, so a slow classifier shortens the loop rather than overrunning the route.
- The safety net is wider than the target: a user may wait longer than 60 seconds for a hard query. This is the intended tradeoff and is stated in the README's requirement interpretations.
