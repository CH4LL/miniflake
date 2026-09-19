from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.data.errors import RepositoryError, TransientRepositoryError, UnsupportedAggregationError
from app.data.repository import CensusRepository
from app.tools.base import Tool, load_tool_descriptions
from app.tools.compare import CompareTool
from app.tools.find_geography import FindGeographyTool
from app.tools.find_variable import FindVariableTool
from app.tools.get_trend import GetTrendTool
from app.tools.get_value import GetValueTool
from app.tools.rank_geographies import RankGeographiesTool
from app.tools.results import ToolError, ToolResult, UnsupportedRequest


class ToolRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._tools: dict[str, Tool] = {}
        self._disabled = {name.strip() for name in settings.disabled_tools}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool registration: {tool.name}")
        if not tool.description:
            raise ValueError(f"Missing description for tool: {tool.name}")
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        for name, tool in self._tools.items():
            if name in self._disabled:
                continue
            input_schema = tool.input_model.model_json_schema()
            input_schema["additionalProperties"] = False
            schemas.append(
                {
                    "name": name,
                    "description": tool.description,
                    "input_schema": input_schema,
                }
            )
        return schemas

    def dispatch(
        self,
        name: str,
        raw_input: dict[str, Any],
        repository: CensusRepository,
    ) -> ToolResult:
        if name not in self._tools or name in self._disabled:
            return UnsupportedRequest(reason=f"Tool is not available: {name}")
        tool = self._tools[name]
        try:
            validated = tool.input_model.model_validate(raw_input)
        except ValidationError as exc:
            return UnsupportedRequest(reason=str(exc))
        try:
            return tool.run(repository, validated)
        except UnsupportedAggregationError as exc:
            return UnsupportedRequest(reason=str(exc))
        except TransientRepositoryError as exc:
            return ToolError(message=str(exc), retryable=True)
        except RepositoryError as exc:
            return ToolError(message=str(exc), retryable=False)
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            return ToolError(message=str(exc), retryable=False)


def default_registry(settings: Settings) -> ToolRegistry:
    descriptions = load_tool_descriptions()
    registry = ToolRegistry(settings)
    registry.register(FindGeographyTool(settings, descriptions["find_geography"]))
    registry.register(FindVariableTool(settings, descriptions["find_variable"]))
    registry.register(GetValueTool(settings, descriptions["get_value"]))
    registry.register(RankGeographiesTool(settings, descriptions["rank_geographies"]))
    registry.register(GetTrendTool(settings, descriptions["get_trend"]))
    registry.register(CompareTool(settings, descriptions["compare"]))
    return registry
