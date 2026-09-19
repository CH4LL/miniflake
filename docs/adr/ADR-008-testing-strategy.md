# ADR-008: Testing strategy

Status: accepted (2026-09-19)

## Context

The requirements ask for meaningful tests and an explainable strategy. The system has two non-deterministic, paid, network-bound dependencies (LLM and Snowflake). Tests must run in CI without credentials, yet the product's real quality is only observable against the live stack.

## Options

1. **Live tests only.** Realistic, but slow, costly, flaky, and impossible in CI without secrets.
2. **Mock everything at the SDK boundary.** Fast, but mocks drift from real behaviour and encourage testing the mock.
3. **Protocol fakes plus contract tests plus opt-in live suites plus a golden eval set.** Every external dependency sits behind a protocol with a fake implementation that shares a contract test suite with the real one. Unit and component tests use fakes; end-to-end API tests inject fakes through the app factory; live suites are skipped unless an environment variable is set; a golden question set defines expected behaviour classes and is run against the deployed service with results committed.

## Decision

Option 3.

- **Unit**: pure logic (config, models, SQL guard, retry, grounding matcher, composer classification, cookie signing). No network.
- **Component**: tools and the agent loop against `FakeCensusRepository` and `FakeLLM`.
- **Contract**: the repository test suite is parametrized over the fake and the Snowflake implementation; the latter runs only when live tests are enabled, keeping the fake honest.
- **End-to-end (API)**: FastAPI `TestClient` with fakes injected; covers multi-turn context, error envelopes, auth, guardrail outcomes driven by the eval file.
- **Browser smoke**: Playwright, opt-in, one two-turn scenario.
- **Live**: Snowflake connection and templates, Anthropic client, one agent lookup; opt-in via environment variable.
- **Evals**: `evals/questions.yaml` with expected behaviour classes and provenance expectations, run by `evals/run_evals.py` against a URL; reports committed under `evals/reports/`.

Test-driven order per stage is specified in each stage spec.

## Consequences

- CI is deterministic and credential-free.
- Model behaviour regressions are caught by evals, not unit tests; evals are run manually before release and their results reported honestly.
- The fake LLM is scripted per test, so tests document the expected tool-call sequence for each scenario, which doubles as behavioural documentation.
- Not covered by design: load testing, long-running soak, adversarial red-teaming beyond the eval set. Listed in the reflection.
