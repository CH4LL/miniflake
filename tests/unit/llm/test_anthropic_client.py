import json
from typing import Any

import httpx2 as httpx
import pytest

from app.config import Settings
from app.llm.anthropic_client import AnthropicLLMClient
from app.llm.errors import LLMError
from app.llm.types import (
    Message,
    OpaqueBlock,
    TextBlock,
    ToolResultBlock,
    ToolSchema,
    ToolUseBlock,
)
from app.tools.registry import default_registry


def _settings(**overrides: Any) -> Settings:
    base = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        "ANTHROPIC_API_KEY": "test-key",
        "ANTHROPIC_MODEL": "claude-sonnet-5",
        "ANTHROPIC_MAX_TOKENS": 2048,
        "ANTHROPIC_EFFORT": "medium",
        "ANTHROPIC_THINKING": "adaptive",
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def _success_response(**overrides: Any) -> dict[str, Any]:
    payload = {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "Hello"}],
        "model": "claude-sonnet-5",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    payload.update(overrides)
    return payload


def test_missing_api_key_raises_at_construction() -> None:
    with pytest.raises(ValueError, match="anthropic_api_key"):
        AnthropicLLMClient(_settings(ANTHROPIC_API_KEY=None))


def test_request_mapping_uses_config_and_strict_tools() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_success_response())

    transport = httpx.MockTransport(handler)
    client = AnthropicLLMClient(_settings(), http_client=httpx.Client(transport=transport))
    tools = [
        ToolSchema(
            name="get_value",
            description="lookup",
            input_schema={"type": "object", "properties": {"field_id": {"type": "string"}}},
        )
    ]
    client.complete(
        "system prompt",
        [Message(role="user", content=[TextBlock(text="Hi")])],
        tools,
        timeout_s=25.0,
    )
    body = json.loads(captured[0].content)
    assert body["model"] == "claude-sonnet-5"
    assert body["max_tokens"] == 2048
    assert body["system"] == "system prompt"
    assert body["output_config"] == {"effort": "medium"}
    assert body["thinking"] == {"type": "adaptive"}
    assert body["tools"][0]["strict"] is True
    assert body["tools"][0]["input_schema"]["additionalProperties"] is False


def test_rank_and_compare_schemas_are_sanitized_for_strict_mode() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_success_response())

    transport = httpx.MockTransport(handler)
    client = AnthropicLLMClient(_settings(), http_client=httpx.Client(transport=transport))
    registry = default_registry(_settings())
    tools = [
        ToolSchema(
            name=schema["name"],
            description=schema["description"],
            input_schema=schema["input_schema"],
        )
        for schema in registry.schemas()
        if schema["name"] in {"rank_geographies", "compare"}
    ]
    client.complete("system", [], tools, timeout_s=10.0)
    body = json.loads(captured[0].content)
    by_name = {tool["name"]: tool["input_schema"] for tool in body["tools"]}
    rank_schema = by_name["rank_geographies"]
    compare_schema = by_name["compare"]
    assert '"minimum":' not in json.dumps(rank_schema)
    assert '"minItems": 2' not in json.dumps(compare_schema)
    assert rank_schema["additionalProperties"] is False
    assert compare_schema["additionalProperties"] is False


def test_response_mapping_includes_opaque_thinking_blocks() -> None:
    thinking_payload = {
        "type": "thinking",
        "thinking": "",
        "signature": "sig_test_123",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_success_response(
                content=[
                    thinking_payload,
                    {"type": "tool_use", "id": "toolu_1", "name": "get_value", "input": {}},
                ],
                stop_reason="tool_use",
            ),
        )

    transport = httpx.MockTransport(handler)
    client = AnthropicLLMClient(_settings(), http_client=httpx.Client(transport=transport))
    response = client.complete("system", [], [], timeout_s=10.0)
    assert isinstance(response.content[0], OpaqueBlock)
    assert response.content[0].payload == thinking_payload
    assert isinstance(response.content[1], ToolUseBlock)
    assert response.stop_reason == "tool_use"


def test_thinking_blocks_are_echoed_verbatim_on_follow_up_request() -> None:
    thinking_payload = {
        "type": "thinking",
        "thinking": "",
        "signature": "sig_preserve_me",
    }
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if len(captured) == 1:
            return httpx.Response(
                200,
                json=_success_response(
                    content=[
                        thinking_payload,
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": "get_value",
                            "input": {"field_id": "B01003e1"},
                        },
                    ],
                    stop_reason="tool_use",
                ),
            )
        return httpx.Response(200, json=_success_response())

    transport = httpx.MockTransport(handler)
    client = AnthropicLLMClient(_settings(), http_client=httpx.Client(transport=transport))
    first = client.complete("system", [], [], timeout_s=10.0)
    messages = [
        Message(role="assistant", content=first.content),
        Message(
            role="tool",
            content=[
                ToolResultBlock(
                    tool_use_id="toolu_1",
                    content='{"kind": "success"}',
                )
            ],
        ),
    ]
    client.complete("system", messages, [], timeout_s=10.0)
    body = json.loads(captured[1].content)
    assistant_blocks = body["messages"][0]["content"]
    assert assistant_blocks[0] == thinking_payload


def test_retryable_error_is_retried_once() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"type": "error", "error": {"type": "rate_limit"}})
        return httpx.Response(200, json=_success_response())

    transport = httpx.MockTransport(handler)
    client = AnthropicLLMClient(_settings(), http_client=httpx.Client(transport=transport))
    response = client.complete("system", [], [], timeout_s=30.0)
    assert attempts == 2
    assert response.content[0].text == "Hello"


def test_classifier_client_can_omit_effort() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_success_response())

    transport = httpx.MockTransport(handler)
    client = AnthropicLLMClient(
        _settings(),
        http_client=httpx.Client(transport=transport),
        model="claude-haiku-4-5",
        use_effort=False,
    )
    client.complete("system", [], [], timeout_s=5.0)
    body = json.loads(captured[0].content)
    assert "output_config" not in body


def test_constructor_overrides_model_thinking_and_tool_choice() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_success_response())

    transport = httpx.MockTransport(handler)
    client = AnthropicLLMClient(
        _settings(ANTHROPIC_MODEL="claude-sonnet-5"),
        http_client=httpx.Client(transport=transport),
        model="claude-haiku-4-5",
        thinking="disabled",
        forced_tool_name="classify_intent",
    )
    tools = [
        ToolSchema(
            name="classify_intent",
            description="classify",
            input_schema={"type": "object", "properties": {}},
        )
    ]
    client.complete("system", [], tools, timeout_s=5.0)
    body = json.loads(captured[0].content)
    assert body["model"] == "claude-haiku-4-5"
    assert body["thinking"] == {"type": "disabled"}
    assert body["tool_choice"] == {"type": "tool", "name": "classify_intent"}


def test_non_retryable_error_raises_without_retry() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, json={"type": "error", "error": {"type": "invalid_request"}})

    transport = httpx.MockTransport(handler)
    client = AnthropicLLMClient(_settings(), http_client=httpx.Client(transport=transport))
    with pytest.raises(LLMError) as exc_info:
        client.complete("system", [], [], timeout_s=30.0)
    assert exc_info.value.retryable is False
    assert attempts == 1
