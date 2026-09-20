from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Literal

from app.agent.composer import AgentAnswer, AnswerComposer, ToolCallTrace, result_kind
from app.agent.prompt import build_system_prompt
from app.config import Settings
from app.data.repository import CensusRepository
from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.llm.types import Message, TextBlock, ToolResultBlock, ToolSchema, ToolUseBlock, Usage
from app.tools.registry import ToolRegistry
from app.tools.results import Success, ToolError, ToolResult, UnsupportedRequest

logger = logging.getLogger(__name__)

SEARCH_TOOL_NAMES = frozenset({"find_variable", "find_geography"})


def search_budget_exhausted(max_search_calls: int) -> UnsupportedRequest:
    return UnsupportedRequest(
        reason=(
            f"Search budget of {max_search_calls} catalog searches for this turn is used up. "
            "Do not search again. Explain what could not be found in the catalog and suggest "
            "how the user could rephrase, or answer with the data already retrieved."
        )
    )


class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        repository: CensusRepository,
        settings: Settings,
        *,
        clock: Callable[[], float] = time.monotonic,
        composer: AnswerComposer | None = None,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._repository = repository
        self._settings = settings
        self._clock = clock
        self._composer = composer or AnswerComposer()

    def run(
        self,
        messages: list[Message],
        deadline: float,
        *,
        context_facts: list[str] | None = None,
        ungrounded_answer_allowed: bool = False,
    ) -> AgentAnswer:
        system = build_system_prompt(
            self._registry,
            self._settings,
            context_facts=context_facts or [],
        )
        tools = [
            ToolSchema(
                name=schema["name"],
                description=schema["description"],
                input_schema=schema["input_schema"],
            )
            for schema in self._registry.schemas()
        ]
        working_messages = list(messages)
        transcript: list[Message] = []
        tool_traces: list[ToolCallTrace] = []
        provenance = []
        usage = Usage()
        stop_reason: Literal["end_turn", "timeout", "iteration_cap", "llm_error"] | None = None
        text_blocks: list[str] = []
        search_calls = 0

        for _ in range(self._settings.agent_max_iterations):
            remaining = deadline - self._clock()
            if remaining < self._settings.agent_min_seconds_per_llm_call:
                stop_reason = "timeout"
                break

            try:
                response = self._llm.complete(
                    system,
                    working_messages,
                    tools,
                    timeout_s=remaining,
                )
            except LLMError as exc:
                stop_reason = "llm_error"
                logger.warning(
                    "agent llm error: %s",
                    exc,
                    extra={"stop_reason": "llm_error", "retryable": exc.retryable},
                )
                break

            usage = Usage(
                input_tokens=usage.input_tokens + response.usage.input_tokens,
                output_tokens=usage.output_tokens + response.usage.output_tokens,
            )

            if response.stop_reason == "end_turn":
                stop_reason = "end_turn"
                text_blocks = [
                    block.text for block in response.content if isinstance(block, TextBlock)
                ]
                final_message = Message(role="assistant", content=response.content)
                working_messages.append(final_message)
                transcript.append(final_message)
                break

            if response.stop_reason in {"max_tokens", "other"}:
                stop_reason = "llm_error"
                break

            if response.stop_reason != "tool_use":
                stop_reason = "llm_error"
                break

            assistant_message = Message(role="assistant", content=response.content)
            working_messages.append(assistant_message)
            transcript.append(assistant_message)
            tool_result_blocks: list[ToolResultBlock] = []
            timed_out = False
            for block in response.content:
                if not isinstance(block, ToolUseBlock):
                    continue
                remaining = deadline - self._clock()
                if remaining < self._settings.agent_min_seconds_per_llm_call:
                    stop_reason = "timeout"
                    timed_out = True
                    break
                started = self._clock()
                result: ToolResult
                if block.name in SEARCH_TOOL_NAMES:
                    search_calls += 1
                    if search_calls > self._settings.agent_max_search_calls:
                        result = search_budget_exhausted(self._settings.agent_max_search_calls)
                        logger.info(
                            "search budget exhausted",
                            extra={"tool_name": block.name, "search_calls": search_calls},
                        )
                    else:
                        result = self._registry.dispatch(block.name, block.input, self._repository)
                else:
                    result = self._registry.dispatch(block.name, block.input, self._repository)
                duration_ms = (self._clock() - started) * 1000
                kind = result_kind(result)
                trace_data = None
                if isinstance(result, Success):
                    provenance.extend(result.provenance)
                    trace_data = result.data.model_dump(mode="json")
                tool_traces.append(
                    ToolCallTrace(
                        name=block.name,
                        input=dict(block.input),
                        result_kind=kind,
                        duration_ms=duration_ms,
                        data=trace_data,
                    )
                )
                tool_result_blocks.append(
                    ToolResultBlock(
                        tool_use_id=block.id,
                        content=result.model_dump_json(),
                        is_error=isinstance(result, ToolError),
                    )
                )
            if tool_result_blocks:
                tool_message = Message(role="tool", content=tool_result_blocks)
                working_messages.append(tool_message)
                transcript.append(tool_message)
            if timed_out:
                break

        if stop_reason is None:
            stop_reason = "iteration_cap"

        if stop_reason != "end_turn":
            logger.info(
                "agent stopped",
                extra={
                    "stop_reason": stop_reason,
                    "tool_names": [trace.name for trace in tool_traces],
                },
            )

        answer = self._composer.compose(
            stop_reason=stop_reason,
            text_blocks=text_blocks,
            tool_traces=tool_traces,
            provenance=provenance,
            usage=usage,
            ungrounded_answer_allowed=ungrounded_answer_allowed,
        )
        answer.transcript = transcript
        return answer
