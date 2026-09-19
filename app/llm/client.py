from __future__ import annotations

from typing import Protocol

from app.llm.types import LLMResponse, Message, ToolSchema


class LLMClient(Protocol):
    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSchema],
        *,
        timeout_s: float,
    ) -> LLMResponse: ...
