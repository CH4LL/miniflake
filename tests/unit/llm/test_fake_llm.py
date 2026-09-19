import pytest

from app.llm.errors import LLMError
from app.llm.fake import FakeLLM
from app.llm.types import LLMResponse, Message, TextBlock, ToolSchema, Usage


def test_fake_llm_returns_scripted_responses_in_order() -> None:
    first = LLMResponse(
        content=[TextBlock(text="first")],
        stop_reason="end_turn",
        usage=Usage(),
    )
    second = LLMResponse(
        content=[TextBlock(text="second")],
        stop_reason="end_turn",
        usage=Usage(),
    )
    llm = FakeLLM([first, second])
    assert llm.complete("system", [], [], timeout_s=10.0) == first
    assert llm.complete("system", [], [], timeout_s=10.0) == second


def test_fake_llm_records_calls() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[TextBlock(text="ok")],
                stop_reason="end_turn",
                usage=Usage(),
            )
        ]
    )
    messages = [Message(role="user", content=[TextBlock(text="hello")])]
    tools = [ToolSchema(name="get_value", description="lookup", input_schema={"type": "object"})]
    llm.complete("system prompt", messages, tools, timeout_s=12.5)
    assert len(llm.calls) == 1
    system, recorded_messages, recorded_tools, timeout = llm.calls[0]
    assert system == "system prompt"
    assert recorded_messages == messages
    assert recorded_tools == tools
    assert timeout == 12.5


def test_fake_llm_raises_when_over_called() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[TextBlock(text="ok")],
                stop_reason="end_turn",
                usage=Usage(),
            )
        ]
    )
    llm.complete("system", [], [], timeout_s=1.0)
    with pytest.raises(RuntimeError, match="more times than scripted"):
        llm.complete("system", [], [], timeout_s=1.0)


def test_fake_llm_can_raise_scripted_exception() -> None:
    llm = FakeLLM([LLMError("boom", retryable=True)])
    with pytest.raises(LLMError, match="boom"):
        llm.complete("system", [], [], timeout_s=1.0)
