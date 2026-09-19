from __future__ import annotations

from pydantic import BaseModel

from app.config import Settings
from app.data.errors import UnsupportedAggregationError
from app.data.repository import CensusRepository
from app.data.rollup import resolve_method
from app.tools.base import ToolInput
from app.tools.results import PeriodUnavailable, Success, ToolResult, UnsupportedRequest


class GetValueInput(ToolInput):
    field_id: str
    geo_id: str
    vintage: int | None = None


class GetValueSuccess(BaseModel):
    field_id: str
    field_name: str
    geo_id: str
    geography_name: str
    vintage: int
    value: float
    aggregation_kind: str
    aggregation_method: str


class GetValueTool:
    name = "get_value"
    input_model = GetValueInput

    def __init__(self, settings: Settings, description: str) -> None:
        self.description = description
        self._settings = settings

    def run(self, repository: CensusRepository, input: BaseModel) -> ToolResult:
        payload = GetValueInput.model_validate(input)
        provenance = []
        variable_result = repository.get_variable(payload.field_id)
        provenance.append(variable_result.provenance)
        if not variable_result.rows:
            return UnsupportedRequest(reason=f"Unknown field id: {payload.field_id}")
        variable = variable_result.rows[0]
        geography_result = repository.get_geography(payload.geo_id)
        provenance.append(geography_result.provenance)
        if not geography_result.rows:
            return UnsupportedRequest(reason=f"Unknown geography id: {payload.geo_id}")
        geography = geography_result.rows[0]
        try:
            resolve_method(variable.aggregation_kind, geography.level)
        except UnsupportedAggregationError:
            return UnsupportedRequest(
                reason=(
                    f"{variable.aggregation_kind.value} fields are available only at block-group "
                    f"level; {geography.level.value} is not supported."
                )
            )
        available = repository.available_vintages(payload.field_id, payload.geo_id)
        if payload.vintage is not None and payload.vintage not in available:
            return PeriodUnavailable(
                requested=str(payload.vintage),
                available=[str(vintage) for vintage in available],
            )
        selected_vintage = payload.vintage or repository.get_latest_vintage(payload.field_id)
        if selected_vintage is None:
            return PeriodUnavailable(requested=str(payload.vintage or "latest"), available=[])
        observations = repository.get_observations(
            payload.field_id,
            [payload.geo_id],
            selected_vintage,
        )
        provenance.append(observations.provenance)
        if not observations.rows:
            return PeriodUnavailable(
                requested=str(selected_vintage),
                available=[str(vintage) for vintage in available],
            )
        observation = observations.rows[0]
        return Success(
            data=GetValueSuccess(
                field_id=variable.field_id,
                field_name=variable.name,
                geo_id=geography.geo_id,
                geography_name=geography.name,
                vintage=observation.vintage,
                value=observation.value,
                aggregation_kind=variable.aggregation_kind.value,
                aggregation_method=observations.provenance.aggregation_method.value,
            ),
            provenance=provenance,
        )
