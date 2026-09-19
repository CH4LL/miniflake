from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

from app.agent.loop import AgentLoop
from app.api.deps import AppContainer
from app.config import Settings
from app.conversation.memory_store import InMemoryConversationStore
from app.conversation.service import ConversationService
from app.data.fake_repository import FakeCensusRepository
from app.data.repository import CensusRepository
from app.guardrails.classifier import IntentClassifier
from app.guardrails.pipeline import GuardrailPipeline
from app.llm.errors import LLMError
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
        "SESSION_COOKIE_NAME": "miniflake_session",
        "DEMO_AUTH_ENABLED": False,
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


class RecordingRepository:
    def __init__(self, inner: CensusRepository) -> None:
        self._inner = inner
        self.call_count = 0

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.call_count += 1
            return attr(*args, **kwargs)

        return wrapper


def _load_eval_items(expected: str) -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parents[2] / "evals" / "questions.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        item
        for item in raw["items"]
        if item.get("status", "active") == "active" and item.get("expected") == expected
    ]


def _classifier_response(intent: str, missing: str = "none") -> LLMResponse:
    return LLMResponse(
        content=[
            ToolUseBlock(
                id="toolu_classify",
                name="classify_intent",
                input={
                    "intent": intent,
                    "reason": "test fixture",
                    "confidence": 0.95,
                    "missing": missing,
                },
            )
        ],
        stop_reason="tool_use",
        usage=Usage(),
    )


def _refuse_classifier_response(item: dict[str, Any]) -> LLMResponse:
    if item["category"] == "harmful":
        return _classifier_response("harmful")
    return _classifier_response("off_topic")


def _build_container(
    classifier_llm: FakeLLM,
    agent_llm: FakeLLM,
    repository: RecordingRepository,
    settings: Settings | None = None,
) -> AppContainer:
    resolved_settings = settings or _settings()
    registry = default_registry(resolved_settings)
    store = InMemoryConversationStore(resolved_settings)
    loop = AgentLoop(agent_llm, registry, repository, resolved_settings)
    classifier = IntentClassifier(classifier_llm, resolved_settings)
    guardrails = GuardrailPipeline(resolved_settings, classifier)
    service = ConversationService(resolved_settings, store, loop, guardrails=guardrails)
    return AppContainer(
        settings=resolved_settings,
        repository=repository,
        llm=agent_llm,
        classifier_llm=classifier_llm,
        registry=registry,
        store=store,
        service=service,
    )


def _client(container: AppContainer) -> TestClient:
    return TestClient(create_app(container=container))


def test_refuse_eval_items_block_data_access() -> None:
    refuse_items = _load_eval_items("refuse")
    for item in refuse_items:
        classifier_llm = FakeLLM([_refuse_classifier_response(item)])
        agent_llm = FakeLLM(
            [
                LLMResponse(
                    content=[TextBlock(text="should not run")],
                    stop_reason="end_turn",
                    usage=Usage(),
                )
            ]
        )
        repository = RecordingRepository(FakeCensusRepository(settings=_settings()))
        client = _client(_build_container(classifier_llm, agent_llm, repository))
        response = client.post("/api/chat", json={"message": item["question"]})
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "refuse"
        assert repository.call_count == 0


def test_injection_refuse_does_not_call_classifier() -> None:
    injection_items = [
        item for item in _load_eval_items("refuse") if item["category"] == "injection"
    ]
    for item in injection_items:
        classifier_llm = FakeLLM([])
        agent_llm = FakeLLM([])
        repository = RecordingRepository(FakeCensusRepository(settings=_settings()))
        client = _client(_build_container(classifier_llm, agent_llm, repository))
        response = client.post("/api/chat", json={"message": item["question"]})
        assert response.status_code == 200
        assert response.json()["outcome"] == "refuse"
        assert classifier_llm.calls == []


def test_geography_clarify_skips_agent_loop() -> None:
    classifier_llm = FakeLLM([_classifier_response("needs_clarification", missing="geography")])
    agent_llm = FakeLLM(
        [
            LLMResponse(
                content=[TextBlock(text="should not run")],
                stop_reason="end_turn",
                usage=Usage(),
            )
        ]
    )
    repository = RecordingRepository(FakeCensusRepository(settings=_settings()))
    client = _client(_build_container(classifier_llm, agent_llm, repository))
    response = client.post("/api/chat", json={"message": "Compare the population."})
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "clarify"
    assert "geography" in body["text"].lower()
    assert agent_llm.calls == []


def test_vintage_clarify_does_not_short_circuit() -> None:
    classifier_llm = FakeLLM([_classifier_response("needs_clarification", missing="vintage")])
    agent_llm = FakeLLM(
        [
            LLMResponse(
                content=[TextBlock(text="Oregon population is available from ACS.")],
                stop_reason="end_turn",
                usage=Usage(),
            )
        ]
    )
    repository = RecordingRepository(FakeCensusRepository(settings=_settings()))
    client = _client(_build_container(classifier_llm, agent_llm, repository))
    response = client.post("/api/chat", json={"message": "What is the population of Oregon?"})
    assert response.status_code == 200
    assert response.json()["outcome"] == "answer"
    assert len(agent_llm.calls) == 1


def test_classifier_timeout_fails_open_to_agent_loop() -> None:
    classifier_llm = FakeLLM([LLMError("timeout", retryable=True)])
    agent_llm = FakeLLM(
        [
            LLMResponse(
                content=[TextBlock(text="Texas has census data.")],
                stop_reason="end_turn",
                usage=Usage(),
            )
        ]
    )
    repository = RecordingRepository(FakeCensusRepository(settings=_settings()))
    client = _client(_build_container(classifier_llm, agent_llm, repository))
    response = client.post("/api/chat", json={"message": "What is the population of Texas?"})
    assert response.status_code == 200
    assert response.json()["outcome"] == "answer"
    assert len(agent_llm.calls) == 1


def test_ungrounded_answer_becomes_unanswerable_with_provenance() -> None:
    classifier_llm = FakeLLM(
        [
            LLMResponse(
                content=[
                    ToolUseBlock(
                        id="toolu_classify",
                        name="classify_intent",
                        input={
                            "intent": "in_scope",
                            "reason": "lookup",
                            "confidence": 0.95,
                            "missing": "none",
                        },
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(),
            )
        ]
    )
    agent_llm = FakeLLM(
        [
            LLMResponse(
                content=[
                    ToolUseBlock(
                        id="toolu_value",
                        name="get_value",
                        input={"field_id": "B01003e1", "geo_id": "48"},
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(),
            ),
            LLMResponse(
                content=[TextBlock(text="Texas has 99,999,999 people.")],
                stop_reason="end_turn",
                usage=Usage(),
            ),
        ]
    )
    repository = RecordingRepository(FakeCensusRepository(settings=_settings()))
    client = _client(_build_container(classifier_llm, agent_llm, repository))
    response = client.post("/api/chat", json={"message": "What is the population of Texas?"})
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "unanswerable"
    assert "could not verify" in body["text"].lower()
    assert body["provenance"]
