from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

from app.agent.loop import AgentLoop
from app.api.deps import AppContainer
from app.config import Settings
from app.conversation.memory_store import InMemoryConversationStore
from app.conversation.service import ConversationService
from app.data.fake_repository import FakeCensusRepository
from app.guardrails.classifier import IntentClassifier
from app.guardrails.pipeline import GuardrailPipeline
from app.llm.fake import FakeLLM
from app.llm.types import LLMResponse, TextBlock, ToolUseBlock, Usage
from app.main import create_app
from app.tools.registry import default_registry
from evals.loader import load_question_set
from evals.reference import RepositoryReference
from evals.rescore import load_run
from evals.run_evals import RunOptions, run_evals, strict_gate_failures, write_report

PASSPHRASE = "test-passphrase"


def _settings() -> Settings:
    return Settings(
        SNOWFLAKE_ACCOUNT="TEST",
        SNOWFLAKE_USER="TEST",
        SNOWFLAKE_ROLE="TEST",
        SNOWFLAKE_WAREHOUSE="TEST",
        SNOWFLAKE_DATABASE="TEST",
        SNOWFLAKE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        DEMO_AUTH_ENABLED=True,
        DEMO_PASSPHRASE=PASSPHRASE,
        AUTH_SIGNING_SECRET="test-signing-secret-at-least-32-chars-long",
        AUTH_COOKIE_NAME="miniflake_auth",
        SESSION_COOKIE_NAME="miniflake_session",
        LOG_FILE="",
        _env_file=None,
    )


def _classifier(intent: str) -> LLMResponse:
    return LLMResponse(
        content=[
            ToolUseBlock(
                id="toolu_classify",
                name="classify_intent",
                input={"intent": intent, "reason": "t", "confidence": 0.95, "missing": "none"},
            )
        ],
        stop_reason="tool_use",
        usage=Usage(),
    )


def _tool_use(name: str, input: dict[str, Any]) -> LLMResponse:
    return LLMResponse(
        content=[ToolUseBlock(id=f"toolu_{name}", name=name, input=input)],
        stop_reason="tool_use",
        usage=Usage(input_tokens=100, output_tokens=10),
    )


def _text(text: str) -> LLMResponse:
    return LLMResponse(
        content=[TextBlock(text=text)],
        stop_reason="end_turn",
        usage=Usage(input_tokens=100, output_tokens=10),
    )


class RecordingClient(TestClient):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.requests: list[tuple[str, str]] = []

    def request(self, method: str, url: Any, *args: Any, **kwargs: Any) -> Any:
        self.requests.append((method.upper(), str(url)))
        return super().request(method, url, *args, **kwargs)


def _container(
    classifier_script: list[LLMResponse],
    agent_script: list[LLMResponse],
    repository: FakeCensusRepository,
) -> AppContainer:
    settings = _settings()
    registry = default_registry(settings)
    store = InMemoryConversationStore(settings)
    agent_llm = FakeLLM(agent_script)
    classifier_llm = FakeLLM(classifier_script)
    loop = AgentLoop(agent_llm, registry, repository, settings)
    guardrails = GuardrailPipeline(settings, IntentClassifier(classifier_llm, settings))
    service = ConversationService(settings, store, loop, guardrails=guardrails)
    return AppContainer(
        settings=settings,
        repository=repository,
        llm=agent_llm,
        classifier_llm=classifier_llm,
        registry=registry,
        store=store,
        service=service,
    )


def _write_questions(path: Path) -> Path:
    payload = {
        "version": 5,
        "items": [
            {
                "id": "L01",
                "category": "lookup",
                "question": "What is the population of Texas?",
                "expected": "answer",
                "provenance": {"series": "B01003", "level": "State", "aggregation_method": "sum"},
                "value_check": {
                    "tolerance_pct": 0.5,
                    "field_id": "B01003e1",
                    "geo_id": "48",
                    "vintage": 2020,
                },
                "notes": "Latest vintage.",
            },
            {
                "id": "F01",
                "category": "follow_up",
                "follows": "L01",
                "question": "And Florida?",
                "expected": "answer",
                "provenance": {
                    "series": "B01003",
                    "level": "State",
                    "geo_name_contains": "Florida",
                },
            },
            {
                "id": "OT01",
                "category": "off_topic",
                "question": "Write me a poem about autumn.",
                "expected": "refuse",
                "expect_no_data_call": True,
            },
        ],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _options(out_dir: Path, **overrides: Any) -> RunOptions:
    base: dict[str, Any] = {
        "target": "http://testserver",
        "out_dir": out_dir,
        "check_values": True,
        "passphrase": PASSPHRASE,
    }
    base.update(overrides)
    return RunOptions(**base)


def test_runner_end_to_end_against_app_with_fakes(tmp_path: Path) -> None:
    repository = FakeCensusRepository(settings=_settings())
    texas = repository.get_observations("B01003e1", ["48"], 2020).rows[0].value
    florida = repository.get_observations("B01003e1", ["12"], 2020).rows[0].value
    agent_script = [
        _tool_use("find_geography", {"query": "Texas", "level": "State"}),
        _tool_use("get_value", {"field_id": "B01003e1", "geo_id": "48"}),
        _text(f"Texas has {texas:,.0f} residents (ACS 2020, sum of block groups)."),
        _tool_use("find_geography", {"query": "Florida", "level": "State"}),
        _tool_use("get_value", {"field_id": "B01003e1", "geo_id": "12"}),
        _text(f"Florida has {florida:,.0f} residents (ACS 2020)."),
    ]
    classifier_script = [_classifier("in_scope"), _classifier("in_scope"), _classifier("off_topic")]
    container = _container(classifier_script, agent_script, repository)
    client = RecordingClient(create_app(container=container))
    questions = _write_questions(tmp_path / "questions.yaml")

    run = run_evals(
        _options(tmp_path / "reports"),
        client=client,
        question_set=load_question_set(questions),
        reference=RepositoryReference(repository),
    )

    assert [result.id for result in run.results] == ["L01", "F01", "OT01"]
    assert run.summary.total == 3
    assert run.summary.passed == 3, [result.failures for result in run.results]
    by_expected = {entry.expected: entry for entry in run.summary.by_expected}
    assert by_expected["answer"].total == 2
    assert by_expected["refuse"].total == 1

    logins = [req for req in run_requests(client) if req.endswith("/api/login")]
    resets = [req for req in run_requests(client) if req.endswith("/api/conversations/reset")]
    assert len(logins) == 1
    assert len(resets) == 2

    root, follow_up, refuse = run.results
    assert root.observation is not None and follow_up.observation is not None
    assert refuse.observation is not None
    assert root.observation.conversation_id == follow_up.observation.conversation_id
    assert refuse.observation.conversation_id != root.observation.conversation_id
    assert root.value_check is not None and root.value_check.status == "pass"
    assert root.note == "Latest vintage."
    assert refuse.tool_call_names == []

    json_path, md_path = write_report(run, tmp_path / "reports")
    assert json_path.exists() and md_path.exists()
    reloaded = load_run(json_path)
    assert [result.id for result in reloaded.results] == ["L01", "F01", "OT01"]
    assert reloaded.results[0].observation is not None
    assert "## Per-item results" in md_path.read_text(encoding="utf-8")
    assert strict_gate_failures(run) == []


def test_expected_filter_runs_only_matching_items(tmp_path: Path) -> None:
    repository = FakeCensusRepository(settings=_settings())
    container = _container([_classifier("off_topic")], [], repository)
    client = RecordingClient(create_app(container=container))
    questions = _write_questions(tmp_path / "questions.yaml")

    run = run_evals(
        _options(tmp_path / "reports", expected=["refuse"], check_values=False),
        client=client,
        question_set=load_question_set(questions),
    )

    assert [result.id for result in run.results] == ["OT01"]
    assert run.expected_filter == ["refuse"]
    chats = [req for req in run_requests(client) if req.endswith("/api/chat")]
    assert len(chats) == 1


def test_strict_gate_reports_failing_refuse_items(tmp_path: Path) -> None:
    repository = FakeCensusRepository(settings=_settings())
    container = _container([_classifier("in_scope")], [_text("Roses are red.")], repository)
    client = RecordingClient(create_app(container=container))
    questions = _write_questions(tmp_path / "questions.yaml")

    run = run_evals(
        _options(tmp_path / "reports", expected=["refuse"], check_values=False),
        client=client,
        question_set=load_question_set(questions),
    )

    assert [result.id for result in strict_gate_failures(run)] == ["OT01"]


def _write_refuse_only_questions(path: Path, count: int) -> Path:
    payload = {
        "version": 5,
        "items": [
            {
                "id": f"OT{index:02d}",
                "category": "off_topic",
                "question": f"Write me poem number {index}.",
                "expected": "refuse",
                "expect_no_data_call": True,
            }
            for index in range(1, count + 1)
        ],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_workers_run_root_groups_in_parallel_with_one_client_each(tmp_path: Path) -> None:
    repository = FakeCensusRepository(settings=_settings())
    container = _container([_classifier("off_topic")] * 4, [], repository)
    app = create_app(container=container)
    created: list[RecordingClient] = []

    def factory() -> RecordingClient:
        client = RecordingClient(app)
        created.append(client)
        return client

    questions = _write_refuse_only_questions(tmp_path / "questions.yaml", 4)
    run = run_evals(
        _options(tmp_path / "reports", check_values=False, workers=2),
        client_factory=factory,
        question_set=load_question_set(questions),
    )

    assert run.workers == 2
    assert [result.id for result in run.results] == ["OT01", "OT02", "OT03", "OT04"]
    assert run.summary.passed == 4
    assert len(created) == 2
    for client in created:
        logins = [req for req in run_requests(client) if req.endswith("/api/login")]
        assert len(logins) == 1
    total_resets = sum(
        1 for client in created for req in run_requests(client) if req.endswith("/reset")
    )
    assert total_resets == 4
    conversation_ids = {
        result.observation.conversation_id
        for result in run.results
        if result.observation is not None
    }
    assert len(conversation_ids) == 4
    _json_path, md_path = write_report(run, tmp_path / "reports")
    assert "- Workers: 2" in md_path.read_text(encoding="utf-8")


def run_requests(client: RecordingClient) -> list[str]:
    return [url for _method, url in client.requests]
