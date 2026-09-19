from __future__ import annotations

import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from evals.config import EvalSettings
from evals.scoring import ItemResult, RunSummary


class EvalRun(BaseModel):
    target_url: str
    started_at: datetime
    finished_at: datetime
    git_sha: str | None = None
    check_values: bool = True
    strict: bool = False
    item_filter: list[str] = Field(default_factory=list)
    category_filter: list[str] = Field(default_factory=list)
    results: list[ItemResult]
    summary: RunSummary
    settings: EvalSettings


def render_json(run: EvalRun) -> str:
    return json.dumps(run.model_dump(mode="json"), indent=2)


def render_markdown(run: EvalRun) -> str:
    lines: list[str] = [
        "# Eval report",
        "",
        f"- Target: {run.target_url}",
        f"- Started: {run.started_at.astimezone(UTC).isoformat()}",
        f"- Finished: {run.finished_at.astimezone(UTC).isoformat()}",
        f"- Git SHA: {run.git_sha or 'unknown'}",
        f"- Check values: {run.check_values}",
        f"- Strict: {run.strict}",
        "",
        "## Summary",
        "",
        f"- Total: {run.summary.total}",
        f"- Passed: {run.summary.passed}",
        f"- Pass rate: {run.summary.passed / run.summary.total:.1%}"
        if run.summary.total
        else "- Pass rate: n/a",
        f"- Latency p50: {run.summary.latency_p50_ms:.0f} ms "
        f"({'within' if run.summary.latency_p50_within_budget else 'over'} budget)",
        f"- Latency p95: {run.summary.latency_p95_ms:.0f} ms "
        f"({'within' if run.summary.latency_p95_within_budget else 'over'} budget)",
        f"- Mean tool calls: {run.summary.mean_tool_calls:.2f}",
        f"- Mean input tokens: {run.summary.mean_input_tokens:.1f}",
        f"- Mean output tokens: {run.summary.mean_output_tokens:.1f}",
        f"- Projected cost per 100 questions: ${run.summary.projected_cost_per_100:.4f}",
        "",
        "### By category",
        "",
        "| Category | Passed | Total | Rate |",
        "| :--- | ---: | ---: | ---: |",
    ]
    for category in run.summary.by_category:
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
    for expected in run.summary.by_expected:
        lines.append(
            f"| {expected.expected} | {expected.passed} | {expected.total} | "
            f"{expected.pass_rate:.0%} |"
        )
    lines.extend(["", "## Per-item results", ""])
    for result in run.results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"### {result.id} ({status})")
        lines.append("")
        lines.append(f"- Category: {result.category}")
        lines.append(f"- Expected: {result.expected}")
        lines.append(f"- Observed: {result.observed_outcome}")
        lines.append(f"- Latency: {result.latency_ms:.0f} ms")
        lines.append(f"- Tokens: in={result.input_tokens} out={result.output_tokens}")
        lines.append(f"- Tool calls: {', '.join(result.tool_call_names) or 'none'}")
        if result.failures:
            lines.append(f"- Failures: {'; '.join(result.failures)}")
        if result.value_check is not None:
            lines.append(
                f"- Value check: {result.value_check.status} "
                f"(ref={result.value_check.reference_value}, "
                f"agent={result.value_check.agent_values})"
            )
        if result.note:
            lines.append(f"- Note: {result.note}")
        lines.append("")
        lines.append("```")
        lines.append(result.text.strip() or "(empty)")
        lines.append("```")
        lines.append("")
    failures = [result for result in run.results if not result.passed]
    if failures:
        lines.extend(["## Failures for triage", ""])
        for result in failures:
            lines.append(
                f"- **{result.id}** ({result.category}, expected {result.expected}): "
                f"{'; '.join(result.failures) or 'unspecified failure'}"
            )
    return "\n".join(lines).rstrip() + "\n"


def timestamp_slug(moment: datetime | None = None) -> str:
    resolved = moment or datetime.now(UTC)
    return resolved.strftime("%Y%m%dT%H%M%SZ")
