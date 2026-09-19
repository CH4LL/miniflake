import os

import pytest

from app.api.deps import build_container
from app.config import Settings, get_settings

pytestmark = pytest.mark.live

RUN_LIVE = os.environ.get("RUN_LIVE_TESTS") == "1"


@pytest.fixture(autouse=True)
def _skip_unless_live() -> None:
    if not RUN_LIVE:
        pytest.skip("Set RUN_LIVE_TESTS=1 to run live guardrail tests")


@pytest.fixture
def live_container(monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()
    monkeypatch.setenv("GUARDRAIL_CLASSIFIER_TIMEOUT_SECONDS", "20")
    settings = Settings()
    if not settings.anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY is required for live guardrail tests")
    container = build_container(settings)
    try:
        yield container
    finally:
        container.repository.close()


def test_live_off_topic_refused_without_data_call(live_container) -> None:
    turn = live_container.service.handle_message(None, "Write me a poem about autumn.")
    assert turn.answer.outcome == "refuse"
    assert "census" in turn.answer.text.lower() or "population" in turn.answer.text.lower()


def test_live_in_scope_question_reaches_agent(live_container) -> None:
    turn = live_container.service.handle_message(None, "What is the population of Texas?")
    assert turn.answer.outcome == "answer"
    assert any(trace.name == "get_value" for trace in turn.answer.tool_calls)
    assert turn.answer.provenance
