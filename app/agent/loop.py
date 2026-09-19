from __future__ import annotations

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
from app.tools.results import Success, ToolError


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

    def run(self, messages: list[Message], deadline: float) -> AgentAnswer:
        system = build_system_prompt(self._registry, self._settings)
        tools = [
            ToolSchema(
                name=schema["name"],
                description=schema["description"],
                input_schema=schema["input_schema"],
            )
            for schema in self._registry.schemas()
        ]
        working_messages = list(messages)
        tool_traces: list[ToolCallTrace] = []
        provenance = []
        usage = Usage()
        stop_reason: Literal["end_turn", "timeout", "iteration_cap", "llm_error"] | None = None
        text_blocks: list[str] = []

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
            except LLMError:
                stop_reason = "llm_error"
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
                break

            if response.stop_reason in {"max_tokens", "other"}:
                stop_reason = "llm_error"
                break

            if response.stop_reason != "tool_use":
                stop_reason = "llm_error"
                break

            working_messages.append(Message(role="assistant", content=response.content))
            tool_result_blocks: list[ToolResultBlock] = []
            for block in response.content:
                if not isinstance(block, ToolUseBlock):
                    continue
                started = self._clock()
                result = self._registry.dispatch(block.name, block.input, self._repository)
                duration_ms = (self._clock() - started) * 1000
                kind = result_kind(result)
                tool_traces.append(
                    ToolCallTrace(
                        name=block.name,
                        input=dict(block.input),
                        result_kind=kind,
                        duration_ms=duration_ms,
                    )
                )
                if isinstance(result, Success):
                    provenance.extend(result.provenance)
                tool_result_blocks.append(
                    ToolResultBlock(
                        tool_use_id=block.id,
                        content=result.model_dump_json(),
                        is_error=isinstance(result, ToolError),
                    )
                )
            working_messages.append(Message(role="tool", content=tool_result_blocks))

        if stop_reason is None:
            stop_reason = "iteration_cap"

        return self._composer.compose(
            stop_reason=stop_reason,
            text_blocks=text_blocks,
            tool_traces=tool_traces,
            provenance=provenance,
            usage=usage,
        )
