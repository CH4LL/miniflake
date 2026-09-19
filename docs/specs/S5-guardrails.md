# S5: Guardrails

Status: see [roadmap.md](../roadmap.md). Estimate: 2 h. Depends on S4.

## Goal

Keep the agent on topic, resistant to instruction injection, and incapable of emitting numbers that did not come from the data. Guardrails are layered so that the cheapest check runs first and the data layer is never reached for out-of-scope input.

## Scope

1. Pre-checks (deterministic, no LLM).
2. Intent classifier (cheap LLM call, structured output).
3. Output grounding check.
4. Refusal and clarification templates.
5. Wiring into `ConversationService` before and after the agent loop.

## Out of scope

Content moderation beyond the classifier; rate limiting (S7 mentions Cloud Run concurrency limits instead).

## Behaviour

### Pre-checks (`app/guardrails/prechecks.py`)

- Length and character sanity (already partially in S4; consolidated here).
- Pattern list from `app/guardrails/patterns.yaml`: prompt-injection phrases ("ignore previous instructions", "reveal your system prompt", role-play overrides), requests for SQL execution, requests for personal data about named individuals. A match yields `refuse` with the matching category, without any LLM call.

### Intent classifier (`app/guardrails/classifier.py`)

One call to the classifier model with a structured output schema: `{intent: in_scope | needs_clarification | off_topic | harmful, reason: str, confidence: float}`. Input is the current message plus the last two turns so that follow-ups like "and in Florida?" are classified in context. Configuration sets the model and a confidence threshold below which `in_scope` is treated as `needs_clarification`. Classifier failure (timeout or error) fails open to the agent loop and is logged; the agent's own grounding rules remain as protection.

### Output grounding check (`app/guardrails/grounding.py`)

Extract numeric tokens from the answer text (integers, decimals, percentages, with thousands separators and common abbreviations such as "million"). Each must match a value present in the collected `Success` tool results, allowing for rounding to the precision displayed and for percentage-of-total derivations when both operands are present. Years and ordinal ranks are exempt. A failing check replaces the text with the ungrounded-answer template and sets outcome `unanswerable`, keeping provenance so the user can see what was fetched.

### Templates (`app/guardrails/templates.yaml`)

Off-topic (states what the agent covers: US population questions from the SafeGraph Open Census ACS block-group dataset, with count rollups to state/county; example questions), harmful (brief refusal), injection (brief refusal), needs clarification (asks the specific missing element: geography, measure or vintage), ungrounded answer.

## Acceptance criteria

- Given every item with expected behaviour `refuse` in `evals/questions.yaml`, when processed through the service with a recording fake repository, then the outcome is `refuse` and the repository recorded zero calls.
- Given an injection phrase from the pattern list, then the outcome is `refuse` and the classifier was not called.
- Given a classifier response `needs_clarification`, then the outcome is `clarify` with the template text and the agent loop was not called.
- Given a classifier timeout, then the agent loop runs normally and a warning is logged.
- Given an answer text containing a number absent from tool results, then the grounding check fails and the outcome becomes `unanswerable`.
- Given an answer whose numbers are rounded versions of tool values (e.g. "about 29.5 million" for a value near that), then the grounding check passes.
- Given an answer with a percentage derived from two returned values, then the grounding check passes.

## Tests to write first

1. `tests/unit/guardrails/test_prechecks.py`: each pattern category, benign near-misses.
2. `tests/unit/guardrails/test_classifier.py`: schema parsing, threshold behaviour, fail-open.
3. `tests/unit/guardrails/test_grounding.py`: number extraction and matching rules, rounding, derived percentages, exemptions.
4. `tests/e2e/test_guardrails_api.py`: eval-driven test loading `refuse` and `clarify` items and asserting outcomes with fakes.

## Files

- `app/guardrails/__init__.py`, `prechecks.py`, `classifier.py`, `grounding.py`, `patterns.yaml`, `templates.yaml`
- `app/conversation/service.py` wiring

## Documentation updates at stage end

`ARCHITECTURE.md` (guardrails row and request lifecycle steps), `USER-GUIDE.md` (what the agent will and will not answer), `CHANGELOG.md`, `docs/roadmap.md`, `docs/decision_log.md` for tuning decisions.
