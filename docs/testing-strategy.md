# Testing strategy

Rationale and alternatives are in [ADR-008](adr/ADR-008-testing-strategy.md). This document describes the layers, what each catches, what is deliberately left out, and how to run them. Per-stage test lists are in the stage specs under [specs/](specs/).

## Layers

| Layer | Location | Doubles used | Catches | Runs in CI |
| :--- | :--- | :--- | :--- | :---: |
| Unit | `tests/unit/` | None or in-memory stubs | Logic errors in config loading, models, SQL guard and limit clamping, retry policy, composer outcome classification, cookie signing | yes |
| Component | `tests/component/` | `FakeCensusRepository`, `FakeLLM` | Tool behaviour for every outcome type; agent loop control flow (iteration cap, deadline, tool error propagation); context resolution | yes |
| Contract | `tests/component/data/test_repository_contract.py` | Parametrized over fake and real repository | Divergence between the fake and the Snowflake implementation (ordering, latest-date semantics, provenance shape) | fake: yes; real: live only |
| End-to-end API | `tests/e2e/` | Fakes injected via the app factory | HTTP contract, error envelope, session and auth behaviour, multi-turn follow-ups, guardrail outcomes for eval-derived inputs | yes |
| Browser smoke | `tests/e2e/test_ui_smoke.py` | App with fakes, Playwright | The page actually works: send, render, provenance panel, error banner | opt-in |
| Live | `tests/live/` | None | Credentials, connectivity, SQL validity against the real schema, LLM request mapping, one real end-to-end lookup | opt-in |
| Evals | `evals/` | None; runs against a URL | Model behaviour: outcome classes per question category, provenance expectations, tool-call budget, latency, value accuracy on sampled items | manual, reported |
| Eval harness self-test | `tests/e2e/test_run_evals.py`, `tests/unit/evals/` | App with fakes, in-process HTTP client | The runner itself: login, one reset per root group, follow-ups in the parent conversation, report files, filters, workers, offline re-scoring | yes |

## Principles

- Every external dependency is behind a protocol with a fake. Tests never patch SDK internals.
- Fakes are kept honest by contract tests that run the same assertions against the real implementation when credentials are present.
- `FakeLLM` is scripted per test with the exact sequence of tool calls and final text, so each component test reads as a behavioural example.
- Tests are written before implementation, in the order given in each stage spec.
- Fixture data under `fixtures/` is a snapshot of the real catalog produced by `scripts/snapshot_catalog.py`, so fake-backed tests use real geography names and variable ids.

## Running

- Default: `uv run pytest` runs unit, component, and end-to-end tests with fakes. No credentials required.
- Live suites: set `RUN_LIVE_TESTS=1` and provide the Snowflake and Anthropic settings in the environment; `uv run pytest tests/live`.
- Browser smoke: set `RUN_BROWSER_TESTS=1` with Playwright installed; `uv run pytest tests/e2e/test_ui_smoke.py`.
- Evals: `uv run python evals/run_evals.py --target <url>`; results are written to `evals/reports/`. See the S8 spec for scoring rules and the section below for the modes.

## Evaluation harness

Live runs are a measurement, not a development loop: behaviour fixes are proven against fakes first, and a live run only records where the deployed agent stands. The harness in `evals/` is built to make that cheap.

- `evals/questions.yaml` is the golden set (schema in its header). Each item declares an expected outcome and optionally provenance, a value check, a clarify slot, a no-data-call constraint, and a tool-call budget (`max_tool_calls`).
- `evals/loader.py` validates the set and groups follow-ups with their parent so a group runs in one conversation.
- `evals/scoring.py` turns a `ChatObservation` (the raw `/api/chat` payload) into an `ItemResult` with typed failures (`outcome`, `clarify_slot`, `no_data_call`, `provenance`, `tool_budget`, `value`, `latency`). The observation and the golden note are stored on the result, so a report is self-describing.
- `evals/reference.py` fetches reference values from the repository for value checks.
- `evals/report.py` renders the JSON and Markdown report: summary, per-item results with the golden note, and failures grouped by kind for triage. The cost line is agent tokens only; the API does not return classifier usage.
- `evals/rescore.py` re-scores a saved JSON report against the current golden set and rules without contacting the service.

Modes of `evals/run_evals.py`:

| Purpose | Command |
| :--- | :--- |
| Full set against the deployed service | `DEMO_PASSPHRASE=... uv run python evals/run_evals.py --target <url> --strict` |
| Strict-gate subset only (cheap) | `... --expected refuse unanswerable` |
| Specific items or categories | `... --items L01 F01` or `... --categories lookup follow_up` |
| Skip Snowflake value checks | `... --no-check-values` |
| Faster wall clock, concurrent root groups | `... --workers 3` (latency figures then reflect load; the header records the worker count) |
| Re-score a saved report offline | `uv run python evals/run_evals.py --rescore evals/reports/<slug>.json` (add `--requery-values` to refresh reference values from Snowflake) |

A re-scored report records `rescored_from` and lists items from the source run that are no longer active in the golden set. Reports produced before raw observations were stored cannot be re-scored; the runner says so and asks for a fresh run.

`--strict` exits non-zero when any `refuse` or `unanswerable` item fails, which is the S8 gate.

## Deliberately not covered

- Load and concurrency testing: the demo runs on a single instance with a concurrency cap; behaviour under load is a documented production gap.
- Soak testing of the in-memory conversation store beyond TTL unit tests.
- Systematic adversarial red-teaming beyond the injection and harmful categories in the eval set.
- Exhaustive SQL correctness across every variable in the catalog; templates are tested on representative variables per topic, and evals sample value accuracy.
- Visual regression of the UI.

## Evaluation results

Latest committed report: [evals/reports/20260919T133835Z.md](../evals/reports/20260919T133835Z.md). It predates the current composer, search and classifier behaviour and the golden set v5, so it serves as the baseline for the next run rather than a description of the current agent. Baseline over 51 active items: 29 passed; strict gate failed on 11 `refuse` and `unanswerable` items; latency p50 within budget, p95 over budget. The per-item reading of that report is in the decision log (S8 entries dated 2026-09-20) and in [reflection.md](reflection.md).

### Next live run

A single manual step: deploy `main`, run the full set once with `--strict`, commit the report, record the date in the decision log. Failures are triaged into the accepted list below rather than fixed and re-run; a scoring bug found afterwards is fixed and applied with `--rescore`.

### Accepted failures

Items whose failure in a report is acceptable given the golden-set expectation, with the reason. Updated after each committed run so every remaining failure has an entry.

| Item | Reason |
| :--- | :--- |
| L06 | The dataset has no place-level geographies; the agent is expected to explain the limit rather than substitute a county. A report that shows substitution is a fail on outcome and is judged from the text. |
| AG01 | Ambiguous place names with no place-level data; the agent may explain the limit or ask for a state. Either reading is acceptable, the item stays `clarify`. |
| L07 | Expected `answer` from B17001 counts rolled up to State. Fails on provenance if the live metadata names the poverty fields in a way the catalog aliases do not cover; the alias list is the remedy. |
