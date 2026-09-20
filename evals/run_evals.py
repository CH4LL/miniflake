#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

from evals.config import EvalSettings, get_eval_settings
from evals.loader import EvalItem, QuestionSet, execution_plan, load_question_set
from evals.reference import ReferenceSource, build_snowflake_reference, resolve_target
from evals.report import EvalRun, render_json, render_markdown, timestamp_slug
from evals.rescore import load_run, rescore_run
from evals.scoring import ChatObservation, ItemResult, UsageSummary, score_item, summarize

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
GATE_EXPECTED = frozenset({"refuse", "unanswerable"})


@dataclass
class RunOptions:
    target: str | None = None
    items: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    expected: list[str] = field(default_factory=list)
    check_values: bool = True
    out_dir: Path = REPORTS_DIR
    no_auth: bool = False
    strict: bool = False
    rescore: Path | None = None
    requery_values: bool = False
    workers: int = 1
    passphrase: str | None = None
    question_set_path: Path | None = None


def parse_args(argv: list[str] | None = None) -> RunOptions:
    parser = argparse.ArgumentParser(description="Run Miniflake golden eval set")
    parser.add_argument(
        "--target",
        default=None,
        help="Base URL of the service (default from eval config)",
    )
    parser.add_argument("--items", nargs="*", default=[], help="Run only these item ids")
    parser.add_argument("--categories", nargs="*", default=[], help="Run only these categories")
    parser.add_argument(
        "--expected",
        nargs="*",
        default=[],
        help="Run only items with these expected outcomes (e.g. refuse unanswerable)",
    )
    parser.add_argument(
        "--check-values",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Compare answer values against direct repository queries",
    )
    parser.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--no-auth", action="store_true", help="Skip demo login")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any refuse or unanswerable item fails",
    )
    parser.add_argument(
        "--rescore",
        type=Path,
        default=None,
        help="Re-score a saved report JSON offline against the current golden set and rules",
    )
    parser.add_argument(
        "--requery-values",
        action="store_true",
        help="With --rescore, fetch reference values from Snowflake again instead of reusing saved",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=None,
        help="Alternative golden set YAML (default evals/questions.yaml)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Run root groups concurrently with this many HTTP clients (latency reflects load)",
    )
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    return RunOptions(
        target=args.target,
        items=args.items,
        categories=args.categories,
        expected=args.expected,
        check_values=args.check_values,
        out_dir=args.out_dir,
        no_auth=args.no_auth,
        strict=args.strict,
        rescore=args.rescore,
        requery_values=args.requery_values,
        workers=args.workers,
        passphrase=os.environ.get("DEMO_PASSPHRASE"),
        question_set_path=args.questions,
    )


def _git_sha() -> str | None:
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return output.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _filter_groups(groups: list[list[EvalItem]], options: RunOptions) -> list[list[EvalItem]]:
    if not options.items and not options.categories and not options.expected:
        return groups
    allowed_ids = set(options.items)
    allowed_categories = set(options.categories)
    allowed_expected = set(options.expected)
    filtered: list[list[EvalItem]] = []
    for group in groups:
        selected = [
            item
            for item in group
            if (not allowed_ids or item.id in allowed_ids)
            and (not allowed_categories or item.category in allowed_categories)
            and (not allowed_expected or item.expected in allowed_expected)
        ]
        if selected:
            filtered.append(selected)
    return filtered


def _login(client: httpx.Client, passphrase: str | None) -> None:
    if not passphrase:
        raise RuntimeError("DEMO_PASSPHRASE is required for authenticated eval runs")
    response = client.post("/api/login", json={"passphrase": passphrase})
    response.raise_for_status()
    if response.json().get("status") != "ok":
        raise RuntimeError(f"Login failed: {response.text}")


def _reset_conversation(client: httpx.Client) -> None:
    response = client.post("/api/conversations/reset")
    response.raise_for_status()


def _ask(
    client: httpx.Client,
    item: EvalItem,
    retry_count: int,
) -> dict[str, object]:
    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        started = time.perf_counter()
        try:
            response = client.post("/api/chat", json={"message": item.question})
            elapsed_ms = (time.perf_counter() - started) * 1000
            if response.status_code >= 500 and attempt < retry_count:
                time.sleep(2)
                continue
            response.raise_for_status()
            payload = response.json()
            payload["latency_ms"] = elapsed_ms
            return payload
        except Exception as exc:
            last_error = exc
            if attempt < retry_count:
                time.sleep(2)
                continue
            raise RuntimeError(f"request failed for {item.id}: {exc}") from exc
    raise RuntimeError(f"request failed for {item.id}: {last_error}")


def _observation_from_payload(payload: dict[str, object]) -> ChatObservation:
    usage_raw = payload.get("usage") or {}
    conversation_id = payload.get("conversation_id")
    return ChatObservation(
        outcome=str(payload.get("outcome", "error")),
        text=str(payload.get("text", "")),
        provenance=list(payload.get("provenance") or []),
        tool_calls=list(payload.get("tool_calls") or []),
        latency_ms=float(payload.get("latency_ms") or 0.0),
        usage=UsageSummary(
            input_tokens=int(usage_raw.get("input_tokens", 0)),
            output_tokens=int(usage_raw.get("output_tokens", 0)),
        ),
        conversation_id=str(conversation_id) if conversation_id else None,
    )


def _run_group(
    client: httpx.Client,
    group: list[EvalItem],
    settings: EvalSettings,
    reference: ReferenceSource | None,
) -> list[ItemResult]:
    results: list[ItemResult] = []
    _reset_conversation(client)
    for item in group:
        print(f"Running {item.id}...", flush=True)
        payload = _ask(client, item, settings.retry_count)
        observation = _observation_from_payload(payload)
        reference_value = None
        if reference is not None:
            target_ref = resolve_target(item, payload)
            if target_ref is not None:
                reference_value = reference.fetch_value(target_ref)
        results.append(
            score_item(
                item,
                observation,
                latency_budget_seconds=settings.latency_budget_seconds,
                reference_value=reference_value,
                default_tolerance_pct=settings.default_tolerance_pct,
            )
        )
    return results


def _run_groups_with_client(
    client: httpx.Client,
    groups: list[list[EvalItem]],
    options: RunOptions,
    settings: EvalSettings,
    reference: ReferenceSource | None,
) -> list[list[ItemResult]]:
    if not options.no_auth:
        _login(client, options.passphrase)
    return [_run_group(client, group, settings, reference) for group in groups]


def _run_worker(
    client_factory: Callable[[], httpx.Client],
    groups: list[list[EvalItem]],
    options: RunOptions,
    settings: EvalSettings,
    reference: ReferenceSource | None,
) -> list[list[ItemResult]]:
    client = client_factory()
    try:
        return _run_groups_with_client(client, groups, options, settings, reference)
    finally:
        client.close()


def _distribute(groups: list[list[EvalItem]], workers: int) -> list[list[list[EvalItem]]]:
    buckets: list[list[list[EvalItem]]] = [[] for _ in range(workers)]
    for index, group in enumerate(groups):
        buckets[index % workers].append(group)
    return [bucket for bucket in buckets if bucket]


def run_evals(
    options: RunOptions,
    *,
    client: httpx.Client | None = None,
    client_factory: Callable[[], httpx.Client] | None = None,
    question_set: QuestionSet | None = None,
    reference: ReferenceSource | None = None,
) -> EvalRun:
    settings = get_eval_settings()
    target = (options.target or settings.default_target_url).rstrip("/")
    resolved_set = question_set or load_question_set(options.question_set_path)
    groups = _filter_groups(execution_plan(resolved_set), options)
    injected = client is not None or client_factory is not None
    if options.check_values and reference is None and not injected:
        reference = build_snowflake_reference()
    if not options.check_values:
        reference = None
    started_at = datetime.now(UTC)
    workers = max(1, min(options.workers, len(groups) or 1))
    if client is not None:
        if options.workers > 1:
            raise ValueError("--workers requires a client factory; a single client shares cookies")
        grouped_results = _run_groups_with_client(client, groups, options, settings, reference)
    else:
        factory = client_factory or (
            lambda: httpx.Client(base_url=target, timeout=settings.http_timeout_seconds)
        )
        if workers == 1:
            grouped_results = _run_worker(factory, groups, options, settings, reference)
        else:
            buckets = _distribute(groups, workers)
            with ThreadPoolExecutor(max_workers=len(buckets)) as pool:
                futures = [
                    pool.submit(_run_worker, factory, bucket, options, settings, reference)
                    for bucket in buckets
                ]
                per_bucket = [future.result() for future in futures]
            by_group_id: dict[str, list[ItemResult]] = {}
            for bucket, bucket_results in zip(buckets, per_bucket, strict=True):
                for group, group_results in zip(bucket, bucket_results, strict=True):
                    by_group_id[group[0].id] = group_results
            grouped_results = [by_group_id[group[0].id] for group in groups]
    results = [result for group_results in grouped_results for result in group_results]
    finished_at = datetime.now(UTC)
    return EvalRun(
        target_url=target,
        started_at=started_at,
        finished_at=finished_at,
        git_sha=_git_sha(),
        check_values=reference is not None,
        strict=options.strict,
        item_filter=options.items,
        category_filter=options.categories,
        expected_filter=options.expected,
        workers=workers,
        results=results,
        summary=summarize(results, settings),
        settings=settings,
    )


def rescore_from_file(options: RunOptions) -> EvalRun:
    assert options.rescore is not None
    source = load_run(options.rescore)
    question_set = load_question_set(options.question_set_path)
    settings = get_eval_settings()
    reference = build_snowflake_reference() if options.requery_values else None
    return rescore_run(
        source,
        question_set,
        settings,
        source_slug=options.rescore.stem,
        reference=reference,
    )


def write_report(run: EvalRun, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = timestamp_slug(run.finished_at)
    json_path = out_dir / f"{slug}.json"
    md_path = out_dir / f"{slug}.md"
    json_path.write_text(render_json(run), encoding="utf-8")
    md_path.write_text(render_markdown(run), encoding="utf-8")
    return json_path, md_path


def strict_gate_failures(run: EvalRun) -> list[ItemResult]:
    return [
        result for result in run.results if result.expected in GATE_EXPECTED and not result.passed
    ]


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    try:
        run = rescore_from_file(options) if options.rescore else run_evals(options)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    json_path, md_path = write_report(run, options.out_dir)
    print(f"Wrote {md_path}")
    print(f"Wrote {json_path}")
    print(
        f"Passed {run.summary.passed}/{run.summary.total} "
        f"(p50={run.summary.latency_p50_ms:.0f}ms p95={run.summary.latency_p95_ms:.0f}ms)"
    )
    if run.missing_items:
        print(f"Not in current golden set: {', '.join(run.missing_items)}")
    if options.strict:
        gate_failures = strict_gate_failures(run)
        if gate_failures:
            print(
                f"Strict gate failed for: {', '.join(result.id for result in gate_failures)}",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
