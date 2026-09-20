from __future__ import annotations

import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from evals.config import EvalSettings
from evals.scoring import FAILURE_KIND_ORDER, ItemResult, RunSummary


class EvalRun(BaseModel):
    target_url: str
    started_at: datetime
    finished_at: datetime
    git_sha: str | None = None
    check_values: bool = True
    strict: bool = False
    item_filter: list[str] = Field(default_factory=list)
    category_filter: list[str] = Field(default_factory=list)
    expected_filter: list[str] = Field(default_factory=list)
    rescored_from: str | None = None
    missing_items: list[str] = Field(default_factory=list)
    workers: int = 1
    results: list[ItemResult]
    summary: RunSummary
    settings: EvalSettings


def render_json(run: EvalRun) -> str:
    return json.dumps(run.model_dump(mode="json"), indent=2)


def group_failures(results: list[ItemResult]) -> dict[str, list[tuple[ItemResult, str]]]:
    grouped: dict[str, list[tuple[ItemResult, str]]] = {}
    for result in results:
        for failure in result.failures:
            grouped.setdefault(failure.kind, []).append((result, failure.message))
    ordered: dict[str, list[tuple[ItemResult, str]]] = {}
    for kind in FAILURE_KIND_ORDER:
        if kind in grouped:
            ordered[kind] = grouped[kind]
    for kind, entries in grouped.items():
        ordered.setdefault(kind, entries)
    return ordered


def _header(run: EvalRun) -> list[str]:
    lines = [
        "# Eval report",
        "",
        f"- Target: {run.target_url}",
        f"- Started: {run.started_at.astimezone(UTC).isoformat()}",
        f"- Finished: {run.finished_at.astimezone(UTC).isoformat()}",
        f"- Git SHA: {run.git_sha or 'unknown'}",
        f"- Check values: {run.check_values}",
        f"- Strict: {run.strict}",
        f"- Workers: {run.workers}",
    ]
    if run.item_filter:
        lines.append(f"- Item filter: {', '.join(run.item_filter)}")
    if run.category_filter:
        lines.append(f"- Category filter: {', '.join(run.category_filter)}")
    if run.expected_filter:
        lines.append(f"- Expected filter: {', '.join(run.expected_filter)}")
    if run.rescored_from:
        lines.append(f"- Rescored from: {run.rescored_from}")
    if run.missing_items:
        lines.append(
            "- Items in the source run no longer active in the golden set: "
            + ", ".join(run.missing_items)
        )
    return lines


def _summary(run: EvalRun) -> list[str]:
    summary = run.summary
    lines = [
        "",
        "## Summary",
        "",
        f"- Total: {summary.total}",
        f"- Passed: {summary.passed}",
        f"- Pass rate: {summary.passed / summary.total:.1%}"
        if summary.total
        else "- Pass rate: n/a",
        f"- Latency p50: {summary.latency_p50_ms:.0f} ms "
        f"({'within' if summary.latency_p50_within_budget else 'over'} budget)",
        f"- Latency p95: {summary.latency_p95_ms:.0f} ms "
        f"({'within' if summary.latency_p95_within_budget else 'over'} budget)",
        f"- Mean tool calls: {summary.mean_tool_calls:.2f}",
        f"- Mean input tokens: {summary.mean_input_tokens:.1f}",
        f"- Mean output tokens: {summary.mean_output_tokens:.1f}",
        f"- Projected cost per 100 questions: ${summary.projected_cost_per_100:.4f} "
        "(agent tokens only; classifier usage is not returned by the API)",
        "",
        "### By category",
        "",
        "| Category | Passed | Total | Rate |",
        "| :--- | ---: | ---: | ---: |",
    ]
    for category in summary.by_category:
        lines.append(
            f"| {category.category} | {category.passed} | {category.total} | "
            f"{category.pass_rate:.0%} |"
        )
    lines.extend(
        [
            "",
            "### By expected outcome",
            "",
            "| Expected | Passed | Total | Rate |",
            "| :--- | ---: | ---: | ---: |",
        ]
    )
    for expected in summary.by_expected:
        lines.append(
            f"| {expected.expected} | {expected.passed} | {expected.total} | "
            f"{expected.pass_rate:.0%} |"
        )
    return lines


def _per_item(result: ItemResult) -> list[str]:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        f"### {result.id} ({status})",
        "",
        f"- Category: {result.category}",
        f"- Expected: {result.expected}",
        f"- Observed: {result.observed_outcome}",
        f"- Latency: {result.latency_ms:.0f} ms",
        f"- Tokens: in={result.input_tokens} out={result.output_tokens}",
        f"- Tool calls: {', '.join(result.tool_call_names) or 'none'}",
    ]
    if result.failures:
        lines.append(
            "- Failures: "
            + "; ".join(f"[{failure.kind}] {failure.message}" for failure in result.failures)
        )
    if result.value_check is not None:
        lines.append(
            f"- Value check: {result.value_check.status} "
            f"(ref={result.value_check.reference_value}, "
            f"agent={result.value_check.agent_values})"
        )
    if result.note:
        lines.append(f"- Note: {result.note}")
    lines.extend(["", "```", result.text.strip() or "(empty)", "```", ""])
    return lines


def _triage(run: EvalRun) -> list[str]:
    failures = [result for result in run.results if not result.passed]
    if not failures:
        return []
    lines = ["## Failures for triage", ""]
    for kind, entries in group_failures(failures).items():
        lines.append(f"### {kind}")
        lines.append("")
        for result, message in entries:
            lines.append(
                f"- **{result.id}** ({result.category}, expected {result.expected}): {message}"
            )
        lines.append("")
    return lines


def render_markdown(run: EvalRun) -> str:
    lines = _header(run) + _summary(run) + ["", "## Per-item results", ""]
    for result in run.results:
        lines.extend(_per_item(result))
    lines.extend(_triage(run))
    return "\n".join(lines).rstrip() + "\n"


def timestamp_slug(moment: datetime | None = None) -> str:
    resolved = moment or datetime.now(UTC)
    return resolved.strftime("%Y%m%dT%H%M%SZ")
