# S3: Agent core

Status: see [roadmap.md](../roadmap.md). Estimate: 3 h. Depends on S2.

## Goal

A single-turn agent that, given a conversation history, decides which tools to call, calls them, and composes a grounded answer with provenance, within a wall-clock budget. Multi-turn storage and HTTP are S4; this stage produces a Python function and a CLI around it.

## Scope

1. `LLMClient` protocol with a provider-neutral message and tool-call model.
2. `AnthropicLLMClient` using the Messages API with strict tool schemas.
3. `FakeLLM` driven by a script of expected turns.
4. `AgentLoop` with iteration cap, wall-clock budget, and tool dispatch through `ToolRegistry`.
5. System prompt as a file under `app/agent/prompts/`.
6. `AnswerComposer` producing `AgentAnswer` (text, provenance, outcome class).
7. `scripts/chat_cli.py` for manual iteration.

## Out of scope

Intent classification and refusal templates (S5), conversation persistence (S4), streaming.

## LLM abstraction (`app/llm/`)

```python
@dataclass
class Message:
    role: Literal["user", "assistant", "tool"]
    content: list[ContentBlock]


ContentBlock = (
    TextBlock
    | ToolUseBlock(id, name, input)
    | ToolResultBlock(tool_use_id, content, is_error)
    | OpaqueBlock(provider_type, payload)
)


@dataclass
class LLMResponse:
    content: list[ContentBlock]
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "other"]
    usage: Usage


class LLMClient(Protocol):
    def complete(
        self, system: str, messages: list[Message], tools: list[ToolSchema], *, timeout_s: float
    ) -> LLMResponse: ...
```

`AnthropicLLMClient` maps these to the Messages API using the official `anthropic` Python SDK with `max_retries=0` so the agent loop owns the single retry. Tools are passed with `strict: true`; schemas are sanitized in the client (inline `$defs`/`$ref`, drop unsupported constraints such as `minimum`/`minItems` above 1, fold dropped constraints into field descriptions, force `additionalProperties: false` on every object) so strict mode accepts the registry's pydantic schemas. Model id, max tokens, effort and thinking mode come from configuration; `ANTHROPIC_API_KEY` is optional in `Settings` and enforced when constructing the client. `thinking` and `redacted_thinking` blocks from the API are stored as `OpaqueBlock` and echoed back verbatim on the next request within a tool-use turn. API errors are mapped to `LLMError(retryable: bool)`; a single retry is applied to retryable errors when the remaining budget allows.

`FakeLLM` takes a list of `LLMResponse` objects and returns them in order; it records every call (system, messages, tools) for assertions and raises if called more times than scripted.

## Agent loop (`app/agent/loop.py`)

Inputs: `messages` (history ending in a user turn), `registry`, `repository`, `llm`, `settings`, `deadline`.

Algorithm:

1. Build the system prompt from the prompt file plus a rendered summary of the available tools and the supported geography levels and topics from the catalog.
2. Loop up to `max_iterations`:
   - Compute the remaining time; if below the configured minimum per call, stop with outcome `timeout`.
   - Call the LLM.
   - If `stop_reason` is `end_turn`, hand the text blocks to the composer.
   - If `tool_use`, append the assistant content verbatim (including any `OpaqueBlock` thinking blocks), dispatch every tool call through the registry, append tool result blocks (serialized `ToolResult`), and continue.
   - If `max_tokens` or `other`, stop with outcome `llm_error`.
3. If the loop exhausts iterations, stop with outcome `iteration_cap`.

All tool results seen during the loop are collected for provenance regardless of how the loop ends.

## System prompt (`app/agent/prompts/system.md`)

States the agent's role and data source (SafeGraph US Open Census, ACS 5-year estimates at block group level). Lists supported geography levels: block group (native), and nation/state/county/place for **count** measures only (summed from block groups). States that median and rate measures (income, age, poverty rate, etc.) are answerable only at block group level; at state, county or place level the agent must explain why and offer a block-group reformulation or a count-based alternative.

Covers the grounding rule (every number must come from a tool result), how to handle each `ToolResult.kind`, the answer format (short answer first, figures with ACS vintage, note when a value is a SUM rollup), and the instruction to never estimate or extrapolate. The prompt is a file so it can be edited without touching code.

## Composer (`app/agent/composer.py`)

`AgentAnswer`:

- `text: str`
- `outcome: Literal["answer", "clarify", "unanswerable", "refuse", "error"]`
- `provenance: list[Provenance]`
- `tool_calls: list[ToolCallTrace]` (name, input, result kind, duration)
- `usage: Usage`

Composer rules:

- `end_turn` with text and at least one `Success` tool result: `answer`.
- `end_turn` with text and only `Ambiguous` results: `clarify`.
- `end_turn` with text and only `NotFound`, `PeriodUnavailable` or `UnsupportedRequest` results: `unanswerable`.
- `end_turn` with text and no tool calls at all: if the text contains no numeric tokens (capability or data-source questions, see eval items `M01`, `M02`), `answer` with empty provenance; otherwise `unanswerable`, and the text is replaced with a templated message explaining the agent could not ground the answer. This prevents the model from answering with figures from memory.
- `timeout`, `iteration_cap`, `llm_error`, or a `ToolError` as the last result: `error`, with a templated message that includes what was attempted (tool names and resolved geographies) so the user can rephrase.

Templated messages live in `app/agent/prompts/templates.yaml`.

## CLI (`scripts/chat_cli.py`)

Reads a question from arguments or stdin, runs the loop once with the real Snowflake repository and Anthropic client, prints the answer, the outcome, each tool call with its result kind, and the provenance. Used for manual iteration and as the live smoke test.

## Acceptance criteria

- Given a FakeLLM scripted to call `find_geography` then `get_value` then end the turn, when the loop runs, then the answer outcome is `answer`, the text is the model's text, and provenance contains both repository calls.
- Given a FakeLLM scripted to call `find_geography` for an ambiguous name and then end the turn with a question, then the outcome is `clarify`.
- Given a FakeLLM scripted to call `get_value` for a year that is not available and then end the turn, then the outcome is `unanswerable` and the text is the model's text.
- Given a FakeLLM that ends the turn immediately with a numeric answer and no tool calls, then the outcome is `unanswerable` and the text is the grounding template, not the model's text.
- Given a FakeLLM that ends the turn immediately with a non-numeric capability description and no tool calls, then the outcome is `answer` with empty provenance.
- Given a deadline in the past, then the loop makes no LLM call and the outcome is `error` with the timeout template.
- Given a FakeLLM that keeps requesting tools, then the loop stops after `max_iterations` with outcome `error`.
- Given a repository that raises, then the tool result passed back to the LLM is a `ToolError` block and, if the model ends the turn, the outcome is `error`.
- Given the Anthropic client with a stubbed HTTP transport, when the API returns a retryable error once, then the request is retried and succeeds; when it returns a non-retryable error, then `LLMError` is raised without retry.
- Given the system prompt file, when rendered, then it lists every tool in the registry and every supported geography level.
- Live (opt-in): given a state population lookup question, when the CLI runs, then the outcome is `answer` and provenance shows a `get_value` call.

## Tests to write first

1. `tests/unit/llm/test_messages.py`: content block serialization round-trips.
2. `tests/unit/llm/test_anthropic_client.py`: request mapping (strict tools, config values), response mapping, error mapping, retry behaviour with a stubbed transport.
3. `tests/unit/llm/test_fake_llm.py`: scripted responses, call recording, over-call error.
4. `tests/unit/agent/test_prompt.py`: rendering includes tools and levels; template file loads.
5. `tests/component/agent/test_loop.py`: every acceptance criterion above that uses FakeLLM and FakeCensusRepository.
6. `tests/unit/agent/test_composer.py`: outcome classification for each combination of stop reason and result kinds.
7. `tests/live/test_agent_live.py`: opt-in end-to-end lookup.

## Files

- `app/llm/__init__.py`, `types.py`, `client.py` (protocol), `anthropic_client.py`, `fake.py`, `errors.py`
- `app/agent/__init__.py`, `loop.py`, `composer.py`, `prompt.py`, `prompts/system.md`, `prompts/templates.yaml`
- `scripts/chat_cli.py`
- tests listed above

## Documentation updates at stage end

- `ARCHITECTURE.md`: agent loop and composer as implemented.
- `USER-GUIDE.md`: CLI usage.
- `docs/EXTENDING.md`: "swap the LLM" section.
- `CHANGELOG.md`, `docs/roadmap.md`, `docs/decision_log.md` for any prompt-engineering dead ends.
