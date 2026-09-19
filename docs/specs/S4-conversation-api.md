# S4: Conversation and API

Status: see [roadmap.md](../roadmap.md). Estimate: 2 h. Depends on S3.

## Goal

Expose the agent over HTTP with server-side conversation memory so follow-up questions resolve against earlier turns.

## Scope

1. `ConversationStore` protocol and `InMemoryConversationStore` with TTL and a maximum turn count per conversation.
2. `ConversationService` orchestrating load, guardrails hook (no-op until S5), agent loop, save.
3. `POST /api/chat` and `POST /api/conversations/reset`.
4. Anonymous session cookie identifying the conversation.
5. Uniform error envelope and request-level timeout.
6. Follow-up resolution via stored context.

## Out of scope

Guardrail logic (S5), demo authentication (S6), persistence beyond process memory.

## Behaviour

- `Conversation`: `id`, `messages: list[Message]`, `context: ResolvedContext` (last geography ids and names, last variable id, last year and period), `created_at`, `updated_at`.
- The service trims history to the configured window of turns before calling the agent and injects `ResolvedContext` into the system prompt as "recently discussed" facts, so "and in Florida?" reuses the last variable and "what about 2015?" reuses the last geography and variable.
- `ResolvedContext` is updated from `Success` tool results after each turn.
- Request contract: `{"message": str}`; response: `{"conversation_id", "text", "outcome", "provenance": [...], "tool_calls": [...], "latency_ms"}`.
- Errors: `{"error": {"code", "message", "request_id"}}` with codes `invalid_input`, `timeout`, `upstream_unavailable`, `internal`. Stack traces never reach the client; the request id is logged with the exception.
- The request timeout is the response budget minus a safety margin; on expiry the API returns `outcome: "error"` with the timeout template rather than a 5xx, because a degraded answer is the specified behaviour.
- Message length is capped by configuration; empty or over-long input returns `invalid_input`.

## Acceptance criteria

- Given a first message that resolves a state and a variable, when a second message says "and in Florida?", then the agent's system prompt contains the prior variable in its context block and the answer outcome is `answer` (with FakeLLM scripted accordingly).
- Given a conversation older than the TTL, when a message arrives, then a new conversation is started and the response carries a new id.
- Given an empty message, then the response is 400 with code `invalid_input`.
- Given the agent raises an unexpected exception, then the response is 500 with code `internal`, a request id, and no exception text.
- Given the agent exceeds the request budget, then the response is 200 with outcome `error` and the timeout text.
- Given `POST /api/conversations/reset`, then subsequent messages start a fresh history.

## Tests to write first

1. `tests/unit/conversation/test_store.py`: TTL expiry, max turns trimming, reset.
2. `tests/unit/conversation/test_context.py`: `ResolvedContext` updates from tool results; prompt rendering.
3. `tests/e2e/test_chat_api.py`: all acceptance criteria via `TestClient` with `FakeLLM` and `FakeCensusRepository` injected through the app factory.

## Files

- `app/conversation/__init__.py`, `store.py`, `memory_store.py`, `service.py`, `context.py`
- `app/api/chat.py`, `app/api/errors.py`, `app/api/deps.py`
- `app/main.py` wiring updates

## Documentation updates at stage end

`ARCHITECTURE.md` (conversation and API rows), `USER-GUIDE.md` (API usage), `CHANGELOG.md`, `docs/roadmap.md`.
