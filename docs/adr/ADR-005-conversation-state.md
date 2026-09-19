# ADR-005: Conversation state

Status: accepted (2026-09-19)

## Context

Context must persist across turns so that follow-ups such as "and in Florida?" or "what about 2015?" resolve correctly. The demo runs for a review window on a single service; reviewers do not need conversations to survive a redeploy.

## Options

1. **Client-side history.** The browser resends the full transcript each turn. Simplest server; but the client can tamper with history, payloads grow, and resolved context (which geography id the model settled on) would have to be trusted from the client.
2. **Server-side in-memory store with TTL, behind a protocol.** Conversation id in a cookie; history and resolved context held in process memory; expired conversations evicted. Correct as long as one instance serves all requests.
3. **Server-side persistent store (Firestore or Redis).** Survives restarts and scales horizontally; costs setup time and another credential, for a property the evaluation does not need.

## Decision

Option 2. `ConversationStore` is a protocol with an `InMemoryConversationStore` implementation. Cloud Run is pinned to one instance during the evaluation window so the store is coherent. Each turn stores the full transcript (user message, assistant tool-use blocks, tool results, final assistant text); trimming drops whole turns so provider message pairing stays valid. The stored `ResolvedContext` (last geography ids and names, variable id, year) is derived from successful tool results and injected into the system prompt on subsequent turns. Prior-turn thinking blocks are stripped when building the LLM message list. Option 3 is the documented production swap, implementable behind the same protocol.

## Amendment (2026-09-19)

Full turn transcripts are stored, not text-only summaries, to satisfy CF-3 conversation context preservation without assuming which details a follow-up may reference. See the decision log entry on the CF-3 conundrum.

## Consequences

- A redeploy clears conversations; acceptable and stated in the README.
- Scaling beyond one instance requires implementing option 3 first; this is listed in the reflection as a production gap.
- Follow-up resolution is testable without an LLM by asserting on the rendered context block.
