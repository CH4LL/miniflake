# ADR-005: Conversation state

Status: accepted

## Context

Context must persist across turns so that follow-ups such as "and in Florida?" or "what about 2015?" resolve correctly. The demo runs for a review window on a single service; reviewers do not need conversations to survive a redeploy.

## Options

1. **Client-side history.** The browser resends the full transcript each turn. Simplest server; but the client can tamper with history, payloads grow, and resolved context (which geography id the model settled on) would have to be trusted from the client.
2. **Server-side in-memory store with TTL, behind a protocol.** Conversation id in a cookie; history and resolved context held in process memory; expired conversations evicted. Correct as long as one instance serves all requests.
3. **Server-side persistent store (Firestore or Redis).** Survives restarts and scales horizontally; costs setup time and another credential, for a property the evaluation does not need.

## Decision

Option 2. `ConversationStore` is a protocol with an `InMemoryConversationStore` implementation. Conversations expire on idle time, not absolute age, and are capped in number. Cloud Run is pinned to one instance during the evaluation window so the store is coherent. Guardrail refusals and clarifications are stored as turns too, so a reply to a clarification has its antecedent. Option 3 is the documented production swap, implementable behind the same protocol.

What a stored turn contains, and how it is replayed to the model, is a separate decision: [ADR-009](ADR-009-conversation-context-content.md).

## Consequences

- A redeploy clears conversations; acceptable and stated in the README.
- Scaling beyond one instance requires implementing option 3 first; this is listed in the reflection as a production gap.
- Follow-up resolution is testable without an LLM by asserting on the rendered context block.
