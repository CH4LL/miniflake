import os
import time

import pytest

from app.agent.loop import AgentLoop
from app.config import Settings, get_settings
from app.data.snowflake_repository import SnowflakeCensusRepository
from app.llm.anthropic_client import AnthropicLLMClient
from app.llm.types import Message, TextBlock
from app.tools.registry import default_registry

pytestmark = pytest.mark.live

RUN_LIVE = os.environ.get("RUN_LIVE_TESTS") == "1"


@pytest.fixture(autouse=True)
def _skip_unless_live() -> None:
    if not RUN_LIVE:
        pytest.skip("Set RUN_LIVE_TESTS=1 to run live agent tests")


@pytest.fixture
def live_settings() -> Settings:
    get_settings.cache_clear()
    settings = Settings()
    if not settings.anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY is required for live agent tests")
    return settings


def test_live_state_population_lookup(live_settings: Settings) -> None:
    repository = SnowflakeCensusRepository(live_settings)
    try:
        llm = AnthropicLLMClient(live_settings)
        registry = default_registry(live_settings)
        loop = AgentLoop(llm, registry, repository, live_settings)
        deadline = time.monotonic() + max(live_settings.agent_budget_seconds, 60.0)
        answer = loop.run(
            [Message(role="user", content=[TextBlock(text="What is the population of Texas?")])],
            deadline,
        )
        assert answer.outcome == "answer"
        assert any(trace.name == "get_value" for trace in answer.tool_calls)
        assert answer.provenance
    finally:
        repository.close()
