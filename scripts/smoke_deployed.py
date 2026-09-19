#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import time

import httpx

GOLDEN_QUESTION = "What is the population of Texas?"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Post-deploy smoke test for Miniflake")
    parser.add_argument("--url", required=True, help="Base URL of the deployed service")
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Number of attempts before failing (allows warm-up to finish)",
    )
    return parser.parse_args()


def run_once(client: httpx.Client, budget_seconds: float) -> tuple[dict[str, object], float]:
    health = client.get("/api/health")
    health.raise_for_status()
    body = health.json()
    if body.get("status") != "ok":
        raise RuntimeError(f"Unexpected health payload: {body}")

    login = client.post("/api/login", json={"passphrase": os.environ["DEMO_PASSPHRASE"]})
    login.raise_for_status()
    if login.json().get("status") != "ok":
        raise RuntimeError(f"Login failed: {login.text}")

    started = time.perf_counter()
    chat = client.post("/api/chat", json={"message": GOLDEN_QUESTION})
    elapsed = time.perf_counter() - started
    chat.raise_for_status()
    payload = chat.json()

    if payload.get("outcome") != "answer":
        raise RuntimeError(f"Expected outcome=answer, got: {payload}")
    if not payload.get("provenance"):
        raise RuntimeError("Expected non-empty provenance")
    if elapsed > budget_seconds:
        raise RuntimeError(f"Latency {elapsed:.2f}s exceeded budget {budget_seconds:.2f}s")
    return payload, elapsed


def main() -> int:
    args = parse_args()
    base_url = args.url.rstrip("/")
    if not os.environ.get("DEMO_PASSPHRASE"):
        print("DEMO_PASSPHRASE is required", file=sys.stderr)
        return 1
    budget_seconds = float(os.environ.get("RESPONSE_BUDGET_SECONDS", "60"))

    last_error: Exception | None = None
    with httpx.Client(base_url=base_url, timeout=budget_seconds + 10) as client:
        for attempt in range(1, args.retries + 1):
            try:
                payload, elapsed = run_once(client, budget_seconds)
                print(
                    f"Smoke test passed: outcome=answer latency={elapsed:.2f}s "
                    f"tool_calls={len(payload.get('tool_calls', []))}"
                )
                return 0
            except Exception as exc:
                last_error = exc
                if attempt < args.retries:
                    print(
                        f"Smoke attempt {attempt} failed ({exc}); retrying...",
                        file=sys.stderr,
                    )
                    time.sleep(10)
                    continue
                print(str(exc), file=sys.stderr)
                return 1
    if last_error is not None:
        print(str(last_error), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
