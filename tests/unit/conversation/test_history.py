from __future__ import annotations

from app.conversation.history import history_for_llm
from app.llm.types import Message, OpaqueBlock, TextBlock, ToolResultBlock, ToolUseBlock


def _turn(user_text: str, tool_use_id: str) -> list[Message]:
    return [
        Message(role="user", content=[TextBlock(text=user_text)]),
        Message(
            role="assistant",
            content=[
                OpaqueBlock(
                    provider_type="thinking",
                    payload={"type": "thinking", "thinking": "h1"},
                ),
                ToolUseBlock(id=tool_use_id, name="find_geography", input={"query": user_text}),
            ],
        ),
        Message(
            role="tool",
            content=[ToolResultBlock(tool_use_id=tool_use_id, content='{"kind":"success"}')],
        ),
        Message(role="assistant", content=[TextBlock(text=f"Answer for {user_text}")]),
    ]


def test_history_for_llm_keeps_only_last_n_turns() -> None:
    messages: list[Message] = []
    messages.extend(_turn("turn one", "toolu_1"))
    messages.extend(_turn("turn two", "toolu_2"))
    messages.extend(_turn("turn three", "toolu_3"))
    trimmed = history_for_llm(messages, window_turns=2)
    user_texts = [
        block.text
        for message in trimmed
        if message.role == "user"
        for block in message.content
        if isinstance(block, TextBlock)
    ]
    assert user_texts == ["turn two", "turn three"]


def test_history_for_llm_strips_thinking_from_prior_turns() -> None:
    messages: list[Message] = []
    messages.extend(_turn("turn one", "toolu_1"))
    messages.extend(_turn("turn two", "toolu_2"))
    trimmed = history_for_llm(messages, window_turns=2)
    prior_assistant = trimmed[1]
    assert prior_assistant.role == "assistant"
    assert all(not isinstance(block, OpaqueBlock) for block in prior_assistant.content)
    current_assistant = trimmed[5]
    assert any(isinstance(block, OpaqueBlock) for block in current_assistant.content)
