from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.loader import EvalItem, QuestionSet, execution_plan, load_question_set

QUESTIONS_PATH = Path(__file__).resolve().parents[3] / "evals" / "questions.yaml"


def _minimal_item(**overrides: object) -> dict[str, object]:
    base = {
        "id": "X01",
        "category": "lookup",
        "question": "What is the population of Texas?",
        "expected": "answer",
        "status": "active",
    }
    base.update(overrides)
    return base


def test_load_real_questions_yaml_is_valid() -> None:
    question_set = load_question_set(QUESTIONS_PATH)
    assert question_set.version >= 2
    assert len(question_set.items) >= 40


def test_required_fields_enforced() -> None:
    with pytest.raises(ValidationError):
        EvalItem.model_validate({"id": "X01", "category": "lookup"})


def test_invalid_category_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid category"):
        EvalItem.model_validate(_minimal_item(category="not_a_category"))


def test_invalid_expected_rejected() -> None:
    with pytest.raises(ValidationError):
        EvalItem.model_validate(_minimal_item(expected="maybe"))


def test_follow_up_requires_parent() -> None:
    with pytest.raises(ValueError, match="follows unknown id"):
        QuestionSet.model_validate(
            {
                "version": 1,
                "items": [
                    _minimal_item(id="F01", category="follow_up", follows="L01", expected="answer"),
                ],
            }
        )


def test_follow_up_category_requires_follows() -> None:
    with pytest.raises(ValueError, match="must set follows"):
        EvalItem.model_validate(_minimal_item(id="F01", category="follow_up", expected="answer"))


def test_non_follow_up_cannot_have_follows() -> None:
    with pytest.raises(ValueError, match="category is not follow_up"):
        EvalItem.model_validate(_minimal_item(follows="L01"))


def test_provenance_only_on_answer_items() -> None:
    with pytest.raises(ValueError, match="provenance only allowed"):
        EvalItem.model_validate(
            _minimal_item(
                expected="refuse",
                provenance={"series": "B01003"},
            )
        )


def test_expected_missing_rejected_on_non_clarify_items() -> None:
    with pytest.raises(ValueError, match="expected_missing only allowed"):
        EvalItem.model_validate(_minimal_item(expected="answer", expected_missing="geography"))


def test_expected_missing_allowed_on_clarify_items() -> None:
    item = EvalItem.model_validate(_minimal_item(expected="clarify", expected_missing="geography"))
    assert item.expected_missing == "geography"


def test_invalid_expected_missing_rejected() -> None:
    with pytest.raises(ValidationError):
        EvalItem.model_validate(_minimal_item(expected="clarify", expected_missing="vintage"))


def test_duplicate_ids_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate item ids"):
        QuestionSet.model_validate(
            {
                "version": 1,
                "items": [
                    _minimal_item(id="L01"),
                    _minimal_item(id="L01", question="duplicate"),
                ],
            }
        )


def test_execution_plan_groups_follow_ups_with_parent() -> None:
    question_set = QuestionSet.model_validate(
        {
            "version": 1,
            "items": [
                _minimal_item(id="L01"),
                _minimal_item(id="L02"),
                _minimal_item(id="F01", category="follow_up", follows="L01", expected="answer"),
                _minimal_item(id="F02", category="follow_up", follows="L01", expected="answer"),
            ],
        }
    )
    groups = execution_plan(question_set)
    assert [item.id for item in groups[0]] == ["L01", "F01", "F02"]
    assert [item.id for item in groups[1]] == ["L02"]


def test_execution_plan_skips_retired_items() -> None:
    question_set = QuestionSet.model_validate(
        {
            "version": 1,
            "items": [
                _minimal_item(id="L01", status="retired"),
                _minimal_item(id="L02"),
            ],
        }
    )
    groups = execution_plan(question_set)
    assert len(groups) == 1
    assert groups[0][0].id == "L02"


def test_execution_plan_every_active_item_in_exactly_one_group() -> None:
    question_set = load_question_set(QUESTIONS_PATH)
    groups = execution_plan(question_set)
    active_ids = [item.id for item in question_set.items if item.status == "active"]
    grouped_ids = [item.id for group in groups for item in group]
    assert sorted(grouped_ids) == sorted(active_ids)
