from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

ALLOWED_CATEGORIES = frozenset(
    {
        "lookup",
        "comparison",
        "ranking",
        "trend",
        "follow_up",
        "ambiguous_geography",
        "ambiguous_variable",
        "missing_variable",
        "unavailable_period",
        "conflicting",
        "unsupported_level",
        "aggregation_trap",
        "off_topic",
        "harmful",
        "injection",
        "meta",
    }
)

ALLOWED_EXPECTED = frozenset({"answer", "clarify", "unanswerable", "refuse"})
ALLOWED_STATUS = frozenset({"active", "retired"})
ALLOWED_AGGREGATION_METHODS = frozenset({"direct", "sum"})
ALLOWED_MISSING = frozenset({"geography", "measure", "generic"})


class ProvenanceExpectation(BaseModel):
    series: str | None = None
    level: str | None = None
    geo_name_contains: str | None = None
    aggregation_method: Literal["direct", "sum"] | None = None


class ValueCheck(BaseModel):
    tolerance_pct: float
    field_id: str | None = None
    geo_id: str | None = None
    vintage: int | None = None


class EvalItem(BaseModel):
    id: str
    category: str
    question: str
    expected: Literal["answer", "clarify", "unanswerable", "refuse"]
    provenance: ProvenanceExpectation | None = None
    value_check: ValueCheck | None = None
    follows: str | None = None
    expect_no_data_call: bool = False
    notes: str | None = None
    status: Literal["active", "retired"] = "active"
    expected_missing: Literal["geography", "measure", "generic"] | None = None

    @model_validator(mode="after")
    def validate_item_rules(self) -> EvalItem:
        if self.category not in ALLOWED_CATEGORIES:
            raise ValueError(f"Invalid category: {self.category}")
        if self.expected not in ALLOWED_EXPECTED:
            raise ValueError(f"Invalid expected outcome: {self.expected}")
        if self.status not in ALLOWED_STATUS:
            raise ValueError(f"Invalid status: {self.status}")
        if self.expected_missing is not None:
            if self.expected != "clarify":
                raise ValueError(f"item {self.id}: expected_missing only allowed for clarify items")
            if self.expected_missing not in ALLOWED_MISSING:
                raise ValueError(
                    f"item {self.id}: invalid expected_missing {self.expected_missing}"
                )
        if self.category == "follow_up":
            if not self.follows:
                raise ValueError(f"follow_up item {self.id} must set follows")
        elif self.follows is not None:
            raise ValueError(f"item {self.id} has follows but category is not follow_up")
        if self.expected != "answer":
            if self.provenance is not None:
                raise ValueError(f"item {self.id}: provenance only allowed for answer items")
            if self.value_check is not None:
                raise ValueError(f"item {self.id}: value_check only allowed for answer items")
        if self.provenance is not None and self.provenance.aggregation_method is not None:
            if self.provenance.aggregation_method not in ALLOWED_AGGREGATION_METHODS:
                raise ValueError(
                    f"item {self.id}: invalid aggregation_method "
                    f"{self.provenance.aggregation_method}"
                )
        return self


class QuestionSet(BaseModel):
    version: int
    items: list[EvalItem]

    @model_validator(mode="after")
    def validate_question_set(self) -> QuestionSet:
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            duplicates = {item_id for item_id in ids if ids.count(item_id) > 1}
            raise ValueError(f"Duplicate item ids: {sorted(duplicates)}")
        by_id = {item.id: item for item in self.items}
        for item in self.items:
            if item.follows is not None:
                parent = by_id.get(item.follows)
                if parent is None:
                    raise ValueError(f"item {item.id} follows unknown id {item.follows}")
                if parent.category == "follow_up":
                    raise ValueError(
                        f"item {item.id} follows follow_up {item.follows}; parent must be a root"
                    )
        return self


def load_question_set(path: Path | str | None = None) -> QuestionSet:
    default_path = Path(__file__).resolve().parent / "questions.yaml"
    resolved = Path(path) if path is not None else default_path
    raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    return QuestionSet.model_validate(raw)


def execution_plan(
    question_set: QuestionSet,
    *,
    include_retired: bool = False,
) -> list[list[EvalItem]]:
    items = (
        question_set.items
        if include_retired
        else [item for item in question_set.items if item.status == "active"]
    )
    groups: dict[str, list[EvalItem]] = {}
    root_order: list[str] = []
    for item in items:
        if item.follows is None:
            groups[item.id] = [item]
            root_order.append(item.id)
        else:
            if item.follows not in groups:
                raise ValueError(f"follow-up {item.id} parent {item.follows} not in active set")
            groups[item.follows].append(item)
    assigned = {item.id for group in groups.values() for item in group}
    missing = {item.id for item in items} - assigned
    if missing:
        raise ValueError(f"items not assigned to any group: {sorted(missing)}")
    return [groups[root_id] for root_id in root_order]
