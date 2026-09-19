from __future__ import annotations

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
        "DEMO_AUTH_ENABLED": True,
        "DEMO_PASSPHRASE": "correct-horse-battery",
        "AUTH_SIGNING_SECRET": "test-signing-secret-at-least-32-chars-long",
        "AUTH_COOKIE_NAME": "miniflake_auth",
        "SESSION_COOKIE_NAME": "miniflake_session",
        "LOG_FILE": "",
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
    store = InMemoryConversationStore(resolved_settings)
    classifier_llm = FakeLLM([_in_scope_classifier_response()] * 20)
    loop = AgentLoop(llm, registry, repository, resolved_settings)
    classifier = IntentClassifier(classifier_llm, resolved_settings)
    guardrails = GuardrailPipeline(resolved_settings, classifier)
    service = ConversationService(resolved_settings, store, loop, guardrails=guardrails)
    return AppContainer(
        settings=resolved_settings,
        repository=repository,
        llm=llm,
        classifier_llm=classifier_llm,
        registry=registry,
        store=store,
        service=service,
    )


def _client(container: AppContainer) -> TestClient:
    get_settings.cache_clear()
    return TestClient(create_app(container=container))


def _simple_answer_script() -> list[LLMResponse]:
    return [
        LLMResponse(
            content=[TextBlock(text="Texas population is available from ACS.")],
            stop_reason="end_turn",
            usage=Usage(),
        ),
    ]


def test_unauthenticated_chat_returns_401() -> None:
    llm = FakeLLM(_simple_answer_script())
    client = _client(_build_container(llm))
    response = client.post("/api/chat", json={"message": "What is the population of Texas?"})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["request_id"]


def test_wrong_passphrase_returns_401_no_cookie() -> None:
    llm = FakeLLM(_simple_answer_script())
    settings = _settings()
    client = _client(_build_container(llm, settings))
    response = client.post("/api/login", json={"passphrase": "wrong-passphrase"})
    assert response.status_code == 401
    assert settings.auth_cookie_name not in response.cookies


def test_correct_passphrase_sets_cookie_and_chat_succeeds() -> None:
    llm = FakeLLM(_simple_answer_script())
    settings = _settings()
    client = _client(_build_container(llm, settings))
    login = client.post("/api/login", json={"passphrase": "correct-horse-battery"})
    assert login.status_code == 200
    auth_cookie = login.cookies.get(settings.auth_cookie_name)
    assert auth_cookie
    chat = client.post(
        "/api/chat",
        json={"message": "What is the population of Texas?"},
        cookies={settings.auth_cookie_name: auth_cookie},
    )
    assert chat.status_code == 200
    assert chat.json()["outcome"] == "answer"


def test_tampered_cookie_returns_401() -> None:
    llm = FakeLLM(_simple_answer_script())
    settings = _settings()
    client = _client(_build_container(llm, settings))
    response = client.post(
        "/api/chat",
        json={"message": "What is the population of Texas?"},
        cookies={settings.auth_cookie_name: "tampered.token.value"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_health_and_index_stay_open() -> None:
    llm = FakeLLM(_simple_answer_script())
    client = _client(_build_container(llm))
    health = client.get("/api/health")
    assert health.status_code == 200
    index = client.get("/")
    assert index.status_code == 200


def test_conversations_reset_is_protected() -> None:
    llm = FakeLLM(_simple_answer_script())
    client = _client(_build_container(llm))
    response = client.post("/api/conversations/reset")
    assert response.status_code == 401


def test_session_endpoint_reports_auth_state() -> None:
    llm = FakeLLM(_simple_answer_script())
    settings = _settings()
    client = _client(_build_container(llm, settings))
    unauth = client.get("/api/session")
    assert unauth.status_code == 200
    assert unauth.json() == {"auth_required": True, "authenticated": False}
    login = client.post("/api/login", json={"passphrase": "correct-horse-battery"})
    auth_cookie = login.cookies.get(settings.auth_cookie_name)
    authed = client.get("/api/session", cookies={settings.auth_cookie_name: auth_cookie})
    assert authed.json() == {"auth_required": True, "authenticated": True}


def test_auth_disabled_allows_chat_without_login() -> None:
    llm = FakeLLM(_simple_answer_script())
    settings = _settings(DEMO_AUTH_ENABLED=False)
    client = _client(_build_container(llm, settings))
    response = client.post("/api/chat", json={"message": "What is the population of Texas?"})
    assert response.status_code == 200
    session = client.get("/api/session")
    assert session.json() == {"auth_required": False, "authenticated": True}
