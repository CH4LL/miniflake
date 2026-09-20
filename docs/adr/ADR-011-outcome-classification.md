# ADR-011: Outcome classification

Status: accepted

## Context

Every chat response carries an `outcome`: `answer`, `clarify`, `unanswerable`, `refuse` or `error`. The UI shows it as a badge, the eval harness scores it, and the strict eval gate is defined on it (every `refuse` and `unanswerable` item must be labelled so). Guardrail short-circuits set `refuse` and `clarify` deterministically. The hard case is a turn that reached the agent loop: after the model has finished, how does the system know whether it answered from data, asked a clarifying question, or explained that the question cannot be answered?

The first implementation matched a list of "not supported" phrases in the model's final text. The baseline eval run showed six correct replies labelled `answer` because the wording was not on the list, and two capability answers ("what can you ask me?") labelled `unanswerable` because they had no tool calls.

## Options

1. **Prose markers.** Recognise the outcome from phrases in the final text. Cheap; but the list can never be complete, changes to the system prompt silently change labels, and a model that paraphrases defeats it.
2. **A second LLM call to label the reply.** Robust to wording; costs a call per turn inside the time budget and is not verifiable against a scripted fake.
3. **Terminal pseudo-tools.** Give the model `declare_unanswerable` and `ask_clarification` tools and require it to end every non-answer turn by calling one. Explicit and provider-neutral; but it is a behaviour the model must comply with, and every `FakeLLM` script in the component and end-to-end suites would need the extra call, so the change could not be verified offline within the remaining time.
4. **Typed signals only.** Label from what the code already knows: the tool traces of the turn and the classifier's intent. The system prompt requires a tool call before any figure, so a turn with no data-tool call is by construction not a data answer.

## Decision

Option 4. The composer applies these rules and never reads the reply text:

- Timeout, iteration cap or an LLM error, or a trailing `tool_error`, is `error`.
- With data-tool traces (`get_value`, `rank_geographies`, `compare`, `get_trend`): any `success` is `answer`; otherwise all `ambiguous` is `clarify`; otherwise `unanswerable`.
- With catalog-only traces (`find_geography`, `find_variable`): any `ambiguous` is `clarify`; otherwise `unanswerable`.
- With no tool traces: `unanswerable`, unless the guardrail pipeline classified the turn as `capability` and passed `ungrounded_answer_allowed` to the loop, in which case it is `answer` with empty provenance.

The `capability` intent was added to the classifier for this, together with a `proceed` decision that reaches the agent without short-circuiting.

## Consequences

- Labels are deterministic and covered by unit tests on the composer; a change to the system prompt cannot move them.
- Provenance is consistent with the label: `answer` always carries at least one successful data-tool trace, except the capability case, which carries none by design.
- A clarifying question the model writes on its own without any tool returning `ambiguous` is labelled `unanswerable`. The classifier is expected to catch missing slots before the loop, and the golden set treats a model-written clarification as a pass only when a tool returned `ambiguous`. This is the known gap.
- A model that answers with a figure without calling a tool, against the prompt, is labelled `unanswerable` and shows no provenance; the eval value checks are the detection for that case (ADR-007 amendment).
- Option 3 remains the cleaner long-term design if the model is to state its own outcome; it is listed in the reflection as work that needs a scripted-fake strategy first.
