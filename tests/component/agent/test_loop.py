from __future__ import annotations

import logging
import time
from typing import Any

from app.agent.loop import AgentLoop
from app.config import Settings
from app.data.errors import RepositoryError
from app.data.fake_repository import FakeCensusRepository
from app.llm.errors import LLMError
from app.llm.fake import FakeLLM
from app.llm.types import LLMResponse, Message, TextBlock, ToolUseBlock, Usage
from app.tools.registry import default_registry


def _settings(**overrides: Any) -> Settings:
    base = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        "AGENT_MAX_ITERATIONS": 8,
        "AGENT_MIN_SECONDS_PER_LLM_CALL": 5.0,
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def _loop(
    llm: FakeLLM,
    repository: FakeCensusRepository | None = None,
    settings: Settings | None = None,
    *,
    clock: Any = None,
) -> AgentLoop:
    resolved_settings = settings or _settings()
    return AgentLoop(
        llm,
        default_registry(resolved_settings),
        repository or FakeCensusRepository(settings=resolved_settings),
        resolved_settings,
        clock=clock or time.monotonic,
    )


def _user_message(text: str) -> list[Message]:
    return [Message(role="user", content=[TextBlock(text=text)])]


def test_happy_path_lookup_returns_answer_with_provenance() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[
                    ToolUseBlock(
                        id="toolu_geo",
                        name="find_geography",
                        input={"query": "Texas", "level": "State"},
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(input_tokens=1, output_tokens=1),
            ),
            LLMResponse(
                content=[
                    ToolUseBlock(
                        id="toolu_value",
                        name="get_value",
                        input={"field_id": "B01003e1", "geo_id": "48"},
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(input_tokens=1, output_tokens=1),
            ),
            LLMResponse(
                content=[TextBlock(text="Texas population is available from ACS.")],
                stop_reason="end_turn",
                usage=Usage(input_tokens=1, output_tokens=2),
            ),
        ]
    )
    answer = _loop(llm).run(
        _user_message("What is the population of Texas?"), deadline=time.monotonic() + 60
    )
    assert answer.outcome == "answer"
    assert answer.stop_reason == "end_turn"
    assert answer.text == "Texas population is available from ACS."
    assert answer.provenance
    assert {trace.name for trace in answer.tool_calls} == {"find_geography", "get_value"}


def test_ambiguous_geography_end_turn_is_clarify() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[
                    ToolUseBlock(
                        id="toolu_geo",
                        name="find_geography",
                        input={"query": "Orange County"},
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(),
            ),
            LLMResponse(
                content=[TextBlock(text="Which Orange County did you mean?")],
                stop_reason="end_turn",
                usage=Usage(),
            ),
        ]
    )
    answer = _loop(llm).run(
        _user_message("Median income in Orange County?"), deadline=time.monotonic() + 60
    )
    assert answer.outcome == "clarify"
    assert "Orange County" in answer.text


def test_period_unavailable_end_turn_is_unanswerable() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[
                    ToolUseBlock(
                        id="toolu_value",
                        name="get_value",
                        input={"field_id": "B01003e1", "geo_id": "48", "vintage": 1990},
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(),
            ),
            LLMResponse(
                content=[TextBlock(text="1990 is outside the available ACS vintages.")],
                stop_reason="end_turn",
                usage=Usage(),
            ),
        ]
    )
    answer = _loop(llm).run(
        _user_message("What was the population of Texas in 1990?"),
        deadline=time.monotonic() + 60,
    )
    assert answer.outcome == "unanswerable"
    assert answer.text == "1990 is outside the available ACS vintages."


def test_numeric_answer_without_tools_passes_through() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[TextBlock(text="The population of Texas is 30 million.")],
                stop_reason="end_turn",
                usage=Usage(),
            )
        ]
    )
    answer = _loop(llm).run(_user_message("Population of Texas?"), deadline=time.monotonic() + 60)
    assert answer.outcome == "answer"
    assert answer.text == "The population of Texas is 30 million."


def test_capability_answer_without_tools_is_answer_with_empty_provenance() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[
                    TextBlock(
                        text=(
                            "I answer US census questions using SafeGraph ACS 5-year "
                            "block-group data for 2019 and 2020, with count rollups "
                            "to state and county levels."
                        )
                    )
                ],
                stop_reason="end_turn",
                usage=Usage(),
            )
        ]
    )
    answer = _loop(llm).run(
        _user_message("What kind of questions can you answer?"), deadline=time.monotonic() + 60
    )
    assert answer.outcome == "answer"
    assert answer.provenance == []


def test_past_deadline_skips_llm_and_returns_timeout_error() -> None:
    llm = FakeLLM([])
    answer = _loop(llm).run(_user_message("Population of Texas?"), deadline=time.monotonic() - 1)
    assert answer.outcome == "error"
    assert answer.stop_reason == "timeout"
    assert "ran out of time" in answer.text.lower()
    assert llm.calls == []


def test_low_remaining_time_skips_further_tools_and_keeps_earlier_traces() -> None:
    times = [90.0, 92.0, 92.0, 96.0, 96.0]
    index = 0

    def clock() -> float:
        nonlocal index
        value = times[min(index, len(times) - 1)]
        index += 1
        return value

    llm = FakeLLM(
        [
            LLMResponse(
                content=[
                    ToolUseBlock(
                        id="toolu_geo_1",
                        name="find_geography",
                        input={"query": "Texas", "level": "State"},
                    ),
                    ToolUseBlock(
                        id="toolu_geo_2",
                        name="find_geography",
                        input={"query": "Nevada", "level": "State"},
                    ),
                ],
                stop_reason="tool_use",
                usage=Usage(),
            )
        ]
    )
    answer = _loop(llm, settings=_settings(AGENT_MIN_SECONDS_PER_LLM_CALL=5.0), clock=clock).run(
        _user_message("Population of Texas and Nevada?"),
        deadline=100.0,
    )
    assert answer.outcome == "error"
    assert answer.stop_reason == "timeout"
    assert [trace.name for trace in answer.tool_calls] == ["find_geography"]
    assert answer.tool_calls[0].input["query"] == "Texas"
    assert "find_geography" in answer.text
    assert len(llm.calls) == 1


def test_iteration_cap_returns_error() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[
                    ToolUseBlock(
                        id=f"toolu_{index}",
                        name="find_geography",
                        input={"query": "Texas"},
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(),
            )
            for index in range(5)
        ]
    )
    answer = _loop(llm, settings=_settings(AGENT_MAX_ITERATIONS=3)).run(
        _user_message("Population of Texas?"),
        deadline=time.monotonic() + 60,
    )
    assert answer.outcome == "error"
    assert answer.stop_reason == "iteration_cap"
    assert "maximum number of lookup steps" in answer.text.lower()
    assert len(llm.calls) == 3


def test_llm_error_logs_stop_reason(caplog: Any) -> None:
    llm = FakeLLM([LLMError("upstream timeout", retryable=True)])
    with caplog.at_level(logging.INFO, logger="app.agent.loop"):
        answer = _loop(llm).run(
            _user_message("Population of Texas?"), deadline=time.monotonic() + 60
        )
    assert answer.outcome == "error"
    assert answer.stop_reason == "llm_error"
    records = [record for record in caplog.records if record.name == "app.agent.loop"]
    assert any(getattr(record, "stop_reason", None) == "llm_error" for record in records)
    assert any(getattr(record, "retryable", None) is True for record in records)
    assert any("upstream timeout" in record.getMessage() for record in records)


def test_repository_error_surfaces_as_tool_error_and_error_outcome() -> None:
    class BrokenRepository(FakeCensusRepository):
        def get_observations(self, field_id: str, geo_ids: list[str], vintage: int | None):
            raise RepositoryError("database unavailable")

    llm = FakeLLM(
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
                content=[TextBlock(text="The lookup failed.")],
                stop_reason="end_turn",
                usage=Usage(),
            ),
        ]
    )
    answer = _loop(llm, repository=BrokenRepository(settings=_settings())).run(
        _user_message("Population of Texas?"),
        deadline=time.monotonic() + 60,
    )
    assert answer.tool_calls[-1].result_kind == "tool_error"
    assert answer.outcome == "error"


def test_happy_path_includes_transcript_with_tool_messages() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[
                    ToolUseBlock(
                        id="toolu_geo",
                        name="find_geography",
                        input={"query": "Texas", "level": "State"},
                    )
                ],
                stop_reason="tool_use",
                usage=Usage(),
            ),
            LLMResponse(
                content=[TextBlock(text="Texas is a state.")],
                stop_reason="end_turn",
                usage=Usage(),
            ),
        ]
    )
    answer = _loop(llm).run(_user_message("Tell me about Texas."), deadline=time.monotonic() + 60)
    assert len(answer.transcript) == 3
    assert answer.transcript[0].role == "assistant"
    assert isinstance(answer.transcript[0].content[0], ToolUseBlock)
    assert answer.transcript[1].role == "tool"
    assert answer.transcript[2].role == "assistant"
    assert isinstance(answer.transcript[2].content[0], TextBlock)


def test_success_trace_includes_data_payload() -> None:
    llm = FakeLLM(
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
                content=[TextBlock(text="Texas population is available from ACS.")],
                stop_reason="end_turn",
                usage=Usage(),
            ),
        ]
    )
    answer = _loop(llm).run(
        _user_message("What is the population of Texas?"), deadline=time.monotonic() + 60
    )
    value_trace = next(trace for trace in answer.tool_calls if trace.name == "get_value")
    assert value_trace.data is not None
    assert value_trace.data["field_id"] == "B01003e1"
    assert value_trace.data["geo_id"] == "48"


def test_context_facts_appear_in_system_prompt() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content=[TextBlock(text="Florida follows the same measure.")],
                stop_reason="end_turn",
                usage=Usage(),
            )
        ]
    )
    loop = _loop(llm)
    loop.run(
        _user_message("And in Florida?"),
        deadline=time.monotonic() + 60,
        context_facts=["Variable: Total Population (B01003e1)", "Geography: Texas (48)"],
    )
    system_prompt = llm.calls[0][0]
    assert "Recently discussed" in system_prompt
    assert "Total Population" in system_prompt
    assert "Texas" in system_prompt
