from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from evals.config import EvalSettings
from evals.loader import QuestionSet
from evals.reference import ReferenceSource, resolve_target
from evals.report import EvalRun
from evals.scoring import ItemResult, score_item, summarize


class RescoreError(RuntimeError):
    pass


def load_run(path: Path | str) -> EvalRun:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        return EvalRun.model_validate(raw)
    except ValidationError as exc:
        raise RescoreError(
            f"{path} is not a re-scorable report (legacy format without raw observations); "
            "re-run the evals to produce a new one"
        ) from exc


def _saved_reference(result: ItemResult) -> float | None:
    if result.value_check is None:
        return None
    return result.value_check.reference_value


def rescore_run(
    run: EvalRun,
    question_set: QuestionSet,
    settings: EvalSettings,
    *,
    source_slug: str,
    reference: ReferenceSource | None = None,
) -> EvalRun:
    active = {item.id: item for item in question_set.items if item.status == "active"}
    results: list[ItemResult] = []
    missing: list[str] = []
    for saved in run.results:
        item = active.get(saved.id)
        if item is None:
            missing.append(saved.id)
            continue
        if saved.observation is None:
            raise RescoreError(
                f"report has no raw observations for {saved.id}; re-run the evals instead"
            )
        reference_value = _saved_reference(saved)
        if reference is not None and item.value_check is not None:
            target = resolve_target(item, {"tool_calls": saved.observation.tool_calls})
            if target is not None:
                reference_value = reference.fetch_value(target)
        results.append(
            score_item(
                item,
                saved.observation,
                latency_budget_seconds=settings.latency_budget_seconds,
                reference_value=reference_value,
                default_tolerance_pct=settings.default_tolerance_pct,
            )
        )
    now = datetime.now(UTC)
    return EvalRun(
        target_url=run.target_url,
        started_at=run.started_at,
        finished_at=now,
        git_sha=run.git_sha,
        check_values=run.check_values or reference is not None,
        strict=run.strict,
        item_filter=run.item_filter,
        category_filter=run.category_filter,
        expected_filter=run.expected_filter,
        rescored_from=source_slug,
        missing_items=missing,
        workers=run.workers,
        results=results,
        summary=summarize(results, settings),
        settings=settings,
    )
