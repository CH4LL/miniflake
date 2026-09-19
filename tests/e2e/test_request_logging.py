from __future__ import annotations

import json
import logging
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
from app.logging import JsonFormatter
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
        "LOG_FORMAT": "json",
        "WARMUP_ENABLED": False,
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


def _build_container(llm: FakeLLM, settings: Settings | None = None) -> AppContainer:
    resolved_settings = settings or _settings()
    repository = FakeCensusRepository(settings=resolved_settings)
    registry = default_registry(resolved_settings)
    store = InMemoryConversationStore(resolved_settings, clock=time.monotonic)
    loop = AgentLoop(llm, registry, repository, resolved_settings, clock=time.monotonic)
    classifier_llm = FakeLLM([_in_scope_classifier_response()] * 20)
    classifier = IntentClassifier(classifier_llm, resolved_settings)
    guardrails = GuardrailPipeline(resolved_settings, classifier)
    service = ConversationService(
        resolved_settings,
        store,
        loop,
        guardrails=guardrails,
        clock=time.monotonic,
    )
    return AppContainer(
        settings=resolved_settings,
        repository=repository,
        llm=llm,
        classifier_llm=classifier_llm,
        registry=registry,
        store=store,
        service=service,
    )


def test_chat_turn_emits_structured_log() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[
                    ToolUseBlock(
                        id="toolu_geo_tx",
                        name="find_geography",
                        input={"query": "Texas", "level": "State"},
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(input_tokens=10, output_tokens=5),
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
                usage=Usage(input_tokens=12, output_tokens=6),
            ),
            LLMResponse(
                content=[TextBlock(text="Texas population is available from ACS.")],
                stop_reason="end_turn",
                usage=Usage(input_tokens=20, output_tokens=15),
            ),
        ]
    )
    settings = _settings()
    container = _build_container(llm, settings)
    get_settings.cache_clear()
    captured: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    chat_logger = logging.getLogger("app.api.chat")
    handler = CaptureHandler()
    chat_logger.addHandler(handler)
    formatter = JsonFormatter()

    client = TestClient(create_app(container))
    response = client.post("/api/chat", json={"message": "What is the population of Texas?"})
    assert response.status_code == 200

    turn_records = [
        json.loads(formatter.format(record))
        for record in captured
        if record.getMessage() == "chat turn completed"
    ]
    assert len(turn_records) == 1
    payload = turn_records[0]
    assert payload["request_id"]
    assert payload["outcome"] == "answer"
    assert payload["latency_ms"] >= 0
    assert any(call["name"] == "get_value" for call in payload["tool_calls"])
