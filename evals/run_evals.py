#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from evals.config import get_eval_settings
from evals.loader import EvalItem, execution_plan, load_question_set
from evals.reference import ReferenceSource, build_snowflake_reference, resolve_target
from evals.report import EvalRun, render_json, render_markdown, timestamp_slug
from evals.scoring import ChatObservation, UsageSummary, score_item, summarize

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Miniflake golden eval set")
    parser.add_argument(
        "--target",
        default=None,
        help="Base URL of the service (default from eval config)",
    )
    parser.add_argument("--items", nargs="*", default=[], help="Run only these item ids")
    parser.add_argument("--categories", nargs="*", default=[], help="Run only these categories")
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
    return parser.parse_args()


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


def _filter_groups(
    groups: list[list[EvalItem]],
    item_ids: list[str],
    categories: list[str],
) -> list[list[EvalItem]]:
    if not item_ids and not categories:
        return groups
    allowed_ids = set(item_ids)
    allowed_categories = set(categories)
    filtered: list[list[EvalItem]] = []
    for group in groups:
        selected = [
            item
            for item in group
            if (not item_ids or item.id in allowed_ids)
            and (not categories or item.category in allowed_categories)
        ]
        if selected:
            filtered.append(selected)
    return filtered


def _login(client: httpx.Client) -> None:
    passphrase = os.environ.get("DEMO_PASSPHRASE")
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
    settings_timeout: float,
    retry_count: int,
) -> tuple[dict[str, object], float]:
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
            return payload, elapsed_ms
        except Exception as exc:
            last_error = exc
            if attempt < retry_count:
                time.sleep(2)
                continue
            raise RuntimeError(f"request failed for {item.id}: {exc}") from exc
    raise RuntimeError(f"request failed for {item.id}: {last_error}")


def _observation_from_payload(payload: dict[str, object]) -> ChatObservation:
    usage_raw = payload.get("usage") or {}
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
    )


def run_evals(args: argparse.Namespace) -> EvalRun:
    settings = get_eval_settings()
    target = (args.target or settings.default_target_url).rstrip("/")
    question_set = load_question_set()
    groups = _filter_groups(execution_plan(question_set), args.items, args.categories)
    reference: ReferenceSource | None = None
    if args.check_values:
        reference = build_snowflake_reference()
    started_at = datetime.now(UTC)
    results: list = []
    timeout = settings.http_timeout_seconds
    with httpx.Client(base_url=target, timeout=timeout) as client:
        if not args.no_auth:
            _login(client)
        for group in groups:
            _reset_conversation(client)
            for item in group:
                print(f"Running {item.id}...", flush=True)
                payload, _elapsed = _ask(client, item, timeout, settings.retry_count)
                observation = _observation_from_payload(payload)
                reference_value = None
                if args.check_values and reference is not None:
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
    finished_at = datetime.now(UTC)
    summary = summarize(results, settings)
    return EvalRun(
        target_url=target,
        started_at=started_at,
        finished_at=finished_at,
        git_sha=_git_sha(),
        check_values=args.check_values,
        strict=args.strict,
        item_filter=args.items,
        category_filter=args.categories,
        results=results,
        summary=summary,
        settings=settings,
    )


def main() -> int:
    args = parse_args()
    try:
        run = run_evals(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    slug = timestamp_slug(run.finished_at)
    json_path = args.out_dir / f"{slug}.json"
    md_path = args.out_dir / f"{slug}.md"
    json_path.write_text(render_json(run), encoding="utf-8")
    md_path.write_text(render_markdown(run), encoding="utf-8")
    print(f"Wrote {md_path}")
    print(f"Wrote {json_path}")
    print(
        f"Passed {run.summary.passed}/{run.summary.total} "
        f"(p50={run.summary.latency_p50_ms:.0f}ms p95={run.summary.latency_p95_ms:.0f}ms)"
    )
    if args.strict:
        gate_failures = [
            result
            for result in run.results
            if result.expected in {"refuse", "unanswerable"} and not result.passed
        ]
        if gate_failures:
            print(
                f"Strict gate failed for: {', '.join(result.id for result in gate_failures)}",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
