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
| Evals | `evals/` | None; runs against a URL | Model behaviour: outcome classes per question category, provenance expectations, latency, value accuracy on sampled items | manual, reported |

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
- Evals: `uv run python evals/run_evals.py --target <url>`; results are written to `evals/reports/`. See the S8 spec for scoring rules.

## Deliberately not covered

- Load and concurrency testing: the demo runs on a single instance with a concurrency cap; behaviour under load is a documented production gap.
- Soak testing of the in-memory conversation store beyond TTL unit tests.
- Systematic adversarial red-teaming beyond the injection and harmful categories in the eval set.
- Exhaustive SQL correctness across every variable in the catalog; templates are tested on representative variables per topic, and evals sample value accuracy.
- Visual regression of the UI.

## Evaluation results

Filled in at S8 with a link to the latest report under `evals/reports/`, per-category pass rates, latency percentiles, and the list of accepted failures.
