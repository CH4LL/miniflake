# Agent workflow

How to pick up work in this repository without re-reading the codebase. Applies to humans and coding agents alike.

## Start here

1. Read [roadmap.md](roadmap.md). Find the first stage whose status is not `done` or `cut`. That is the current stage.
2. Open its spec in [specs/](specs/). The spec is the contract: scope, out of scope, behaviour, acceptance criteria, tests to write first, files, documentation updates.
3. Skim the "Manual steps" section if present; if a manual step is not done (credentials missing, listing not acquired), stop and report it instead of working around it.
4. Read only the code the spec's "Files" section names plus their direct dependencies. [ARCHITECTURE.md](../ARCHITECTURE.md) describes the boundaries; do not scan the whole tree.
5. If the stage is `todo`, set it to `in-progress` in the roadmap before writing code.

## While working

- Follow test-driven development as required by `.cursorrules`: write the tests listed under "Tests to write first" in the given order, watch them fail, implement, watch them pass.
- Keep adjustable values in `app/config.py` (or the YAML files the spec names), never in code or documentation.
- When a decision is made that the spec did not anticipate, or an approach is tried and abandoned, add an entry to [decision_log.md](decision_log.md) immediately, in the entry format defined there.
- When an alternative architecture is weighed, write an ADR in [adr/](adr/) following the existing files' structure and link it from the decision log.
- If the spec turns out to be wrong or incomplete, edit the spec first, then implement. Specs are living documents; the roadmap order is not.
- Do not start the next stage's work inside the current stage. If something from a later stage is a hard prerequisite, note it in the decision log and do the minimum.

## Stage end checklist

Run through every item before setting the stage to `done`:

- [ ] Every acceptance criterion in the spec is covered by a passing test or, for manual criteria, verified and noted in the decision log.
- [ ] `ruff` and `pytest` pass locally; CI is green.
- [ ] Live tests relevant to the stage pass when run with credentials (record the date in the decision log).
- [ ] [CHANGELOG.md](../CHANGELOG.md) has an entry for the stage.
- [ ] [ARCHITECTURE.md](../ARCHITECTURE.md) reflects the components that now exist.
- [ ] [USER-GUIDE.md](../USER-GUIDE.md) reflects any user-facing behaviour added.
- [ ] [decision_log.md](decision_log.md) has entries for every decision, dead end and deviation encountered.
- [ ] The spec's "Documentation updates at stage end" list is complete.
- [ ] [roadmap.md](roadmap.md): stage status set to `done`, "Last updated" line updated.

## Cutting a stage

If time forces a cut, follow the cut order in the roadmap. Set the stage status to `cut`, add a decision log entry of type `cut` stating what was dropped and the user-visible consequence, and add the item to the "edge cases and failure modes" or "with more time" section of [reflection.md](reflection.md).

## Evaluations

`evals/questions.yaml` is the behavioural definition of the product. When a stage changes agent behaviour (S3, S5, S8), add or adjust eval items in the same change and note it in the changelog. Items are never deleted; obsolete items get `status: retired` with a reason.

## Where things live

| Question | Look in |
| :--- | :--- |
| What is required? | [requirements.md](requirements.md) |
| What is next? | [roadmap.md](roadmap.md) |
| What exactly to build? | [specs/](specs/) |
| Why was it built this way? | [adr/](adr/), [decision_log.md](decision_log.md) |
| How is it structured? | [ARCHITECTURE.md](../ARCHITECTURE.md) |
| How to extend it? | [EXTENDING.md](EXTENDING.md) |
| How is it tested? | [testing-strategy.md](testing-strategy.md) |
| What does the data look like? | [data/dataset.md](data/dataset.md) |
| What should the agent do on question X? | `evals/questions.yaml` |
| How does a user use it? | [USER-GUIDE.md](../USER-GUIDE.md) |
| What changed? | [CHANGELOG.md](../CHANGELOG.md) |
