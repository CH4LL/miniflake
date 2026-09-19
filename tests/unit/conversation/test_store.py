from __future__ import annotations

from datetime import UTC, datetime

from app.config import Settings
from app.conversation.memory_store import InMemoryConversationStore
from app.llm.types import Message, TextBlock, ToolResultBlock, ToolUseBlock


def _settings(**overrides: object) -> Settings:
    base = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        "CONVERSATION_TTL_SECONDS": 60,
        "CONVERSATION_MAX_TURNS": 2,
        "CONVERSATION_MAX_CONVERSATIONS": 2,
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def _user_message(text: str) -> Message:
    return Message(role="user", content=[TextBlock(text=text)])


def _tool_turn(user_text: str, tool_use_id: str) -> list[Message]:
    return [
        _user_message(user_text),
        Message(
            role="assistant",
            content=[
                ToolUseBlock(id=tool_use_id, name="find_geography", input={"query": user_text})
            ],
        ),
        Message(
            role="tool",
            content=[ToolResultBlock(tool_use_id=tool_use_id, content='{"kind":"success"}')],
        ),
        Message(role="assistant", content=[TextBlock(text=f"Answer for {user_text}")]),
    ]


def test_get_returns_none_for_expired_conversation() -> None:
    now = datetime(2026, 9, 19, 12, 0, 0, tzinfo=UTC)
    store = InMemoryConversationStore(_settings(), clock=lambda: now.timestamp())
    conversation = store.create()
    store.save(conversation)
    later = datetime(2026, 9, 19, 12, 2, 0, tzinfo=UTC)
    store._clock = lambda: later.timestamp()  # noqa: SLF001
    assert store.get(conversation.id) is None


def test_save_trims_whole_turns_when_over_max_turns() -> None:
    store = InMemoryConversationStore(_settings(CONVERSATION_MAX_TURNS=2))
    conversation = store.create()
    conversation.messages.extend(_tool_turn("turn one", "toolu_1"))
    conversation.messages.extend(_tool_turn("turn two", "toolu_2"))
    conversation.messages.extend(_tool_turn("turn three", "toolu_3"))
    store.save(conversation)
    saved = store.get(conversation.id)
    assert saved is not None
    user_texts = [
        block.text
        for message in saved.messages
        if message.role == "user"
        for block in message.content
        if isinstance(block, TextBlock)
    ]
    assert user_texts == ["turn two", "turn three"]
    tool_use_ids = [
        block.id
        for message in saved.messages
        if message.role == "assistant"
        for block in message.content
        if isinstance(block, ToolUseBlock)
    ]
    assert tool_use_ids == ["toolu_2", "toolu_3"]


def test_delete_removes_conversation() -> None:
    store = InMemoryConversationStore(_settings())
    conversation = store.create()
    store.save(conversation)
    store.delete(conversation.id)
    assert store.get(conversation.id) is None


def test_create_evicts_least_recently_updated_when_at_capacity() -> None:
    store = InMemoryConversationStore(_settings(CONVERSATION_MAX_CONVERSATIONS=2))
    first = store.create()
    store.save(first)
    second = store.create()
    store.save(second)
    third = store.create()
    store.save(third)
    assert store.get(first.id) is None
    assert store.get(second.id) is not None
    assert store.get(third.id) is not None
