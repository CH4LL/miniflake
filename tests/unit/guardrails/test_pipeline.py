from __future__ import annotations

from typing import Any

from app.config import Settings
from app.conversation.store import Conversation
from app.guardrails.classifier import IntentClassifier
from app.guardrails.pipeline import GuardrailPipeline, load_templates
from app.llm.fake import FakeLLM
from app.llm.types import LLMResponse, ToolUseBlock, Usage


def _settings(**overrides: Any) -> Settings:
    base = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        "GUARDRAIL_CLASSIFIER_CONFIDENCE_THRESHOLD": 0.7,
        "GUARDRAIL_CLASSIFIER_CONTEXT_TURNS": 2,
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def _classifier_response(
    intent: str,
    *,
    missing: str = "none",
    confidence: float = 0.95,
) -> LLMResponse:
    return LLMResponse(
        content=[
            ToolUseBlock(
                id="toolu_classify",
                name="classify_intent",
                input={
                    "intent": intent,
                    "reason": "test",
                    "confidence": confidence,
                    "missing": missing,
                },
            )
        ],
        stop_reason="tool_use",
        usage=Usage(),
    )


def _pipeline(response: LLMResponse) -> GuardrailPipeline:
    classifier = IntentClassifier(FakeLLM([response]), _settings())
    return GuardrailPipeline(_settings(), classifier)


def test_missing_vintage_does_not_short_circuit() -> None:
    pipeline = _pipeline(
        _classifier_response("needs_clarification", missing="vintage"),
    )
    decision = pipeline.before_agent(Conversation(), "What is the population of Oregon?")
    assert decision is None


def test_geography_clarify_still_short_circuits() -> None:
    pipeline = _pipeline(
        _classifier_response("needs_clarification", missing="geography"),
    )
    decision = pipeline.before_agent(Conversation(), "Compare the population.")
    templates = load_templates()
    assert decision is not None
    assert decision.outcome == "clarify"
    assert decision.text == templates["needs_clarification_geography"]


def test_measure_clarify_still_short_circuits() -> None:
    pipeline = _pipeline(
        _classifier_response("needs_clarification", missing="measure"),
    )
    decision = pipeline.before_agent(Conversation(), "What is the income in Ohio?")
    templates = load_templates()
    assert decision is not None
    assert decision.outcome == "clarify"
    assert decision.text == templates["needs_clarification_measure"]
    assert "total population" not in decision.text.lower()


def test_population_phrasing_does_not_clarify_measure() -> None:
    pipeline = _pipeline(
        _classifier_response("needs_clarification", missing="measure"),
    )
    decision = pipeline.before_agent(Conversation(), "What is the population of Oregon?")
    assert decision is None


def test_how_many_people_does_not_clarify_measure() -> None:
    pipeline = _pipeline(
        _classifier_response("needs_clarification", missing="measure"),
    )
    decision = pipeline.before_agent(Conversation(), "How many people live in Texas?")
    assert decision is None


def test_capability_intent_proceeds_with_ungrounded_answer_allowed() -> None:
    pipeline = _pipeline(_classifier_response("capability"))
    decision = pipeline.before_agent(Conversation(), "What kind of questions can you answer?")
    assert decision is not None
    assert decision.outcome == "proceed"
    assert decision.ungrounded_answer_allowed is True


def test_in_scope_intent_returns_none() -> None:
    pipeline = _pipeline(_classifier_response("in_scope"))
    decision = pipeline.before_agent(Conversation(), "What is the population of Texas?")
    assert decision is None


def test_populous_does_not_clarify_measure() -> None:
    pipeline = _pipeline(
        _classifier_response("needs_clarification", missing="measure"),
    )
    decision = pipeline.before_agent(Conversation(), "What are the five most populous states?")
    assert decision is None
