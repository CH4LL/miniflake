# S9: Documentation and reflection

Status: see [roadmap.md](../roadmap.md). Estimate: 2 h. Depends on S7 (S8 preferred). Never cut.

## Goal

Everything a reviewer or a new engineer needs is in the repository and internally consistent: how to run, how to evaluate, why each decision was made, what was cut, and what would be done next.

## Scope

1. `README.md` final: what it is, how to evaluate the demo (URL, credentials pointer, example questions by category), architecture summary with link, run locally, run tests, configuration reference (names and purposes of settings, no values), data source and scope section (SafeGraph listing, counts-only rollup policy), link map to reflection, ADRs, decision log, roadmap.
2. `REFLECTION.md` (repository root): sections on (development process and key decisions; what would be improved with more time; edge cases and failure modes not fully addressed; testing approach and what would be added), plus a section on how AI coding tools were used, drawing from `docs/decision_log.md` and the S8 report.
3. `docs/testing-strategy.md` final: layers, coverage, tradeoffs, live suites, evals.
4. `docs/EXTENDING.md` final: add a tool, add a data source, swap the LLM, swap the conversation store, with file paths that exist.
5. Synchronise `ARCHITECTURE.md`, `USER-GUIDE.md`, `CHANGELOG.md` with the shipped state; mark cut stages in `docs/roadmap.md`.
6. Release check: no secrets in history.

## Out of scope

New features. Any fix discovered here is either trivial and applied, or recorded in the reflection.

## Acceptance criteria

- Given a fresh clone and the README only, when a new engineer follows the local run instructions with their own credentials, then the health endpoint and the CLI work.
- Given the README, when a reviewer follows the demo instructions, then they reach the chat page and can log in.
- Given every ADR, then its status is `accepted` or `superseded` and the decision log references it.
- Given the roadmap, then every stage is `done` or `cut`, and every `cut` has a decision log entry and a reflection mention.
- Given the repository history, when scanned for secrets, then none are found.
- Given the reflection, then each section is present and cites concrete items (file paths, eval item ids, decision log entries) rather than generalities.

## Tests to write first

None: this stage produces documentation. A link checker over `docs/` and `README.md` is run manually or as a one-off script under `/tmp`.

## Files

- `README.md`, `REFLECTION.md`, `docs/testing-strategy.md`, `docs/EXTENDING.md`, `ARCHITECTURE.md`, `USER-GUIDE.md`, `CHANGELOG.md`, `docs/roadmap.md`, `docs/decision_log.md`

## Documentation updates at stage end

This stage is the documentation update. Final `docs/roadmap.md` status for S9 and "Last updated" line.
