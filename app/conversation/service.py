from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.agent.composer import AgentAnswer
from app.agent.loop import AgentLoop
from app.config import Settings
from app.conversation.history import history_for_llm
from app.conversation.store import Conversation, ConversationStore
from app.guardrails.prechecks import check_sanity
from app.guardrails.types import GuardrailDecision
from app.llm.types import Message, TextBlock


class InvalidMessageError(ValueError):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class GuardrailHook(Protocol):
    def before_agent(
        self, conversation: Conversation, message: str
    ) -> GuardrailDecision | None: ...


@dataclass(frozen=True)
class ChatTurn:
    conversation_id: str
    answer: AgentAnswer
    latency_ms: float


class ConversationService:
    def __init__(
        self,
        settings: Settings,
        store: ConversationStore,
        loop: AgentLoop,
        *,
        guardrails: GuardrailHook | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._store = store
        self._loop = loop
        self._guardrails = guardrails
        self._clock = clock
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def handle_message(
        self,
        conversation_id: str | None,
        message: str,
        cancellation: CancellationToken | None = None,
    ) -> ChatTurn:
        normalized = message.strip()
        sanity_reason = check_sanity(normalized, self._settings.max_message_chars)
        if sanity_reason:
            raise InvalidMessageError(sanity_reason)

        conversation = self._load_or_create(conversation_id)
        lock = self._lock_for(conversation.id)
        started = self._clock()
        with lock:
            conversation = self._load_or_create(conversation.id)
            ungrounded_answer_allowed = False
            if self._guardrails is not None:
                guarded = self._guardrails.before_agent(conversation, normalized)
                if guarded is not None and guarded.short_circuits:
                    return self._short_circuit_turn(conversation, normalized, guarded, started)
                if guarded is not None:
                    ungrounded_answer_allowed = guarded.ungrounded_answer_allowed

            user_message = Message(role="user", content=[TextBlock(text=normalized)])
            conversation.messages.append(user_message)
            history = history_for_llm(
                conversation.messages,
                window_turns=self._settings.conversation_history_window_turns,
            )
            now = self._clock()
            remaining_api = self._settings.api_request_timeout_seconds - (now - started)
            deadline = now + self._settings.inner_deadline_seconds(remaining_api)
            answer = self._loop.run(
                history,
                deadline,
                context_facts=conversation.context.as_facts(),
                ungrounded_answer_allowed=ungrounded_answer_allowed,
            )
            latency_ms = (self._clock() - started) * 1000

            if cancellation is not None and cancellation.cancelled:
                return ChatTurn(
                    conversation_id=conversation.id,
                    answer=answer,
                    latency_ms=latency_ms,
                )

            conversation.messages.extend(answer.transcript)
            updated_context = conversation.context.model_copy(deep=True)
            updated_context.update_from_traces(answer.tool_calls)
            conversation.context = updated_context
            self._store.save(conversation)
            return ChatTurn(
                conversation_id=conversation.id,
                answer=answer,
                latency_ms=latency_ms,
            )

    def reset(self, conversation_id: str | None) -> str | None:
        if conversation_id:
            self._store.delete(conversation_id)
        fresh = self._store.create()
        return fresh.id

    def _short_circuit_turn(
        self,
        conversation: Conversation,
        message: str,
        decision: GuardrailDecision,
        started: float,
    ) -> ChatTurn:
        user_message = Message(role="user", content=[TextBlock(text=message)])
        assistant_message = Message(role="assistant", content=[TextBlock(text=decision.text)])
        conversation.messages.append(user_message)
        conversation.messages.append(assistant_message)
        self._store.save(conversation)
        answer = AgentAnswer(text=decision.text, outcome=decision.outcome)
        return ChatTurn(
            conversation_id=conversation.id,
            answer=answer,
            latency_ms=(self._clock() - started) * 1000,
        )

    def _load_or_create(self, conversation_id: str | None) -> Conversation:
        if conversation_id:
            existing = self._store.get(conversation_id)
            if existing is not None:
                return existing
        return self._store.create()

    def _lock_for(self, conversation_id: str) -> threading.Lock:
        with self._locks_guard:
            if conversation_id not in self._locks:
                self._locks[conversation_id] = threading.Lock()
            return self._locks[conversation_id]
