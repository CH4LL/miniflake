from __future__ import annotations

import time
from typing import Any, Literal

import httpx2 as httpx
from anthropic import Anthropic, APIConnectionError, APIStatusError, APITimeoutError

from app.config import Settings
from app.llm.errors import LLMError
from app.llm.schema_sanitize import sanitize_schema_for_strict
from app.llm.types import (
    ContentBlock,
    LLMResponse,
    Message,
    OpaqueBlock,
    TextBlock,
    ToolResultBlock,
    ToolSchema,
    ToolUseBlock,
    Usage,
)


class AnthropicLLMClient:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
        model: str | None = None,
        thinking: str | None = None,
        forced_tool_name: str | None = None,
        use_effort: bool = True,
    ) -> None:
        if not settings.anthropic_api_key:
            raise ValueError("anthropic_api_key is required")
        self._settings = settings
        self._model = model or settings.anthropic_model
        self._thinking = thinking or settings.anthropic_thinking
        self._forced_tool_name = forced_tool_name
        self._use_effort = use_effort
        self._client = Anthropic(
            api_key=settings.anthropic_api_key,
            max_retries=0,
            http_client=http_client,
        )

    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSchema],
        *,
        timeout_s: float,
    ) -> LLMResponse:
        kwargs = self._build_request_kwargs(system, messages, tools, timeout_s)
        try:
            return self._call(kwargs)
        except LLMError as exc:
            if not exc.retryable or not self._settings.agent_llm_retry_enabled:
                raise
            time.sleep(0.1)
            return self._call(kwargs)

    def _call(self, kwargs: dict[str, Any]) -> LLMResponse:
        try:
            response = self._client.messages.create(**kwargs)
        except APIStatusError as exc:
            retryable = exc.status_code >= 500 or exc.status_code == 429
            raise LLMError(str(exc), retryable=retryable) from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise LLMError(str(exc), retryable=True) from exc
        return self._map_response(response)

    def _build_request_kwargs(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSchema],
        timeout_s: float,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._settings.anthropic_max_tokens,
            "system": system,
            "messages": self._map_messages(messages),
            "timeout": timeout_s,
        }
        thinking = self._thinking.strip().lower()
        if thinking == "disabled":
            kwargs["thinking"] = {"type": "disabled"}
        elif thinking == "adaptive":
            kwargs["thinking"] = {"type": "adaptive"}
        if self._use_effort:
            kwargs["output_config"] = {"effort": self._settings.anthropic_effort}
        if tools:
            kwargs["tools"] = [self._map_tool(tool) for tool in tools]
            if self._forced_tool_name:
                kwargs["tool_choice"] = {"type": "tool", "name": self._forced_tool_name}
        return kwargs

    def _map_tool(self, tool: ToolSchema) -> dict[str, Any]:
        sanitized = sanitize_schema_for_strict(tool.input_schema)
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": sanitized,
            "strict": True,
        }

    def _map_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        mapped: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "tool":
                mapped.append(
                    {
                        "role": "user",
                        "content": [self._map_content_block(block) for block in message.content],
                    }
                )
                continue
            mapped.append(
                {
                    "role": message.role,
                    "content": [self._map_content_block(block) for block in message.content],
                }
            )
        return mapped

    def _map_content_block(self, block: ContentBlock) -> dict[str, Any]:
        if isinstance(block, OpaqueBlock):
            return dict(block.payload)
        if isinstance(block, TextBlock):
            return {"type": "text", "text": block.text}
        if isinstance(block, ToolUseBlock):
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        if isinstance(block, ToolResultBlock):
            payload: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": block.tool_use_id,
                "content": block.content,
            }
            if block.is_error:
                payload["is_error"] = True
            return payload
        raise TypeError(f"Unsupported block type: {type(block)!r}")

    def _map_response(self, response: Any) -> LLMResponse:
        content = [self._map_response_block(block) for block in response.content]
        stop_reason = self._map_stop_reason(response.stop_reason)
        usage = Usage(
            input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
        )
        return LLMResponse(content=content, stop_reason=stop_reason, usage=usage)

    def _map_response_block(self, block: Any) -> ContentBlock:
        block_type = getattr(block, "type", None)
        if block_type in {"thinking", "redacted_thinking"}:
            payload = block.model_dump() if hasattr(block, "model_dump") else dict(block)
            return OpaqueBlock(provider_type=block_type, payload=payload)
        if block_type == "text":
            return TextBlock(text=block.text)
        if block_type == "tool_use":
            return ToolUseBlock(id=block.id, name=block.name, input=dict(block.input))
        raise TypeError(f"Unsupported response block type: {block_type!r}")

    @staticmethod
    def _map_stop_reason(
        stop_reason: str | None,
    ) -> Literal["end_turn", "tool_use", "max_tokens", "other"]:
        mapping = {
            "end_turn": "end_turn",
            "tool_use": "tool_use",
            "max_tokens": "max_tokens",
        }
        if stop_reason in mapping:
            return mapping[stop_reason]
        return "other"
