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
6. Follow-up resolution via stored context and full turn transcripts.

## Out of scope

Guardrail logic (S5), demo authentication (S6), persistence beyond process memory.

## Behaviour

- `Conversation`: `id`, `messages: list[Message]`, `context: ResolvedContext` (last geography ids and names, last variable id, last year and period), `created_at`, `updated_at`.
- Stored history is the full per-turn transcript: user message, assistant `tool_use` blocks, `tool_result` blocks, and final assistant text. Trimming drops whole turns from the front so `tool_use`/`tool_result` pairing stays valid for the provider.
- The service trims history to the configured window of turns before calling the agent and injects `ResolvedContext` into the system prompt as "recently discussed" facts, so "and in Florida?" reuses the last variable and "what about 2015?" reuses the last geography and variable.
- Prior-turn thinking blocks are stripped when building the LLM message list; storage keeps them.
- `ResolvedContext` is updated from `Success` tool results after each turn.
- Request contract: `{"message": str}`; response: `{"conversation_id", "text", "outcome", "provenance": [...], "tool_calls": [...], "latency_ms"}`.
- Errors: `{"error": {"code", "message", "request_id"}}` with codes `invalid_input`, `timeout`, `upstream_unavailable`, `internal`. Stack traces never reach the client; the request id is logged with the exception.
- The request timeout is the response budget minus a safety margin; on expiry the API returns 200 with `outcome: "error"` and the timeout template rather than a 5xx. The route enforces this with a hard outer timeout in a worker thread; a cancellation token prevents a late-finishing turn from overwriting newer state.
- Message length is capped by configuration; empty or over-long input returns `invalid_input`.

## S3 layer changes (spec gap)

- `ToolCallTrace` gains optional `data` from `Success` tool payloads for context extraction.
- `AgentAnswer` gains `transcript: list[Message]` holding messages produced in the turn.
- `AgentLoop.run` accepts `context_facts: list[str]` passed to `build_system_prompt`.
- `prompts/system.md` gains a "Recently discussed" section rendered from those facts.

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
3. `tests/unit/conversation/test_history.py`: window trimming and prior-turn thinking-block stripping.
4. `tests/component/agent/test_loop.py`: additions for `AgentAnswer.transcript`, trace `data`, and `context_facts` in the system prompt.
5. `tests/e2e/test_chat_api.py`: all acceptance criteria via `TestClient` with `FakeLLM` and `FakeCensusRepository` injected through the app factory.

## Files

- `app/conversation/__init__.py`, `store.py`, `memory_store.py`, `service.py`, `context.py`, `history.py`
- `app/api/chat.py`, `app/api/errors.py`, `app/api/deps.py`
- `app/main.py` wiring updates
- `app/agent/composer.py`, `app/agent/loop.py`, `app/agent/prompt.py`, `app/agent/prompts/system.md` (S3 signature changes above)

## Documentation updates at stage end

`ARCHITECTURE.md` (conversation and API rows), `USER-GUIDE.md` (API usage), `CHANGELOG.md`, `docs/roadmap.md`.
