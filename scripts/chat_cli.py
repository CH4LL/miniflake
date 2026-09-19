from __future__ import annotations

import argparse
import sys
import time

from app.agent.loop import AgentLoop
from app.config import Settings, get_settings
from app.data.snowflake_repository import SnowflakeCensusRepository
from app.llm.anthropic_client import AnthropicLLMClient
from app.llm.types import Message, TextBlock
from app.logging import configure_logging
from app.tools.registry import default_registry


def read_question(argv: list[str]) -> str:
    parser = argparse.ArgumentParser(description="Run a single Miniflake agent turn from the CLI")
    parser.add_argument("question", nargs="?", help="Question to ask")
    args = parser.parse_args(argv)
    question = args.question or sys.stdin.read().strip()
    if not question:
        raise SystemExit("No question provided")
    return question


def run_question(question: str, settings: Settings | None = None) -> None:
    get_settings.cache_clear()
    resolved_settings = settings or Settings()
    configure_logging(resolved_settings)
    repository = SnowflakeCensusRepository(resolved_settings)
    try:
        llm = AnthropicLLMClient(resolved_settings)
        registry = default_registry(resolved_settings)
        loop = AgentLoop(llm, registry, repository, resolved_settings)
        deadline = time.monotonic() + resolved_settings.inner_deadline_seconds(
            resolved_settings.api_request_timeout_seconds
        )
        messages = [Message(role="user", content=[TextBlock(text=question)])]
        answer = loop.run(messages, deadline)
        print(f"Outcome: {answer.outcome}")
        print(answer.text)
        for trace in answer.tool_calls:
            print(f"Tool: {trace.name} -> {trace.result_kind} ({trace.duration_ms:.1f} ms)")
        for index, provenance in enumerate(answer.provenance, start=1):
            print(
                "Provenance "
                f"{index}: source={provenance.source} "
                f"method={provenance.aggregation_method.value} "
                f"rows={provenance.row_count}"
            )
    finally:
        repository.close()


def main(argv: list[str] | None = None) -> None:
    question = read_question(argv if argv is not None else sys.argv[1:])
    run_question(question)


if __name__ == "__main__":
    main()
