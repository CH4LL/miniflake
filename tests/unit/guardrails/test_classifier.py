from __future__ import annotations

from typing import Any

from app.config import Settings
from app.guardrails.classifier import IntentClassifier, render_context
from app.llm.errors import LLMError
from app.llm.fake import FakeLLM
from app.llm.types import LLMResponse, Message, TextBlock, ToolUseBlock, Usage


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
    confidence: float = 0.95,
    missing: str | None = None,
    reason: str = "test",
) -> LLMResponse:
    payload: dict[str, Any] = {
        "intent": intent,
        "reason": reason,
        "confidence": confidence,
        "missing": missing,
    }
    return LLMResponse(
        content=[
            ToolUseBlock(id="toolu_classify", name="classify_intent", input=payload),
        ],
        stop_reason="tool_use",
        usage=Usage(),
    )


def test_classify_parses_tool_use_block() -> None:
    llm = FakeLLM([_classifier_response("off_topic")])
    classifier = IntentClassifier(llm, _settings())
    decision = classifier.classify("Write me a poem.", context_excerpt="")
    assert decision.intent == "off_topic"
    assert decision.failed_open is False


def test_classify_parses_json_text_fallback() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[
                    TextBlock(
                        text='{"intent": "harmful", "reason": "discrimination", "confidence": 0.9}'
                    )
                ],
                stop_reason="end_turn",
                usage=Usage(),
            )
        ]
    )
    classifier = IntentClassifier(llm, _settings())
    decision = classifier.classify("Which neighbourhoods should I avoid?", context_excerpt="")
    assert decision.intent == "harmful"


def test_low_confidence_in_scope_downgraded_to_needs_clarification() -> None:
    llm = FakeLLM([_classifier_response("in_scope", confidence=0.4)])
    classifier = IntentClassifier(llm, _settings())
    decision = classifier.classify("Population of Washington?", context_excerpt="")
    assert decision.intent == "needs_clarification"


def test_classifier_fail_open_on_llm_error() -> None:
    llm = FakeLLM([LLMError("timeout", retryable=True)])
    classifier = IntentClassifier(llm, _settings())
    decision = classifier.classify("Population of Texas?", context_excerpt="")
    assert decision.intent == "in_scope"
    assert decision.failed_open is True


def test_classifier_fail_open_on_malformed_output() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[TextBlock(text="not json")],
                stop_reason="end_turn",
                usage=Usage(),
            )
        ]
    )
    classifier = IntentClassifier(llm, _settings())
    decision = classifier.classify("Population of Texas?", context_excerpt="")
    assert decision.intent == "in_scope"
    assert decision.failed_open is True


def test_render_context_is_plain_text_only() -> None:
    messages = [
        Message(role="user", content=[TextBlock(text="Population of Texas?")]),
        Message(
            role="assistant",
            content=[ToolUseBlock(id="t1", name="get_value", input={"field_id": "B01003e1"})],
        ),
    ]
    excerpt = render_context(messages, max_turns=2)
    assert "tool_use" not in excerpt
    assert "Population of Texas?" in excerpt
