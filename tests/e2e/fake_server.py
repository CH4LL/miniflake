"""Test server with FakeLLM and FakeCensusRepository for browser smoke tests."""

from __future__ import annotations

import argparse

import uvicorn

from app.agent.loop import AgentLoop
from app.api.deps import AppContainer
from app.config import Settings
from app.conversation.memory_store import InMemoryConversationStore
from app.conversation.service import ConversationService
from app.data.fake_repository import FakeCensusRepository
from app.guardrails.classifier import IntentClassifier
from app.guardrails.pipeline import GuardrailPipeline
from app.llm.fake import FakeLLM
from app.llm.types import LLMResponse, TextBlock, ToolUseBlock, Usage
from app.main import create_app
from app.tools.registry import default_registry


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


def _texas_then_florida_script() -> list[LLMResponse]:
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


def build_fake_container() -> AppContainer:
    settings = Settings(
        SNOWFLAKE_ACCOUNT="TEST",
        SNOWFLAKE_USER="TEST",
        SNOWFLAKE_ROLE="TEST",
        SNOWFLAKE_WAREHOUSE="TEST",
        SNOWFLAKE_DATABASE="TEST",
        SNOWFLAKE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        DEMO_AUTH_ENABLED=True,
        DEMO_PASSPHRASE="test-passphrase",
        AUTH_SIGNING_SECRET="test-signing-secret-at-least-32-chars-long",
        AUTH_COOKIE_NAME="miniflake_auth",
        SESSION_COOKIE_NAME="miniflake_session",
        LOG_FILE="",
        _env_file=None,
    )
    llm = FakeLLM(_texas_then_florida_script())
    repository = FakeCensusRepository(settings=settings)
    registry = default_registry(settings)
    store = InMemoryConversationStore(settings)
    classifier_llm = FakeLLM([_in_scope_classifier_response()] * 20)
    loop = AgentLoop(llm, registry, repository, settings)
    classifier = IntentClassifier(classifier_llm, settings)
    guardrails = GuardrailPipeline(settings, classifier)
    service = ConversationService(settings, store, loop, guardrails=guardrails)
    return AppContainer(
        settings=settings,
        repository=repository,
        llm=llm,
        classifier_llm=classifier_llm,
        registry=registry,
        store=store,
        service=service,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    app = create_app(container=build_fake_container())
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
