from __future__ import annotations

import statistics
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.data.rollup import level_for_geo_id, series_id_from_field_id
from app.guardrails.pipeline import load_templates
from evals.config import EvalSettings
from evals.loader import EvalItem
from evals.numeric import extract_numbers


class UsageSummary(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class ChatObservation(BaseModel):
    outcome: Literal["answer", "clarify", "unanswerable", "refuse", "error"]
    text: str = ""
    provenance: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: float = 0.0
    usage: UsageSummary = Field(default_factory=UsageSummary)
    conversation_id: str | None = None


FailureKind = Literal[
    "outcome",
    "clarify_slot",
    "no_data_call",
    "provenance",
    "latency",
    "value",
    "tool_budget",
]

FAILURE_KIND_ORDER: tuple[FailureKind, ...] = (
    "outcome",
    "clarify_slot",
    "no_data_call",
    "provenance",
    "tool_budget",
    "value",
    "latency",
)


class Failure(BaseModel):
    kind: FailureKind
    message: str


class ValueCheckDetail(BaseModel):
    status: Literal["pass", "fail", "skipped", "no_reference", "no_numbers"]
    reference_value: float | None = None
    agent_values: list[float] = Field(default_factory=list)
    tolerance_pct: float | None = None
    message: str = ""


class ItemResult(BaseModel):
    id: str
    category: str
    expected: str
    observed_outcome: str
    passed: bool
    failures: list[Failure] = Field(default_factory=list)
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_call_names: list[str] = Field(default_factory=list)
    provenance_summary: dict[str, Any] = Field(default_factory=dict)
    value_check: ValueCheckDetail | None = None
    text: str = ""
    note: str = ""
    observation: ChatObservation | None = None


class CategorySummary(BaseModel):
    category: str
    total: int
    passed: int

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


class ExpectedSummary(BaseModel):
    expected: str
    total: int
    passed: int

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


class RunSummary(BaseModel):
    total: int
    passed: int
    by_category: list[CategorySummary]
    by_expected: list[ExpectedSummary]
    latency_p50_ms: float
    latency_p95_ms: float
    mean_tool_calls: float
    mean_input_tokens: float
    mean_output_tokens: float
    projected_cost_per_100: float
    latency_budget_ms: float
    latency_p50_within_budget: bool
    latency_p95_within_budget: bool


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _extract_provenance_summary(observation: ChatObservation) -> dict[str, Any]:
    series_ids: set[str] = set()
    levels: set[str] = set()
    geo_names: set[str] = set()
    aggregation_methods: set[str] = set()
    vintages: set[int] = set()

    for tool_call in observation.tool_calls:
        if tool_call.get("result_kind") != "success":
            continue
        data = tool_call.get("data") or {}
        field_id = data.get("field_id")
        if isinstance(field_id, str):
            try:
                series_ids.add(series_id_from_field_id(field_id))
            except ValueError:
                series_ids.add(field_id[:6])
        geo_id = data.get("geo_id")
        if isinstance(geo_id, str):
            try:
                levels.add(level_for_geo_id(geo_id).value)
            except ValueError:
                pass
        geography_name = data.get("geography_name")
        if isinstance(geography_name, str):
            geo_names.add(geography_name)
        level = data.get("level")
        if isinstance(level, str):
            levels.add(level)
        aggregation_method = data.get("aggregation_method")
        if isinstance(aggregation_method, str):
            aggregation_methods.add(aggregation_method)
        vintage = data.get("vintage")
        if isinstance(vintage, int):
            vintages.add(vintage)
        for ranking in data.get("rankings") or []:
            if isinstance(ranking, dict):
                name = ranking.get("name")
                if isinstance(name, str):
                    geo_names.add(name)
                ranked_geo_id = ranking.get("geo_id")
                if isinstance(ranked_geo_id, str):
                    try:
                        levels.add(level_for_geo_id(ranked_geo_id).value)
                    except ValueError:
                        pass
        for geography in data.get("geographies") or []:
            if isinstance(geography, dict):
                name = geography.get("geography_name")
                if isinstance(name, str):
                    geo_names.add(name)
                compared_geo_id = geography.get("geo_id")
                if isinstance(compared_geo_id, str):
                    try:
                        levels.add(level_for_geo_id(compared_geo_id).value)
                    except ValueError:
                        pass

    for record in observation.provenance:
        method = record.get("aggregation_method")
        if isinstance(method, str):
            aggregation_methods.add(method)

    return {
        "series_ids": sorted(series_ids),
        "levels": sorted(levels),
        "geo_names": sorted(geo_names),
        "aggregation_methods": sorted(aggregation_methods),
        "vintages": sorted(vintages),
    }


def _check_clarify_slot(item: EvalItem, observation: ChatObservation) -> list[Failure]:
    if item.expected != "clarify" or item.expected_missing is None:
        return []
    if observation.outcome != "clarify":
        return []
    templates = load_templates()
    observed = observation.text.strip()
    slot_keys = {
        "geography": "needs_clarification_geography",
        "measure": "needs_clarification_measure",
        "generic": "needs_clarification_generic",
        "vintage": "needs_clarification_vintage",
    }
    for slot, key in slot_keys.items():
        canned = templates.get(key, "").strip()
        if canned and observed == canned and slot != item.expected_missing:
            return [
                Failure(
                    kind="clarify_slot",
                    message=(
                        f"clarify slot expected {item.expected_missing}, got canned {slot} template"
                    ),
                )
            ]
    return []


def _check_provenance(item: EvalItem, summary: dict[str, Any]) -> list[Failure]:
    if item.provenance is None:
        return []
    messages: list[str] = []
    expected = item.provenance
    if expected.series is not None:
        if not any(series.startswith(expected.series) for series in summary["series_ids"]):
            messages.append(
                f"provenance series {expected.series} not found in {summary['series_ids']}"
            )
    if expected.level is not None:
        if expected.level not in summary["levels"]:
            messages.append(f"provenance level {expected.level} not found in {summary['levels']}")
    if expected.geo_name_contains is not None:
        needle = expected.geo_name_contains.lower()
        if not any(needle in name.lower() for name in summary["geo_names"]):
            messages.append(
                f"provenance geo_name_contains '{expected.geo_name_contains}' "
                f"not found in {summary['geo_names']}"
            )
    if expected.aggregation_method is not None:
        if expected.aggregation_method not in summary["aggregation_methods"]:
            messages.append(
                f"provenance aggregation_method {expected.aggregation_method} "
                f"not found in {summary['aggregation_methods']}"
            )
    return [Failure(kind="provenance", message=message) for message in messages]


def _check_tool_budget(item: EvalItem, observation: ChatObservation) -> list[Failure]:
    if item.max_tool_calls is None:
        return []
    observed = len(observation.tool_calls)
    if observed <= item.max_tool_calls:
        return []
    return [
        Failure(
            kind="tool_budget",
            message=f"{observed} tool calls exceed max {item.max_tool_calls}",
        )
    ]


def _check_value(
    item: EvalItem,
    observation: ChatObservation,
    reference_value: float | None,
    default_tolerance_pct: float,
) -> ValueCheckDetail:
    if item.value_check is None:
        return ValueCheckDetail(status="skipped", message="no value_check configured")
    tolerance = item.value_check.tolerance_pct
    if reference_value is None:
        return ValueCheckDetail(
            status="no_reference",
            tolerance_pct=tolerance,
            message="reference value unavailable",
        )
    tokens = [token.value for token in extract_numbers(observation.text) if not token.is_percent]
    if not tokens:
        return ValueCheckDetail(
            status="no_numbers",
            reference_value=reference_value,
            tolerance_pct=tolerance,
            message="no numeric tokens in answer text",
        )
    matched = any(
        abs(value - reference_value) <= abs(reference_value) * tolerance / 100.0 for value in tokens
    )
    return ValueCheckDetail(
        status="pass" if matched else "fail",
        reference_value=reference_value,
        agent_values=tokens,
        tolerance_pct=tolerance,
        message="within tolerance" if matched else "no agent value within tolerance",
    )


def score_item(
    item: EvalItem,
    observation: ChatObservation,
    *,
    latency_budget_seconds: float,
    reference_value: float | None = None,
    default_tolerance_pct: float = 1.0,
) -> ItemResult:
    failures: list[Failure] = []
    if observation.outcome != item.expected:
        failures.append(
            Failure(
                kind="outcome",
                message=f"outcome expected {item.expected}, got {observation.outcome}",
            )
        )
    failures.extend(_check_clarify_slot(item, observation))
    if item.expect_no_data_call and observation.tool_calls:
        failures.append(
            Failure(
                kind="no_data_call", message="expected no data call but tool_calls is non-empty"
            )
        )
    summary = _extract_provenance_summary(observation)
    failures.extend(_check_provenance(item, summary))
    failures.extend(_check_tool_budget(item, observation))
    if observation.latency_ms > latency_budget_seconds * 1000:
        failures.append(
            Failure(
                kind="latency",
                message=(
                    f"latency {observation.latency_ms:.0f}ms exceeds budget "
                    f"{latency_budget_seconds * 1000:.0f}ms"
                ),
            )
        )
    value_detail = _check_value(item, observation, reference_value, default_tolerance_pct)
    if value_detail.status == "fail":
        failures.append(Failure(kind="value", message=value_detail.message))
    return ItemResult(
        id=item.id,
        category=item.category,
        expected=item.expected,
        observed_outcome=observation.outcome,
        passed=not failures,
        failures=failures,
        latency_ms=observation.latency_ms,
        input_tokens=observation.usage.input_tokens,
        output_tokens=observation.usage.output_tokens,
        tool_call_names=[str(call.get("name", "")) for call in observation.tool_calls],
        provenance_summary=summary,
        value_check=value_detail if item.value_check is not None else None,
        text=observation.text,
        note=item.notes or "",
        observation=observation,
    )


def summarize(results: list[ItemResult], settings: EvalSettings) -> RunSummary:
    latencies = [result.latency_ms for result in results]
    tool_counts = [len(result.tool_call_names) for result in results]
    input_tokens = [result.input_tokens for result in results]
    output_tokens = [result.output_tokens for result in results]
    budget_ms = settings.latency_budget_seconds * 1000
    p50 = _percentile(latencies, 0.5)
    p95 = _percentile(latencies, 0.95)
    mean_input = statistics.mean(input_tokens) if input_tokens else 0.0
    mean_output = statistics.mean(output_tokens) if output_tokens else 0.0
    cost_per_question = (
        mean_input * settings.agent_input_price_per_million / 1_000_000
        + mean_output * settings.agent_output_price_per_million / 1_000_000
    )
    by_category: dict[str, CategorySummary] = {}
    by_expected: dict[str, ExpectedSummary] = {}
    for result in results:
        category = by_category.setdefault(
            result.category, CategorySummary(category=result.category, total=0, passed=0)
        )
        category.total += 1
        category.passed += int(result.passed)
        expected = by_expected.setdefault(
            result.expected, ExpectedSummary(expected=result.expected, total=0, passed=0)
        )
        expected.total += 1
        expected.passed += int(result.passed)
    return RunSummary(
        total=len(results),
        passed=sum(int(result.passed) for result in results),
        by_category=sorted(by_category.values(), key=lambda item: item.category),
        by_expected=sorted(by_expected.values(), key=lambda item: item.expected),
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        mean_tool_calls=statistics.mean(tool_counts) if tool_counts else 0.0,
        mean_input_tokens=mean_input,
        mean_output_tokens=mean_output,
        projected_cost_per_100=cost_per_question * 100,
        latency_budget_ms=budget_ms,
        latency_p50_within_budget=p50 <= budget_ms,
        latency_p95_within_budget=p95 <= budget_ms,
    )
