from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


class OpaqueBlock(BaseModel):
    type: Literal["opaque"] = "opaque"
    provider_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


ContentBlock = Annotated[
    TextBlock | ToolUseBlock | ToolResultBlock | OpaqueBlock,
    Field(discriminator="type"),
]


class Message(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: list[ContentBlock]


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class LLMResponse(BaseModel):
    content: list[ContentBlock]
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "other"]
    usage: Usage


class ToolSchema(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


def content_block_to_dict(block: ContentBlock) -> dict[str, Any]:
    if isinstance(block, OpaqueBlock):
        return dict(block.payload)
    return block.model_dump()


def content_block_from_dict(data: dict[str, Any]) -> ContentBlock:
    block_type = data.get("type")
    if block_type in {"thinking", "redacted_thinking"}:
        return OpaqueBlock(provider_type=block_type, payload=dict(data))
    if block_type == "text":
        return TextBlock.model_validate(data)
    if block_type == "tool_use":
        return ToolUseBlock.model_validate(data)
    if block_type == "tool_result":
        return ToolResultBlock.model_validate(data)
    if block_type == "opaque":
        return OpaqueBlock.model_validate(data)
    raise ValueError(f"Unsupported content block type: {block_type!r}")


def message_to_dict(message: Message) -> dict[str, Any]:
    return {
        "role": message.role,
        "content": [content_block_to_dict(block) for block in message.content],
    }


def message_from_dict(data: dict[str, Any]) -> Message:
    content = [content_block_from_dict(item) for item in data["content"]]
    return Message(role=data["role"], content=content)
