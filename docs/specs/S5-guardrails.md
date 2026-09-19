# S5: Guardrails

Status: see [roadmap.md](../roadmap.md). Estimate: 2 h. Depends on S4.

## Goal

Keep the agent on topic, resistant to instruction injection, and limited to data obtained through typed tools. Guardrails are layered so that the cheapest check runs first and the data layer is never reached for out-of-scope input.

## Scope

1. Pre-checks (deterministic, no LLM).
2. Intent classifier (cheap LLM call, structured output).
3. Refusal and clarification templates.
4. Wiring into `ConversationService` before the agent loop.

## Out of scope

Content moderation beyond the classifier; rate limiting (S7 mentions Cloud Run concurrency limits instead); post-answer numeric verification against tool payloads.

## Behaviour

### Pre-checks (`app/guardrails/prechecks.py`)

- Length and character sanity (already partially in S4; consolidated here).
- Pattern list from `app/guardrails/patterns.yaml`: prompt-injection phrases ("ignore previous instructions", "reveal your system prompt", role-play overrides), requests for SQL execution, requests for personal data about named individuals. A match yields `refuse` with the matching category, without any LLM call.

### Intent classifier (`app/guardrails/classifier.py`)

One call to the classifier model with a structured output schema: `{intent: in_scope | needs_clarification | off_topic | harmful, reason: str, confidence: float, missing: geography | measure | vintage | generic | null}`. Input is the current message plus the last two turns so that follow-ups like "and in Florida?" are classified in context. Context is rendered as plain text only (never raw `tool_use` blocks). Configuration sets the model and a confidence threshold below which `in_scope` is treated as `needs_clarification`. Omitted vintage is not treated as missing: the agent defaults to the latest ACS 5-year release. Capability questions (what the agent can answer, where the data comes from) are in_scope. Classifier failure (timeout or error) fails open to the agent loop and is logged; the agent's own grounding rules remain as protection.

### Templates (`app/guardrails/templates.yaml`)

Off-topic (states what the agent covers: US population questions from the SafeGraph Open Census ACS block-group dataset, with count rollups to state/county; example questions), harmful (brief refusal), injection (brief refusal), needs clarification (asks the specific missing element: geography or measure). `needs_clarification_vintage` is unused: the pipeline ignores `missing=vintage`.

### Pipeline (`app/guardrails/pipeline.py`)

`GuardrailPipeline` composes pre-checks and the classifier. It returns a layer-neutral `GuardrailDecision` (`outcome`, `text`); `ConversationService` builds the `AgentAnswer` so `app/guardrails/` never imports `app/agent/`. Guardrail short-circuit turns (refusal and clarification) are persisted as user plus assistant text so a follow-up answering the clarification has an antecedent. If the classifier returns `needs_clarification` with `missing=vintage`, the pipeline does not short-circuit and the agent loop runs. Population phrasing (`population`, `how many people`, `populous`) does not short-circuit a `missing=measure` decision.

## Acceptance criteria

- Given every item with expected behaviour `refuse` in `evals/questions.yaml`, when processed through the service with a recording fake repository, then the outcome is `refuse` and the repository recorded zero calls.
- Given an injection phrase from the pattern list, then the outcome is `refuse` and the classifier was not called.
- Given a classifier response `needs_clarification` with `missing=geography` or `measure` (and the message is not a named population question), then the outcome is `clarify` with the template text and the agent loop was not called.
- Given a classifier response `needs_clarification` with `missing=vintage`, then the agent loop runs.
- Given a classifier timeout, then the agent loop runs normally and a warning is logged.

## Tests to write first

1. `tests/unit/guardrails/test_prechecks.py`: each pattern category, benign near-misses.
2. `tests/unit/guardrails/test_classifier.py`: schema parsing, threshold behaviour, fail-open.
3. `tests/e2e/test_guardrails_api.py`: refuse items block data access; geography clarify skips the agent; vintage clarify does not.

## Files

- `app/guardrails/__init__.py`, `types.py`, `prechecks.py`, `classifier.py`, `pipeline.py`, `patterns.yaml`, `templates.yaml`
- `app/conversation/service.py` wiring

## Documentation updates at stage end

`ARCHITECTURE.md` (guardrails row and request lifecycle steps), `USER-GUIDE.md` (what the agent will and will not answer), `CHANGELOG.md`, `docs/roadmap.md`, `docs/decision_log.md` for tuning decisions.
