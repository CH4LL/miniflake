from __future__ import annotations

import time
from typing import Any

from fastapi.testclient import TestClient

from app.agent.loop import AgentLoop
from app.api.deps import AppContainer
from app.config import Settings, get_settings
from app.conversation.memory_store import InMemoryConversationStore
from app.conversation.service import ConversationService
from app.data.fake_repository import FakeCensusRepository
from app.guardrails.classifier import IntentClassifier
from app.guardrails.pipeline import GuardrailPipeline
from app.llm.fake import FakeLLM
from app.llm.types import LLMResponse, TextBlock, ToolUseBlock, Usage
from app.main import create_app
from app.tools.registry import default_registry


def _settings(**overrides: Any) -> Settings:
    base = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        "RESPONSE_BUDGET_SECONDS": 60,
        "API_TIMEOUT_MARGIN_SECONDS": 2,
        "CONVERSATION_TTL_SECONDS": 3600,
        "SESSION_COOKIE_NAME": "miniflake_session",
        "DEMO_AUTH_ENABLED": False,
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def _in_scope_classifier_response() -> LLMResponse:
    return LLMResponse(
        content=[
            ToolUseBlock(
                id="toolu_classify",
                name="classify_intent",
                input={
                    "intent": "in_scope",
                    "reason": "test fixture",
                    "confidence": 0.95,
                    "missing": "none",
                },
            )
        ],
        stop_reason="tool_use",
        usage=Usage(),
    )


def _build_container(
    llm: FakeLLM,
    settings: Settings | None = None,
    *,
    clock: Any = None,
    classifier_llm: FakeLLM | None = None,
) -> AppContainer:
    resolved_settings = settings or _settings()
    repository = FakeCensusRepository(settings=resolved_settings)
    registry = default_registry(resolved_settings)
    store = InMemoryConversationStore(resolved_settings, clock=clock or time.monotonic)
    loop = AgentLoop(llm, registry, repository, resolved_settings, clock=clock or time.monotonic)
    resolved_classifier = classifier_llm or FakeLLM([_in_scope_classifier_response()] * 20)
    classifier = IntentClassifier(resolved_classifier, resolved_settings)
    guardrails = GuardrailPipeline(resolved_settings, classifier)
    service = ConversationService(
        resolved_settings,
        store,
        loop,
        guardrails=guardrails,
        clock=clock or time.monotonic,
    )
    return AppContainer(
        settings=resolved_settings,
        repository=repository,
        llm=llm,
        classifier_llm=resolved_classifier,
        registry=registry,
        store=store,
        service=service,
    )


def _client(container: AppContainer, *, raise_server_exceptions: bool = True) -> TestClient:
    get_settings.cache_clear()
    return TestClient(
        create_app(container=container),
        raise_server_exceptions=raise_server_exceptions,
    )


def _texas_then_florida_script() -> list[LLMResponse | Exception]:
    return [
        LLMResponse(
            content=[
                ToolUseBlock(
                    id="toolu_geo_tx",
                    name="find_geography",
                    input={"query": "Texas", "level": "State"},
                )
            ],
            stop_reason="tool_use",
            usage=Usage(),
        ),
        LLMResponse(
            content=[
                ToolUseBlock(
                    id="toolu_value_tx",
                    name="get_value",
                    input={"field_id": "B01003e1", "geo_id": "48"},
                )
            ],
            stop_reason="tool_use",
            usage=Usage(),
        ),
        LLMResponse(
            content=[TextBlock(text="Texas population is available from ACS.")],
            stop_reason="end_turn",
            usage=Usage(),
        ),
        LLMResponse(
            content=[
                ToolUseBlock(
                    id="toolu_geo_fl",
                    name="find_geography",
                    input={"query": "Florida", "level": "State"},
                )
            ],
            stop_reason="tool_use",
            usage=Usage(),
        ),
        LLMResponse(
            content=[
                ToolUseBlock(
                    id="toolu_value_fl",
                    name="get_value",
                    input={"field_id": "B01003e1", "geo_id": "12"},
                )
            ],
            stop_reason="tool_use",
            usage=Usage(),
        ),
        LLMResponse(
            content=[TextBlock(text="Florida population is available from ACS.")],
            stop_reason="end_turn",
            usage=Usage(),
        ),
    ]


def test_follow_up_reuses_prior_variable_in_system_prompt() -> None:
    llm = FakeLLM(_texas_then_florida_script())
    client = _client(_build_container(llm))

    first = client.post("/api/chat", json={"message": "What is the population of Texas?"})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["outcome"] == "answer"
    assert first_body["usage"]["input_tokens"] >= 0
    assert first_body["usage"]["output_tokens"] >= 0

    second = client.post("/api/chat", json={"message": "and in Florida?"})
    assert second.status_code == 200
    assert second.json()["outcome"] == "answer"
    assert len(llm.calls) == 6
    second_system = llm.calls[3][0]
    assert "Total Population" in second_system or "B01003e1" in second_system
    second_messages = llm.calls[3][1]
    assert any(
        block.type == "tool_result"
        for message in second_messages
        if message.role == "tool"
        for block in message.content
    )


def test_expired_conversation_starts_new_session() -> None:
    now = [1000.0]

    def clock() -> float:
        return now[0]

    llm = FakeLLM(
        [
            LLMResponse(
                content=[TextBlock(text="Hello.")],
                stop_reason="end_turn",
                usage=Usage(),
            ),
            LLMResponse(
                content=[TextBlock(text="Fresh start.")],
                stop_reason="end_turn",
                usage=Usage(),
            ),
        ]
    )
    settings = _settings(CONVERSATION_TTL_SECONDS=60)
    client = _client(_build_container(llm, settings, clock=clock))

    first = client.post("/api/chat", json={"message": "Hi"})
    assert first.status_code == 200
    first_id = first.json()["conversation_id"]
    cookie = first.cookies.get(settings.session_cookie_name)
    assert cookie

    now[0] += 120
    second = client.post(
        "/api/chat",
        json={"message": "Hi again"},
        cookies={settings.session_cookie_name: cookie},
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] != first_id


def test_empty_message_returns_invalid_input() -> None:
    llm = FakeLLM([])
    client = _client(_build_container(llm))
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "invalid_input"
    assert body["error"]["request_id"]


def test_unexpected_exception_returns_internal_error() -> None:
    class ExplodingLoop:
        def run(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("boom")

    llm = FakeLLM([])
    container = _build_container(llm)
    container.service._loop = ExplodingLoop()  # noqa: SLF001
    client = _client(container, raise_server_exceptions=False)
    response = client.post("/api/chat", json={"message": "Population of Texas?"})
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal"
    assert body["error"]["request_id"]
    assert "boom" not in body["error"]["message"]


def test_request_timeout_returns_error_outcome() -> None:
    class SlowLLM:
        def complete(self, *args: Any, **kwargs: Any) -> LLMResponse:
            time.sleep(0.5)
            return LLMResponse(
                content=[TextBlock(text="late")],
                stop_reason="end_turn",
                usage=Usage(),
            )

    settings = _settings(
        RESPONSE_BUDGET_SECONDS=0.2,
        API_TIMEOUT_MARGIN_SECONDS=0.05,
        AGENT_MIN_SECONDS_PER_LLM_CALL=0.01,
    )
    repository = FakeCensusRepository(settings=settings)
    registry = default_registry(settings)
    store = InMemoryConversationStore(settings)
    loop = AgentLoop(SlowLLM(), registry, repository, settings)
    classifier = IntentClassifier(FakeLLM([_in_scope_classifier_response()]), settings)
    guardrails = GuardrailPipeline(settings, classifier)
    service = ConversationService(settings, store, loop, guardrails=guardrails)
    container = AppContainer(
        settings=settings,
        repository=repository,
        llm=SlowLLM(),
        classifier_llm=FakeLLM([_in_scope_classifier_response()]),
        registry=registry,
        store=store,
        service=service,
    )
    client = _client(container)
    response = client.post("/api/chat", json={"message": "Population of Texas?"})
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "error"
    assert "ran out of time" in body["text"].lower()


def test_reset_starts_fresh_history() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[TextBlock(text="First answer.")],
                stop_reason="end_turn",
                usage=Usage(),
            ),
            LLMResponse(
                content=[TextBlock(text="Second answer.")],
                stop_reason="end_turn",
                usage=Usage(),
            ),
        ]
    )
    client = _client(_build_container(llm))
    first = client.post("/api/chat", json={"message": "Population of Texas?"})
    cookie = first.cookies.get("miniflake_session")
    reset = client.post("/api/conversations/reset", cookies={"miniflake_session": cookie})
    assert reset.status_code == 200
    fresh_cookie = reset.cookies.get("miniflake_session")
    second = client.post(
        "/api/chat",
        json={"message": "Population of Texas?"},
        cookies={"miniflake_session": fresh_cookie},
    )
    assert second.status_code == 200
    assert len(llm.calls[1][1]) == 1
