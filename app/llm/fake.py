from __future__ import annotations

from app.llm.types import LLMResponse, Message, ToolSchema


class FakeLLM:
    def __init__(self, script: list[LLMResponse | Exception]) -> None:
        self._script = list(script)
        self._index = 0
        self.calls: list[tuple[str, list[Message], list[ToolSchema], float]] = []

    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSchema],
        *,
        timeout_s: float,
    ) -> LLMResponse:
        self.calls.append(
            (system, [message.model_copy(deep=True) for message in messages], tools, timeout_s)
        )
        if self._index >= len(self._script):
            raise RuntimeError("FakeLLM called more times than scripted")
        item = self._script[self._index]
        self._index += 1
        if isinstance(item, Exception):
            raise item
        return item
