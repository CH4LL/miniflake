from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.config import EvalSettings
from evals.loader import EvalItem, QuestionSet
from evals.report import EvalRun, render_json
from evals.rescore import RescoreError, load_run, rescore_run
from evals.scoring import ChatObservation, ItemResult, score_item, summarize

SETTINGS = EvalSettings(LATENCY_BUDGET_SECONDS=60)


def _question_set(*items: dict[str, object]) -> QuestionSet:
    return QuestionSet.model_validate({"version": 5, "items": list(items)})


def _items() -> list[dict[str, object]]:
    return [
        {
            "id": "L01",
            "category": "lookup",
            "question": "What is the population of Texas?",
            "expected": "answer",
            "provenance": {"series": "B01003", "level": "State"},
            "value_check": {"tolerance_pct": 1.0},
            "notes": "Latest vintage.",
        },
        {
            "id": "OT01",
            "category": "off_topic",
            "question": "Write a poem.",
            "expected": "refuse",
            "expect_no_data_call": True,
        },
    ]


def _observations() -> dict[str, ChatObservation]:
    return {
        "L01": ChatObservation(
            outcome="answer",
            text="Texas has 29,145,505 residents.",
            tool_calls=[
                {
                    "name": "get_value",
                    "result_kind": "success",
                    "data": {"field_id": "B01003e1", "geo_id": "48", "vintage": 2020},
                }
            ],
            latency_ms=1500.0,
            conversation_id="c1",
        ),
        "OT01": ChatObservation(outcome="answer", text="Roses are red.", latency_ms=100.0),
    }


def _saved_run(question_set: QuestionSet) -> EvalRun:
    observations = _observations()
    results = [
        score_item(
            item,
            observations[item.id],
            latency_budget_seconds=SETTINGS.latency_budget_seconds,
            reference_value=29_145_505.0 if item.id == "L01" else None,
        )
        for item in question_set.items
    ]
    return EvalRun(
        target_url="http://example",
        started_at=datetime(2026, 9, 20, tzinfo=UTC),
        finished_at=datetime(2026, 9, 20, tzinfo=UTC),
        results=results,
        summary=summarize(results, SETTINGS),
        settings=SETTINGS,
    )


def test_round_trip_reproduces_per_item_outcomes(tmp_path: Path) -> None:
    question_set = _question_set(*_items())
    saved = _saved_run(question_set)
    path = tmp_path / "20260920T000000Z.json"
    path.write_text(render_json(saved), encoding="utf-8")

    loaded = load_run(path)
    rescored = rescore_run(loaded, question_set, SETTINGS, source_slug="20260920T000000Z")

    assert rescored.rescored_from == "20260920T000000Z"
    assert rescored.missing_items == []
    assert [result.id for result in rescored.results] == ["L01", "OT01"]
    for before, after in zip(saved.results, rescored.results, strict=True):
        assert after.passed == before.passed
        assert after.observed_outcome == before.observed_outcome
        assert after.failures == before.failures
        assert after.value_check == before.value_check
    assert rescored.summary.passed == saved.summary.passed


def test_rule_change_in_golden_set_is_applied_offline() -> None:
    question_set = _question_set(*_items())
    saved = _saved_run(question_set)
    assert saved.results[0].passed

    stricter = _items()
    stricter[0]["max_tool_calls"] = 0
    rescored = rescore_run(saved, _question_set(*stricter), SETTINGS, source_slug="x")

    assert not rescored.results[0].passed
    assert rescored.results[0].failures[0].kind == "tool_budget"


def test_items_no_longer_active_are_listed_not_dropped() -> None:
    question_set = _question_set(*_items())
    saved = _saved_run(question_set)
    current = _question_set(_items()[1])

    rescored = rescore_run(saved, current, SETTINGS, source_slug="x")

    assert rescored.missing_items == ["L01"]
    assert [result.id for result in rescored.results] == ["OT01"]


def test_run_without_raw_observations_is_rejected() -> None:
    legacy = EvalRun(
        target_url="http://example",
        started_at=datetime(2026, 9, 19, tzinfo=UTC),
        finished_at=datetime(2026, 9, 19, tzinfo=UTC),
        results=[
            ItemResult(
                id="L01",
                category="lookup",
                expected="answer",
                observed_outcome="answer",
                passed=True,
            )
        ],
        summary=summarize([], SETTINGS),
        settings=SETTINGS,
    )
    question_set = _question_set(*_items())
    with pytest.raises(RescoreError, match="raw observations"):
        rescore_run(legacy, question_set, SETTINGS, source_slug="legacy")


def test_legacy_report_format_is_rejected_with_clear_message(tmp_path: Path) -> None:
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(
        '{"target_url": "x", "started_at": "2026-09-19T00:00:00Z", '
        '"finished_at": "2026-09-19T00:00:00Z", "results": [{"id": "L01", '
        '"category": "lookup", "expected": "answer", "observed_outcome": "answer", '
        '"passed": false, "failures": ["outcome expected answer, got error"]}], '
        '"summary": {}, "settings": {}}',
        encoding="utf-8",
    )
    with pytest.raises(RescoreError, match="legacy format"):
        load_run(legacy_path)


def test_saved_reference_value_is_reused_without_repository() -> None:
    question_set = _question_set(*_items())
    saved = _saved_run(question_set)
    rescored = rescore_run(saved, question_set, SETTINGS, source_slug="x")
    value_check = rescored.results[0].value_check
    assert value_check is not None
    assert value_check.status == "pass"
    assert value_check.reference_value == 29_145_505.0


def test_item_model_accepts_max_tool_calls() -> None:
    item = EvalItem.model_validate({**_items()[0], "max_tool_calls": 3})
    assert item.max_tool_calls == 3
