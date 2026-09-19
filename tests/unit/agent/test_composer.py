from datetime import UTC, datetime

from app.agent.composer import AnswerComposer, ToolCallTrace, contains_numeric_token
from app.data.models import AggregationMethod, Provenance
from app.llm.types import Usage


def _composer() -> AnswerComposer:
    return AnswerComposer(
        {
            "ungrounded_numeric": "grounding template",
            "timeout": "timeout template: {{ attempted }}",
            "iteration_cap": "iteration template: {{ attempted }}",
            "llm_error": "llm template: {{ attempted }}",
            "tool_error": "tool template: {{ attempted }}",
        }
    )


def test_end_turn_with_success_is_answer() -> None:
    answer = _composer().compose(
        stop_reason="end_turn",
        text_blocks=["Texas population is 29 million."],
        tool_traces=[
            ToolCallTrace(
                name="get_value", input={"geo_id": "48"}, result_kind="success", duration_ms=1.0
            )
        ],
        provenance=[
            Provenance(
                sql="fake",
                row_count=1,
                source="fake",
                executed_at=datetime.now(UTC),
                duration_ms=0.0,
                aggregation_method=AggregationMethod.SUM,
            )
        ],
        usage=Usage(input_tokens=1, output_tokens=2),
    )
    assert answer.outcome == "answer"
    assert answer.text == "Texas population is 29 million."


def test_end_turn_with_only_ambiguous_is_clarify() -> None:
    answer = _composer().compose(
        stop_reason="end_turn",
        text_blocks=["Which Washington did you mean?"],
        tool_traces=[
            ToolCallTrace(
                name="find_geography",
                input={"query": "Washington"},
                result_kind="ambiguous",
                duration_ms=1.0,
            )
        ],
        provenance=[],
        usage=Usage(),
    )
    assert answer.outcome == "clarify"


def test_catalog_success_with_unsupported_get_value_is_unanswerable() -> None:
    answer = _composer().compose(
        stop_reason="end_turn",
        text_blocks=["Median income is not available at county level."],
        tool_traces=[
            ToolCallTrace(
                name="find_geography",
                input={"query": "Cook County"},
                result_kind="success",
                duration_ms=1.0,
            ),
            ToolCallTrace(
                name="find_variable",
                input={"query": "median household income"},
                result_kind="success",
                duration_ms=1.0,
            ),
            ToolCallTrace(
                name="get_value",
                input={"field_id": "B19013e1", "geo_id": "17031"},
                result_kind="unsupported_request",
                duration_ms=1.0,
            ),
        ],
        provenance=[],
        usage=Usage(),
    )
    assert answer.outcome == "unanswerable"


def test_catalog_only_success_without_data_fetch_is_unanswerable() -> None:
    answer = _composer().compose(
        stop_reason="end_turn",
        text_blocks=["Median income cannot be ranked at county level."],
        tool_traces=[
            ToolCallTrace(
                name="find_variable",
                input={"query": "median household income"},
                result_kind="success",
                duration_ms=1.0,
            )
        ],
        provenance=[],
        usage=Usage(),
    )
    assert answer.outcome == "unanswerable"


def test_end_turn_with_only_unavailable_is_unanswerable() -> None:
    answer = _composer().compose(
        stop_reason="end_turn",
        text_blocks=["1990 is not available."],
        tool_traces=[
            ToolCallTrace(
                name="get_value",
                input={"vintage": 1990},
                result_kind="period_unavailable",
                duration_ms=1.0,
            )
        ],
        provenance=[],
        usage=Usage(),
    )
    assert answer.outcome == "unanswerable"


def test_end_turn_without_tools_and_limitation_text_is_unanswerable() -> None:
    answer = _composer().compose(
        stop_reason="end_turn",
        text_blocks=["CBSA geography isn't supported in this dataset."],
        tool_traces=[],
        provenance=[],
        usage=Usage(),
    )
    assert answer.outcome == "unanswerable"


def test_end_turn_without_tools_and_without_numbers_is_answer() -> None:
    answer = _composer().compose(
        stop_reason="end_turn",
        text_blocks=["I answer US census questions from SafeGraph ACS block-group data."],
        tool_traces=[],
        provenance=[],
        usage=Usage(),
    )
    assert answer.outcome == "answer"
    assert answer.provenance == []


def test_end_turn_without_tools_and_with_numbers_uses_grounding_template() -> None:
    answer = _composer().compose(
        stop_reason="end_turn",
        text_blocks=["The population is 30 million."],
        tool_traces=[],
        provenance=[],
        usage=Usage(),
    )
    assert answer.outcome == "unanswerable"
    assert answer.text == "grounding template"


def test_end_turn_without_tools_allows_years_and_five_year_label() -> None:
    answer = _composer().compose(
        stop_reason="end_turn",
        text_blocks=["Values are ACS 5-year estimates for 2019 and 2020."],
        tool_traces=[],
        provenance=[],
        usage=Usage(),
    )
    assert answer.outcome == "answer"
    assert "2019" in answer.text


def test_end_turn_without_tools_limitation_text_stays_unanswerable() -> None:
    answer = _composer().compose(
        stop_reason="end_turn",
        text_blocks=["Median income at county level is not supported in this dataset."],
        tool_traces=[],
        provenance=[],
        usage=Usage(),
    )
    assert answer.outcome == "unanswerable"


def test_timeout_iteration_and_llm_error_use_error_templates() -> None:
    traces = [
        ToolCallTrace(
            name="find_geography", input={"query": "Texas"}, result_kind="success", duration_ms=1.0
        )
    ]
    timeout = _composer().compose(
        stop_reason="timeout",
        text_blocks=[],
        tool_traces=traces,
        provenance=[],
        usage=Usage(),
    )
    iteration = _composer().compose(
        stop_reason="iteration_cap",
        text_blocks=[],
        tool_traces=traces,
        provenance=[],
        usage=Usage(),
    )
    llm_error = _composer().compose(
        stop_reason="llm_error",
        text_blocks=[],
        tool_traces=traces,
        provenance=[],
        usage=Usage(),
    )
    assert timeout.outcome == "error"
    assert "timeout template" in timeout.text
    assert iteration.outcome == "error"
    assert "iteration template" in iteration.text
    assert llm_error.outcome == "error"
    assert "llm template" in llm_error.text


def test_tool_error_as_last_result_is_error() -> None:
    answer = _composer().compose(
        stop_reason="end_turn",
        text_blocks=["I could not finish."],
        tool_traces=[
            ToolCallTrace(
                name="get_value", input={"geo_id": "48"}, result_kind="tool_error", duration_ms=1.0
            )
        ],
        provenance=[],
        usage=Usage(),
    )
    assert answer.outcome == "error"
    assert "tool template" in answer.text


def test_contains_numeric_token() -> None:
    assert contains_numeric_token("about 30 million")
    assert not contains_numeric_token("I answer census questions.")
