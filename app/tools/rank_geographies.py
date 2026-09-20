from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.config import Settings
from app.data.errors import UnsupportedAggregationError
from app.data.models import GeoLevel
from app.data.repository import CensusRepository
from app.data.rollup import resolve_method
from app.tools.base import ToolInput
from app.tools.results import PeriodUnavailable, Success, ToolResult, UnsupportedRequest


class RankGeographiesInput(ToolInput):
    field_id: str
    level: GeoLevel
    within_geo_id: str | None = None
    vintage: int | None = None
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=10, ge=1)


class RankedGeography(BaseModel):
    geo_id: str
    name: str
    value: float


class RankGeographiesSuccess(BaseModel):
    field_id: str
    level: GeoLevel
    vintage: int
    rankings: list[RankedGeography]


class RankGeographiesTool:
    name = "rank_geographies"
    input_model = RankGeographiesInput

    def __init__(self, settings: Settings, description: str) -> None:
        self.description = description
        self._settings = settings

    def run(self, repository: CensusRepository, input: BaseModel) -> ToolResult:
        payload = RankGeographiesInput.model_validate(input)
        provenance = []
        variable_result = repository.get_variable(payload.field_id)
        provenance.append(variable_result.provenance)
        if not variable_result.rows:
            return UnsupportedRequest(reason=f"Unknown field id: {payload.field_id}")
        variable = variable_result.rows[0]
        try:
            resolve_method(variable.aggregation_kind, payload.level)
        except UnsupportedAggregationError:
            return UnsupportedRequest(
                reason=(
                    f"{variable.aggregation_kind.value} fields cannot be ranked at "
                    f"{payload.level.value} level."
                )
            )
        selected_vintage = payload.vintage or repository.get_latest_vintage(payload.field_id)
        if selected_vintage is None:
            return PeriodUnavailable(requested=str(payload.vintage or "latest"), available=[])
        limit = min(payload.limit, self._settings.tool_rank_limit_max)
        ranking = repository.rank_geographies(
            payload.field_id,
            payload.level,
            selected_vintage,
            payload.within_geo_id,
            descending=payload.order == "desc",
            limit=limit,
        )
        provenance.append(ranking.provenance)
        names = repository.get_geographies([observation.geo_id for observation in ranking.rows])
        provenance.append(names.provenance)
        name_by_id = {geography.geo_id: geography.name for geography in names.rows}
        rankings = [
            RankedGeography(
                geo_id=observation.geo_id,
                name=name_by_id.get(observation.geo_id, observation.geo_id),
                value=observation.value,
            )
            for observation in ranking.rows
        ]
        return Success(
            data=RankGeographiesSuccess(
                field_id=variable.field_id,
                level=payload.level,
                vintage=selected_vintage,
                rankings=rankings,
            ),
            provenance=provenance,
        )
