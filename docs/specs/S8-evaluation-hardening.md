# S8: Evaluation and hardening

Status: see [roadmap.md](../roadmap.md). Estimate: 3 h. Depends on S7. First stage in the cut order; see the cut policy in the roadmap.

This version supersedes the planning-time spec. The original assumed a loop of live golden-set runs against the deployed stack; that loop proved slow, costly and poor at isolating causes. The superseding principle is: live runs are a measurement, not a development loop. Every behaviour fix is proven against `FakeLLM` and `FakeCensusRepository`; one live run at the end produces the committed report; scoring-rule changes after that run are applied offline by re-scoring saved observations.

## Goal

Close the evaluation harness so it can be iterated on without credentials, fix the deterministic causes behind the last report's failures, curate the golden set, and record an honest measurement of the deployed agent for the reflection.

## Tier 1 (required to close the stage)

1. **Spec superseded.** This document and a decision-log entry explaining why the live-run loop was dropped.
2. **Harness: offline iteration and a self-test.**
   - Each `ItemResult` carries the raw `ChatObservation` and the golden `notes`, so a report is self-describing and re-scorable.
   - `run_evals.py --rescore <report.json>` rebuilds observations from a saved run and re-scores them against the current golden set and scoring rules, reusing saved reference values. The new report records `rescored_from`; items no longer active are listed rather than dropped.
   - `--expected` filter alongside `--items` and `--categories`, so the strict gate (refuse and unanswerable items) can be checked cheaply.
   - Report groups failures for triage by failure kind and prints the golden note per item; the cost line is labelled as agent tokens only.
   - `run_evals` accepts an injected HTTP client and question-set path; an end-to-end test runs it in-process against the app with fakes.
3. **Outcome labelling without tool calls.** A `capability` classifier intent marks turns that may be answered without data (what can you answer, where does the data come from). With no tool traces, the composer labels the outcome `unanswerable` unless the turn is a capability turn, in which case `answer`. Prose markers are no longer used to infer outcomes.
4. **Search-call budget.** The agent loop counts `find_variable` and `find_geography` dispatches per turn. Past the configured cap, further search calls are not dispatched; the model receives an `unsupported_request` result asking it to explain what could not be found.
5. **Golden set v5.** Optional `max_tool_calls` per item, scored as a failure kind; a capability item and a search-budget item added; header schema updated.
6. **Documentation closure.** Testing strategy (how to run, gate subset, rescore, accepted failures), reflection edge cases, architecture, changelog, decision log, roadmap.
7. **One live run.** Deploy `main`, run the full set once with `--strict`, commit the report, triage failures into the accepted-failures list. No fix-and-rerun loop; a scoring bug found afterwards is fixed and applied with `--rescore`.

## Tier 2 (each independently completable; skipped items go to the reflection)

- Token-based variable search in SQL and the fake repository, plus curated aliases per series in the catalog spec.
- Batch geography name lookup (`get_geographies`) so `rank_geographies` makes one call instead of one per row.
- Retag B17001 to `count` with a catalog-spec test, and set the L07 expectation to whichever outcome the field-description table can support; only alongside token-based search.
- Parallel root groups in the runner (`--workers`), with the concurrency stated in the report header.

## Out of scope

Statistical rigour beyond a single run; automatic prompt optimisation; terminal pseudo-tools for declaring outcomes.

## Acceptance criteria

- Given the default test command, then the suite is green including the runner end-to-end test, and Ruff passes.
- Given a saved report JSON and unchanged rules, when `--rescore` runs, then per-item outcomes are reproduced exactly and the new report names its source.
- Given an agent turn that ends without tool calls, then the outcome is `unanswerable`, unless the classifier marked the turn `capability`, in which case `answer`.
- Given a turn whose search calls reach the configured cap, then no further search dispatch reaches the repository and the outcome is `unanswerable`.
- Given the golden set, then every item with `max_tool_calls` fails scoring when the observed tool-call count exceeds it.
- Given the committed report produced from `main`, then the strict-gate status is recorded and every failure is listed in the testing strategy with a reason.

## Tests to write first

1. `tests/unit/evals/test_scoring.py`: observation and notes stored on results; `max_tool_calls` failure kind; failure-kind grouping.
2. `tests/unit/evals/test_rescore.py`: round trip from saved JSON to identical per-item outcomes; missing items listed.
3. `tests/e2e/test_run_evals.py`: in-process run against the app with fakes; login, one reset per group, follow-up in the parent conversation, JSON and Markdown written, totals correct; `--expected` filter.
4. `tests/unit/agent/test_composer.py`: no-tool text is `unanswerable`; capability turn is `answer`; markers removed.
5. `tests/unit/guardrails/test_classifier.py`, `test_pipeline.py`, `tests/unit/conversation/test_service.py`, `tests/e2e/test_guardrails_api.py`: `capability` intent flows to the agent and the composer.
6. `tests/component/agent/test_loop.py`, `tests/unit/test_config.py`: search-call cap.
7. `tests/unit/evals/test_loader.py`: `max_tool_calls` validation and v5 golden set.

## Files

- `evals/run_evals.py`, `evals/scoring.py`, `evals/report.py`, `evals/rescore.py`, `evals/loader.py`, `evals/questions.yaml`, `evals/reports/`
- `app/agent/composer.py`, `app/agent/loop.py`, `app/config.py`, `app/guardrails/classifier.py`, `app/guardrails/types.py`, `app/guardrails/pipeline.py`, `app/conversation/service.py`, `app/agent/prompts/system.md`
- Tier 2: `app/data/sql/search_variables.sql`, `app/data/search_utils.py`, `app/data/repository.py`, `app/data/snowflake_repository.py`, `app/data/fake_repository.py`, `app/tools/rank_geographies.py`, `fixtures/variable_catalog_spec.yaml`

## Documentation updates at stage end

`docs/testing-strategy.md` (evaluation results, how to run and re-score, accepted failures), `REFLECTION.md` (edge cases and failure modes), `ARCHITECTURE.md` (eval harness, composer outcome rules, search budget), `CHANGELOG.md`, `docs/roadmap.md`, `docs/decision_log.md` for each decision and accepted failure.
