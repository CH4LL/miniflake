from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.config import Settings
from app.conversation.store import Conversation
from app.llm.types import Message


def split_turns(messages: list[Message]) -> list[list[Message]]:
    turns: list[list[Message]] = []
    current: list[Message] = []
    for message in messages:
        if message.role == "user" and current:
            turns.append(current)
            current = [message]
        else:
            current.append(message)
    if current:
        turns.append(current)
    return turns


def trim_turns(messages: list[Message], max_turns: int) -> list[Message]:
    turns = split_turns(messages)
    if len(turns) <= max_turns:
        return list(messages)
    trimmed_turns = turns[-max_turns:]
    flattened: list[Message] = []
    for turn in trimmed_turns:
        flattened.extend(turn)
    return flattened


class InMemoryConversationStore:
    def __init__(
        self,
        settings: Settings,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._settings = settings
        self._clock = clock or datetime.now(UTC).timestamp
        self._conversations: dict[str, Conversation] = {}

    def get(self, conversation_id: str) -> Conversation | None:
        self._purge_expired()
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            return None
        if self._is_expired(conversation):
            del self._conversations[conversation_id]
            return None
        return conversation.model_copy(deep=True)

    def create(self) -> Conversation:
        self._purge_expired()
        self._evict_if_needed()
        now = self._now()
        conversation = Conversation(created_at=now, updated_at=now)
        self._conversations[conversation.id] = conversation
        return conversation.model_copy(deep=True)

    def save(self, conversation: Conversation) -> None:
        self._purge_expired()
        trimmed_messages = trim_turns(
            conversation.messages,
            self._settings.conversation_max_turns,
        )
        now = self._now()
        stored = conversation.model_copy(deep=True)
        stored.messages = trimmed_messages
        stored.updated_at = now
        if stored.created_at is None:
            stored.created_at = now
        self._conversations[stored.id] = stored
        self._evict_if_needed()

    def delete(self, conversation_id: str) -> None:
        self._conversations.pop(conversation_id, None)

    def _now(self) -> datetime:
        return datetime.fromtimestamp(self._clock(), tz=UTC)

    def _is_expired(self, conversation: Conversation) -> bool:
        if conversation.updated_at is None:
            return False
        age_seconds = self._clock() - conversation.updated_at.timestamp()
        return age_seconds > self._settings.conversation_ttl_seconds

    def _purge_expired(self) -> None:
        expired_ids = [
            conversation_id
            for conversation_id, conversation in self._conversations.items()
            if self._is_expired(conversation)
        ]
        for conversation_id in expired_ids:
            del self._conversations[conversation_id]

    def _evict_if_needed(self) -> None:
        limit = self._settings.conversation_max_conversations
        overflow = len(self._conversations) - limit
        if overflow <= 0:
            return
        ordered = sorted(
            self._conversations.items(),
            key=lambda item: (
                item[1].updated_at or item[1].created_at or datetime.min.replace(tzinfo=UTC)
            ),
        )
        for conversation_id, _ in ordered[:overflow]:
            del self._conversations[conversation_id]
