# Testing strategy

Rationale and alternatives are in [ADR-008](adr/ADR-008-testing-strategy.md). This document describes the layers, what each catches, what is deliberately left out, and how to run them. Per-stage test lists are in the stage specs under [specs/](specs/).

At the end of the build, `uv run pytest -q -m "not live and not browser"` collects and passes 333 tests (253 unit, 53 component, 27 e2e). A further 24 are opt-in: 14 Snowflake contract cases parametrized with the fake, 9 under `tests/live/`, and 1 Playwright smoke. Full collect-only is 357.

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

Latest committed report: [evals/reports/20260920T004303Z.md](../evals/reports/20260920T004303Z.md). It re-scores the live run [20260920T002700Z](../evals/reports/20260920T002700Z.md) against the golden set as it now stands; both are kept, the live run being the measurement and the re-scored one the current reading of it. Latency percentiles in both come from a run with concurrent root groups, which the report header records.

Over the 53 active items, every category passes except two single-item outcome mismatches, both `unanswerable` items answered with a clarifying question, so the strict gate does not pass. Latency p50 and p95 are inside the response budget. The per-item detail, including the text of every answer, is in the report itself.

### Accepted failures

Items whose failure in the committed report is accepted rather than fixed, with the reason. Updated after each committed run so every remaining failure has an entry.

| Item | Reason |
| :--- | :--- |
| AG01 | An ambiguous place name with no place-level data in the dataset. The classifier asks which geography is meant before the agent can explain that the level is unsupported. The clarification is useful to a user and the reformulation it invites is answerable, so the behaviour is kept and the item keeps expecting `unanswerable`, which is the stricter reading. |
| UL02 | A street address. The same clarification path fires, where an explanation that no sub-block-group geography exists would serve the user better. Distinguishing "ambiguous" from "below the smallest supported grain" needs a place and address catalogue the dataset does not carry. |
| L06 | Place-level question. Currently passes: the agent explains the limit and offers the containing county. It stays on this list because a substitution of the county figure without saying so would also read as an answer to a user, and only the text distinguishes them. |

The golden set also records one dataset gap rather than a behaviour gap. The curated catalogue in `fixtures/variable_catalog_spec.yaml` lists poverty, housing, health insurance and commuting series, but the marketplace field-description table returns no estimate rows for them, so `find_variable` cannot reach them and the system prompt advertises topics the tools cannot serve. L07 therefore expects `unanswerable`. Trimming the catalogue to the series that are actually reachable needs a live metadata query and is listed in [REFLECTION.md](../REFLECTION.md).
