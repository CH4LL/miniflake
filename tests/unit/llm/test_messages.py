import json

from app.llm.types import (
    LLMResponse,
    Message,
    OpaqueBlock,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    Usage,
    content_block_from_dict,
    content_block_to_dict,
    message_from_dict,
    message_to_dict,
)


def test_text_block_round_trip() -> None:
    block = TextBlock(text="hello")
    restored = content_block_from_dict(content_block_to_dict(block))
    assert restored == block


def test_tool_use_block_round_trip() -> None:
    block = ToolUseBlock(id="toolu_1", name="get_value", input={"field_id": "B01003e1"})
    restored = content_block_from_dict(content_block_to_dict(block))
    assert restored == block


def test_tool_result_block_round_trip() -> None:
    block = ToolResultBlock(
        tool_use_id="toolu_1",
        content='{"kind": "success"}',
        is_error=False,
    )
    restored = content_block_from_dict(content_block_to_dict(block))
    assert restored == block


def test_opaque_block_round_trip_preserves_payload() -> None:
    payload = {
        "type": "thinking",
        "thinking": "",
        "signature": "sig_abc123",
    }
    block = OpaqueBlock(provider_type="thinking", payload=payload)
    encoded = content_block_to_dict(block)
    restored = content_block_from_dict(encoded)
    assert restored == block
    assert json.dumps(restored.payload, sort_keys=True) == json.dumps(payload, sort_keys=True)


def test_message_round_trip_with_mixed_blocks() -> None:
    message = Message(
        role="assistant",
        content=[
            OpaqueBlock(
                provider_type="thinking",
                payload={"type": "thinking", "thinking": "plan", "signature": "sig"},
            ),
            ToolUseBlock(id="toolu_1", name="find_geography", input={"query": "Texas"}),
            TextBlock(text="Looking up Texas."),
        ],
    )
    restored = message_from_dict(message_to_dict(message))
    assert restored == message


def test_tool_role_message_round_trip() -> None:
    message = Message(
        role="tool",
        content=[
            ToolResultBlock(
                tool_use_id="toolu_1",
                content='{"kind": "success", "data": {}}',
            )
        ],
    )
    restored = message_from_dict(message_to_dict(message))
    assert restored == message


def test_llm_response_round_trip() -> None:
    response = LLMResponse(
        content=[TextBlock(text="Done.")],
        stop_reason="end_turn",
        usage=Usage(input_tokens=12, output_tokens=4),
    )
    payload = response.model_dump()
    restored = LLMResponse.model_validate(payload)
    assert restored == response
