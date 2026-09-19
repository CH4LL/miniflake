from __future__ import annotations

from dataclasses import dataclass

from app.agent.loop import AgentLoop
from app.config import Settings
from app.conversation.memory_store import InMemoryConversationStore
from app.conversation.service import ConversationService
from app.data.repository import CensusRepository
from app.data.snowflake_repository import SnowflakeCensusRepository
from app.llm.anthropic_client import AnthropicLLMClient
from app.llm.client import LLMClient
from app.tools.registry import ToolRegistry, default_registry


@dataclass
class AppContainer:
    settings: Settings
    repository: CensusRepository
    llm: LLMClient
    registry: ToolRegistry
    store: InMemoryConversationStore
    service: ConversationService


def build_container(settings: Settings) -> AppContainer:
    repository = SnowflakeCensusRepository(settings)
    llm = AnthropicLLMClient(settings)
    registry = default_registry(settings)
    store = InMemoryConversationStore(settings)
    loop = AgentLoop(llm, registry, repository, settings)
    service = ConversationService(settings, store, loop)
    return AppContainer(
        settings=settings,
        repository=repository,
        llm=llm,
        registry=registry,
        store=store,
        service=service,
    )
