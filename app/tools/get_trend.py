from __future__ import annotations

from pydantic import BaseModel

from app.config import Settings
from app.data.errors import UnsupportedAggregationError
from app.data.repository import CensusRepository
from app.data.rollup import level_for_geo_id, resolve_method
from app.tools.base import ToolInput, measurement_period_note
from app.tools.results import PeriodUnavailable, Success, ToolResult, UnsupportedRequest


class GetTrendInput(ToolInput):
    field_id: str
    geo_id: str
    start_year: int | None = None
    end_year: int | None = None


class TrendPoint(BaseModel):
    vintage: int
    value: float


class GetTrendSuccess(BaseModel):
    field_id: str
    geo_id: str
    aggregation_method: str
    measurement_period_note: str
    points: list[TrendPoint]


class GetTrendTool:
    name = "get_trend"
    input_model = GetTrendInput

    def __init__(self, settings: Settings, description: str) -> None:
        self.description = description
        self._settings = settings

    def run(self, repository: CensusRepository, input: BaseModel) -> ToolResult:
        payload = GetTrendInput.model_validate(input)
        variable_result = repository.get_variable(payload.field_id)
        provenance = [variable_result.provenance]
        if not variable_result.rows:
            return UnsupportedRequest(reason=f"Unknown field id: {payload.field_id}")
        variable = variable_result.rows[0]
        level = level_for_geo_id(payload.geo_id, self._settings.nation_geo_id)
        try:
            resolve_method(variable.aggregation_kind, level)
        except UnsupportedAggregationError:
            return UnsupportedRequest(
                reason=(
                    f"{variable.aggregation_kind.value} trends are available only at block-group "
                    f"level; {level.value} is not supported."
                )
            )
        series = repository.get_time_series(payload.field_id, payload.geo_id)
        provenance.append(series.provenance)
        available = [str(point.vintage) for point in series.rows]
        filtered = [
            point
            for point in series.rows
            if (payload.start_year is None or point.vintage >= payload.start_year)
            and (payload.end_year is None or point.vintage <= payload.end_year)
        ]
        if series.rows and not filtered:
            requested = _requested_range(payload.start_year, payload.end_year)
            return PeriodUnavailable(requested=requested, available=available)
        return Success(
            data=GetTrendSuccess(
                field_id=variable.field_id,
                geo_id=payload.geo_id,
                aggregation_method=series.provenance.aggregation_method.value,
                measurement_period_note=measurement_period_note(),
                points=[TrendPoint(vintage=point.vintage, value=point.value) for point in filtered],
            ),
            provenance=provenance,
        )


def _requested_range(start_year: int | None, end_year: int | None) -> str:
    if start_year is not None and end_year is not None:
        return f"{start_year}-{end_year}"
    if start_year is not None:
        return f">={start_year}"
    if end_year is not None:
        return f"<={end_year}"
    return "requested range"
