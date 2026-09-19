from __future__ import annotations

from datetime import UTC, datetime

from app.config import Settings
from app.guardrails.pipeline import load_templates
from evals.config import EvalSettings
from evals.loader import EvalItem, ProvenanceExpectation, ValueCheck
from evals.report import EvalRun, render_json, render_markdown
from evals.scoring import ChatObservation, ItemResult, RunSummary, score_item, summarize


def _item(**overrides: object) -> EvalItem:
    base = {
        "id": "L01",
        "category": "lookup",
        "question": "What is the population of Texas?",
        "expected": "answer",
        "status": "active",
    }
    base.update(overrides)
    return EvalItem.model_validate(base)


def _observation(**overrides: object) -> ChatObservation:
    base = {
        "outcome": "answer",
        "text": "Texas has about 29,145,505 residents.",
        "tool_calls": [
            {
                "name": "get_value",
                "result_kind": "success",
                "data": {
                    "field_id": "B01003e1",
                    "geo_id": "48",
                    "geography_name": "Texas",
                    "vintage": 2020,
                    "value": 29145505,
                    "aggregation_method": "sum",
                },
            }
        ],
        "provenance": [{"aggregation_method": "sum"}],
        "latency_ms": 1200.0,
    }
    base.update(overrides)
    return ChatObservation.model_validate(base)


def test_outcome_match_passes() -> None:
    result = score_item(_item(), _observation(), latency_budget_seconds=60)
    assert result.passed
    assert result.observed_outcome == "answer"


def test_outcome_mismatch_fails() -> None:
    result = score_item(
        _item(expected="refuse"),
        _observation(outcome="answer"),
        latency_budget_seconds=60,
    )
    assert not result.passed
    assert any("outcome expected refuse" in failure for failure in result.failures)


def test_wrong_canned_clarify_template_fails() -> None:
    templates = load_templates()
    result = score_item(
        _item(
            id="AG03",
            category="ambiguous_geography",
            expected="clarify",
            expected_missing="geography",
        ),
        _observation(
            outcome="clarify",
            text=templates["needs_clarification_vintage"],
            tool_calls=[],
        ),
        latency_budget_seconds=60,
    )
    assert not result.passed
    assert any("clarify slot" in failure for failure in result.failures)


def test_matching_canned_clarify_template_passes() -> None:
    templates = load_templates()
    result = score_item(
        _item(
            id="AG02",
            category="ambiguous_geography",
            expected="clarify",
            expected_missing="geography",
        ),
        _observation(
            outcome="clarify",
            text=templates["needs_clarification_geography"],
            tool_calls=[],
        ),
        latency_budget_seconds=60,
    )
    assert result.passed


def test_agent_written_clarify_does_not_require_canned_template() -> None:
    result = score_item(
        _item(
            id="AG03",
            category="ambiguous_geography",
            expected="clarify",
            expected_missing="geography",
        ),
        _observation(
            outcome="clarify",
            text="Which Orange County did you mean, California or Florida?",
            tool_calls=[],
        ),
        latency_budget_seconds=60,
    )
    assert result.passed


def test_expect_no_data_call_violation_fails() -> None:
    result = score_item(
        _item(expected="refuse", expect_no_data_call=True),
        _observation(outcome="refuse", tool_calls=[{"name": "get_value"}]),
        latency_budget_seconds=60,
    )
    assert not result.passed
    assert any("no data call" in failure for failure in result.failures)


def test_provenance_series_level_geo_and_aggregation() -> None:
    item = _item(
        provenance=ProvenanceExpectation(
            series="B01003",
            level="State",
            geo_name_contains="Texas",
            aggregation_method="sum",
        )
    )
    result = score_item(item, _observation(), latency_budget_seconds=60)
    assert result.passed


def test_provenance_rank_payload_matches_level() -> None:
    item = _item(
        id="R01",
        category="ranking",
        provenance=ProvenanceExpectation(series="B01003", level="State", aggregation_method="sum"),
    )
    observation = _observation(
        text="Top states by population.",
        tool_calls=[
            {
                "name": "rank_geographies",
                "result_kind": "success",
                "data": {
                    "field_id": "B01003e1",
                    "level": "State",
                    "vintage": 2020,
                    "rankings": [{"geo_id": "48", "name": "Texas", "value": 29145505}],
                },
            }
        ],
    )
    result = score_item(item, observation, latency_budget_seconds=60)
    assert result.passed


def test_provenance_compare_payload_matches_geo_name() -> None:
    item = _item(
        id="C02",
        category="comparison",
        provenance=ProvenanceExpectation(series="B01003", level="County", aggregation_method="sum"),
    )
    observation = _observation(
        text="Los Angeles County has more people than Harris County.",
        tool_calls=[
            {
                "name": "compare",
                "result_kind": "success",
                "data": {
                    "field_id": "B01003e1",
                    "vintage": 2020,
                    "geographies": [
                        {"geo_id": "06037", "geography_name": "Los Angeles County", "value": 1},
                        {"geo_id": "48201", "geography_name": "Harris County", "value": 2},
                    ],
                },
            }
        ],
    )
    result = score_item(item, observation, latency_budget_seconds=60)
    assert result.passed


def test_latency_over_budget_fails() -> None:
    result = score_item(_item(), _observation(latency_ms=70000), latency_budget_seconds=60)
    assert not result.passed
    assert any("latency" in failure for failure in result.failures)


def test_value_check_within_tolerance_passes() -> None:
    item = _item(value_check=ValueCheck(tolerance_pct=1.0))
    result = score_item(
        item,
        _observation(text="Population is 29,145,505."),
        latency_budget_seconds=60,
        reference_value=29_145_505,
    )
    assert result.passed
    assert result.value_check is not None
    assert result.value_check.status == "pass"


def test_value_check_outside_tolerance_fails() -> None:
    item = _item(value_check=ValueCheck(tolerance_pct=0.1))
    result = score_item(
        item,
        _observation(text="Population is 30,000,000."),
        latency_budget_seconds=60,
        reference_value=29_145_505,
    )
    assert not result.passed
    assert result.value_check is not None
    assert result.value_check.status == "fail"


def test_value_check_no_reference_skips_failure() -> None:
    item = _item(value_check=ValueCheck(tolerance_pct=1.0))
    result = score_item(item, _observation(), latency_budget_seconds=60, reference_value=None)
    assert result.passed
    assert result.value_check is not None
    assert result.value_check.status == "no_reference"


def test_summarize_percentiles_and_cost() -> None:
    settings = EvalSettings(
        LATENCY_BUDGET_SECONDS=60,
        AGENT_INPUT_PRICE_PER_MILLION=3.0,
        AGENT_OUTPUT_PRICE_PER_MILLION=15.0,
    )
    results = [
        ItemResult(
            id="A",
            category="lookup",
            expected="answer",
            observed_outcome="answer",
            passed=True,
            latency_ms=1000,
            input_tokens=1000,
            output_tokens=100,
            tool_call_names=["get_value"],
        ),
        ItemResult(
            id="B",
            category="lookup",
            expected="answer",
            observed_outcome="answer",
            passed=True,
            latency_ms=3000,
            input_tokens=2000,
            output_tokens=200,
            tool_call_names=["get_value", "find_geography"],
        ),
    ]
    summary = summarize(results, settings)
    assert summary.total == 2
    assert summary.passed == 2
    assert summary.latency_p50_ms == 2000
    assert summary.mean_tool_calls == 1.5
    assert summary.projected_cost_per_100 > 0


def test_report_rendering_from_fixed_result_set() -> None:
    settings = EvalSettings()
    summary = RunSummary(
        total=1,
        passed=0,
        by_category=[],
        by_expected=[],
        latency_p50_ms=1000,
        latency_p95_ms=1000,
        mean_tool_calls=1,
        mean_input_tokens=10,
        mean_output_tokens=5,
        projected_cost_per_100=0.01,
        latency_budget_ms=60000,
        latency_p50_within_budget=True,
        latency_p95_within_budget=True,
    )
    run = EvalRun(
        target_url="http://localhost:8080",
        started_at=datetime(2026, 9, 19, tzinfo=UTC),
        finished_at=datetime(2026, 9, 19, tzinfo=UTC),
        results=[
            ItemResult(
                id="OT01",
                category="off_topic",
                expected="refuse",
                observed_outcome="answer",
                passed=False,
                failures=["outcome expected refuse, got answer"],
                text="Here is a poem.",
            )
        ],
        summary=summary,
        settings=settings,
    )
    markdown = render_markdown(run)
    payload = render_json(run)
    assert "OT01" in markdown
    assert "FAIL" in markdown
    assert '"OT01"' in payload


def test_eval_latency_budget_default_matches_product_response_budget() -> None:
    eval_default = EvalSettings.model_fields["latency_budget_seconds"].default
    product_default = Settings.model_fields["response_budget_seconds"].default
    assert eval_default == product_default


def test_eval_http_timeout_exceeds_hard_agent_budget() -> None:
    eval_http = EvalSettings.model_fields["http_timeout_seconds"].default
    agent_budget = Settings.model_fields["agent_budget_seconds"].default
    assert eval_http > agent_budget
