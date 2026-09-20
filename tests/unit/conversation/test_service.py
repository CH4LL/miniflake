from __future__ import annotations

from typing import Any

from app.agent.composer import AgentAnswer
from app.config import Settings
from app.conversation.memory_store import InMemoryConversationStore
from app.conversation.service import ConversationService
from app.conversation.store import Conversation
from app.guardrails.types import GuardrailDecision
from app.llm.types import Message


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class RecordingLoop:
    def __init__(self) -> None:
        self.deadline: float | None = None
        self.messages: list[Message] | None = None
        self.ungrounded_answer_allowed: bool | None = None

    def run(
        self,
        messages: list[Message],
        deadline: float,
        *,
        context_facts: list[str] | None = None,
        ungrounded_answer_allowed: bool = False,
    ) -> AgentAnswer:
        self.messages = messages
        self.deadline = deadline
        self.ungrounded_answer_allowed = ungrounded_answer_allowed
        return AgentAnswer(text="ok", outcome="answer")


class ProceedGuardrails:
    def __init__(self, decision: GuardrailDecision | None) -> None:
        self._decision = decision

    def before_agent(self, conversation: Conversation, message: str) -> GuardrailDecision | None:
        return self._decision


class SlowPassThroughGuardrails:
    def __init__(self, clock: FakeClock, delay_seconds: float) -> None:
        self._clock = clock
        self._delay_seconds = delay_seconds

    def before_agent(self, conversation: Conversation, message: str) -> GuardrailDecision | None:
        self._clock.advance(self._delay_seconds)
        return None


def _settings(**overrides: object) -> Settings:
    base: dict[str, Any] = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def _service(
    settings: Settings,
    clock: FakeClock,
    loop: RecordingLoop,
    *,
    classifier_delay: float,
) -> ConversationService:
    return ConversationService(
        settings,
        InMemoryConversationStore(settings),
        loop,  # type: ignore[arg-type]
        guardrails=SlowPassThroughGuardrails(clock, classifier_delay),
        clock=clock,
    )


def test_proceed_decision_forwards_ungrounded_flag_to_loop() -> None:
    settings = _settings()
    loop = RecordingLoop()
    service = ConversationService(
        settings,
        InMemoryConversationStore(settings),
        loop,  # type: ignore[arg-type]
        guardrails=ProceedGuardrails(
            GuardrailDecision(outcome="proceed", text="", ungrounded_answer_allowed=True)
        ),
        clock=FakeClock(),
    )
    turn = service.handle_message(None, "What kind of questions can you answer?")
    assert loop.ungrounded_answer_allowed is True
    assert turn.answer.outcome == "answer"


def test_none_decision_runs_loop_grounded() -> None:
    settings = _settings()
    loop = RecordingLoop()
    service = ConversationService(
        settings,
        InMemoryConversationStore(settings),
        loop,  # type: ignore[arg-type]
        guardrails=ProceedGuardrails(None),
        clock=FakeClock(),
    )
    service.handle_message(None, "What is the population of Texas?")
    assert loop.ungrounded_answer_allowed is False


def test_deadline_is_computed_after_guardrails_from_remaining_api_time() -> None:
    settings = _settings()
    clock = FakeClock()
    loop = RecordingLoop()
    started = clock.now
    classifier_delay = 5.0
    service = _service(settings, clock, loop, classifier_delay=classifier_delay)
    service.handle_message(None, "What is the population of Texas?")
    remaining_api = settings.api_request_timeout_seconds - classifier_delay
    assert loop.deadline == started + classifier_delay + settings.inner_deadline_seconds(
        remaining_api
    )


def test_explicit_agent_budget_still_caps_inner_deadline() -> None:
    settings = _settings(AGENT_BUDGET_SECONDS=45)
    clock = FakeClock()
    loop = RecordingLoop()
    started = clock.now
    service = _service(settings, clock, loop, classifier_delay=0.0)
    service.handle_message(None, "What is the population of Texas?")
    remaining_api = settings.api_request_timeout_seconds
    assert settings.inner_deadline_seconds(remaining_api) == 45.0
    assert loop.deadline == started + 45.0
