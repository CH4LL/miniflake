# ADR-009: Conversation context content

Status: accepted

## Context

CF-3 requires that "the agent must preserve conversation context across multiple turns" and says nothing about which context. ADR-005 decides where conversation state lives; this record decides what a stored turn contains and what the model sees on the next turn. The two readings differ in cost and in which follow-ups they can resolve:

- "And Florida?" needs the previous measure and vintage.
- "The second one" after an ambiguous geography needs the candidate list the tool returned.
- "Why not 2018?" needs the rejected vintages from a `period_unavailable` result.
- "How much is that compared to the earlier number?" needs the exact value returned, not the rounded prose.

There was no stakeholder to ask which of these count as "context".

## Options

1. **Text-only history.** Store the user message and the final assistant text per turn; drop tool-use and tool-result blocks. Cheapest in tokens and provider-neutral. Loses candidate lists, exact values and rejected periods; the model can only re-derive them by calling tools again, which costs time budget and may resolve differently.
2. **Text-only history plus a running summary.** As option 1, with a model-written or code-written summary of resolved facts appended. The summary carries the facts the code chooses to extract; anything else is still lost, and a model-written summary is another unverifiable step.
3. **Full per-turn transcript plus extracted resolved context.** Store the user message, every assistant tool_use block, every tool_result block and the final text, exactly as exchanged with the provider. Separately extract a small `ResolvedContext` (last geography ids and names, variable id, vintage) from successful tool results and render it into the system prompt as "recently discussed". Trim history only at whole-turn boundaries so tool_use and tool_result pairs stay matched.

## Decision

Option 3. It is the conservative reading of CF-3: no follow-up is ruled out by a choice the code made about what mattered. The `ResolvedContext` block exists so the common follow-ups resolve from a short, deterministic summary that tests can assert on, while the transcript remains available for the uncommon ones.

Provider specifics that follow from storing the raw exchange:

- Anthropic thinking blocks are kept as `OpaqueBlock` values and re-sent unchanged within the turn that produced them, because the API requires them alongside tool_use blocks. They are stripped from completed prior turns when the message list is rebuilt, because the API validates their signatures and they carry no follow-up value.
- Tool JSON schemas are sanitised for strict mode inside the Anthropic client, so the stored transcript is what the provider actually saw.

Bounds: a configurable history window in turns, a per-conversation turn cap, and a message-length cap. Trimming drops the oldest whole turns.

## Consequences

- Token cost per turn grows with the length of the conversation and with the size of tool results; the history window caps it.
- A second provider must either accept the same block model or map it; `OpaqueBlock` keeps provider-only content out of the neutral types.
- Follow-up resolution is testable without a model: component tests assert on the rendered context block and on the message list handed to `FakeLLM`.
- Guardrail short-circuit turns (refusals, clarifications) are stored as turns, so a reply to a clarification has its antecedent.
- The alternative, if token cost became the constraint, is option 2 behind the same `ConversationStore` protocol; the decision to reject it is recorded in the decision log.
