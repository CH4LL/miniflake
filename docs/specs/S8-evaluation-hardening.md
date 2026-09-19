# S8: Evaluation and hardening

Status: see [roadmap.md](../roadmap.md). Estimate: 3 h. Depends on S7. First stage in the cut order; see the cut policy in the roadmap.

## Goal

Measure the deployed agent against the golden question set, fix the failures that matter most, and produce an honest record of what remains for the reflection.

## Scope

1. `evals/run_evals.py`: runs every item in `evals/questions.yaml` against a target URL (deployed by default, local optional), using a fresh conversation per item except for items marked as follow-ups, which run in sequence within one conversation.
2. Scoring per item: outcome class matches expected; expected provenance elements present (variable id or series, geography level or name, year when specified); latency within budget; for `answer` items with a `expected_value_check`, the value falls within the tolerance of a reference query run directly against the repository.
3. Report written to `evals/reports/<timestamp>.md` and `.json`: per-category pass rate, per-item result with the agent's text, provenance summary, latency, tokens, and a free-text note field for the analyst.
4. Triage and fixes: at least the failing `refuse` and `unanswerable` items must pass; `answer` and `clarify` failures are fixed in order of impact (prompt wording, tool descriptions, catalog curation, grounding rules) within the time budget.
5. Latency and cost: p50 and p95 latency, tool calls per question, tokens per question, projected cost per hundred questions recorded in the report.
6. Unresolved items copied into `docs/reflection.md` under edge cases and failure modes.

## Out of scope

Statistical rigour beyond a single run; automatic prompt optimisation.

## Acceptance criteria

- Given the deployed URL and credentials, when `run_evals.py` runs, then a report is written with one row per eval item and category totals.
- Given the report, then every `refuse` item passes and every `unanswerable` item passes.
- Given a follow-up item, then it is executed in the same conversation as its parent and scored against the follow-up expectation.
- Given an `answer` item with a value check, then the reported value is compared against a direct repository query and the comparison result is in the report.
- Given the final report, then p50 and p95 latency are below the response budget.

## Tests to write first

1. `tests/unit/evals/test_loader.py`: YAML schema validation for `evals/questions.yaml` (required fields, allowed categories and behaviour classes, follow-up references resolve).
2. `tests/unit/evals/test_scoring.py`: outcome matching, provenance matching, tolerance comparison, report rendering from a fixed result set.

## Files

- `evals/run_evals.py`, `evals/scoring.py`, `evals/report.py`, `evals/reports/` (committed reports)
- Fixes may touch `app/agent/prompts/system.md`, tool descriptions, `fixtures/variable_catalog_spec.yaml`, `app/guardrails/*`

## Documentation updates at stage end

`docs/reflection.md` (edge cases and failure modes, testing approach), `docs/testing-strategy.md` (eval results summary and how to re-run), `CHANGELOG.md`, `docs/roadmap.md`, `docs/decision_log.md` for each hardening decision and each accepted failure.
