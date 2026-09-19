from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from app.conversation.context import ResolvedContext
from app.llm.types import Message


class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    messages: list[Message] = Field(default_factory=list)
    context: ResolvedContext = Field(default_factory=ResolvedContext)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConversationStore(Protocol):
    def get(self, conversation_id: str) -> Conversation | None: ...

    def create(self) -> Conversation: ...

    def save(self, conversation: Conversation) -> None: ...

    def delete(self, conversation_id: str) -> None: ...
