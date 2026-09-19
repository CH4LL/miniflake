from __future__ import annotations

from pydantic import BaseModel

from app.config import Settings
from app.data.repository import CensusRepository
from app.tools.base import ToolInput, relaxed_variable_suggestions
from app.tools.results import Ambiguous, NotFound, Success, ToolResult


class FindVariableInput(ToolInput):
    query: str
    topic: str | None = None


class VariableCandidate(BaseModel):
    field_id: str
    name: str
    topic: str
    series_id: str


class FindVariableSuccess(BaseModel):
    candidates: list[VariableCandidate]


class FindVariableTool:
    name = "find_variable"
    input_model = FindVariableInput

    def __init__(self, settings: Settings, description: str) -> None:
        self.description = description
        self._settings = settings

    def run(self, repository: CensusRepository, input: BaseModel) -> ToolResult:
        payload = FindVariableInput.model_validate(input)
        result = repository.search_variables(
            payload.query,
            payload.topic,
            self._settings.repository_search_limit,
        )
        provenance = [result.provenance]
        rows = result.rows
        if not rows:
            return NotFound(
                what=payload.query,
                suggestions=relaxed_variable_suggestions(
                    repository,
                    payload.query,
                    limit=self._settings.tool_suggestion_limit,
                ),
            )
        series_ids = {variable.series_id for variable in rows}
        if len(series_ids) == 1:
            limited = rows[: self._settings.tool_max_variable_candidates]
            data = FindVariableSuccess(
                candidates=[
                    VariableCandidate(
                        field_id=variable.field_id,
                        name=variable.name,
                        topic=variable.topic,
                        series_id=variable.series_id,
                    )
                    for variable in limited
                ]
            )
            return Success(data=data, provenance=provenance)
        return Ambiguous(
            candidates=[
                VariableCandidate(
                    field_id=variable.field_id,
                    name=variable.name,
                    topic=variable.topic,
                    series_id=variable.series_id,
                )
                for variable in rows[: self._settings.tool_max_variable_candidates]
            ],
            hint="Candidates span different variable series; ask which measure is intended.",
        )
