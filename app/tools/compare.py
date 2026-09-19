from __future__ import annotations

from pydantic import BaseModel, Field

from app.config import Settings
from app.data.repository import CensusRepository
from app.tools.base import ToolInput
from app.tools.results import PeriodUnavailable, Success, ToolResult, UnsupportedRequest


class CompareInput(ToolInput):
    field_id: str
    geo_ids: list[str] = Field(min_length=2)
    vintage: int | None = None


class ComparedGeography(BaseModel):
    geo_id: str
    geography_name: str
    value: float


class CompareSuccess(BaseModel):
    field_id: str
    vintage: int
    geographies: list[ComparedGeography]
    absolute_difference: float
    relative_difference: float | None


class CompareTool:
    name = "compare"
    input_model = CompareInput

    def __init__(self, settings: Settings, description: str) -> None:
        self.description = description
        self._settings = settings

    def run(self, repository: CensusRepository, input: BaseModel) -> ToolResult:
        payload = CompareInput.model_validate(input)
        if len(payload.geo_ids) > self._settings.tool_compare_max_geographies:
            return UnsupportedRequest(
                reason=(
                    f"compare supports at most {self._settings.tool_compare_max_geographies} "
                    "geographies."
                )
            )
        provenance = []
        variable_result = repository.get_variable(payload.field_id)
        provenance.append(variable_result.provenance)
        if not variable_result.rows:
            return UnsupportedRequest(reason=f"Unknown field id: {payload.field_id}")
        available_by_geo = {
            geo_id: repository.available_vintages(payload.field_id, geo_id)
            for geo_id in payload.geo_ids
        }
        if payload.vintage is not None:
            missing = [
                geo_id
                for geo_id, vintages in available_by_geo.items()
                if payload.vintage not in vintages
            ]
            if missing:
                return PeriodUnavailable(
                    requested=str(payload.vintage),
                    available=[
                        f"{geo_id}: {', '.join(str(v) for v in available_by_geo[geo_id]) or 'none'}"
                        for geo_id in payload.geo_ids
                    ],
                )
            selected_vintage = payload.vintage
        else:
            common = set.intersection(*[set(vintages) for vintages in available_by_geo.values()])
            if not common:
                return PeriodUnavailable(
                    requested="common vintage",
                    available=[
                        f"{geo_id}: {', '.join(str(v) for v in available_by_geo[geo_id]) or 'none'}"
                        for geo_id in payload.geo_ids
                    ],
                )
            selected_vintage = max(common)
        observations = repository.get_observations(
            payload.field_id,
            payload.geo_ids,
            selected_vintage,
        )
        provenance.append(observations.provenance)
        observation_by_geo = {row.geo_id: row for row in observations.rows}
        compared: list[ComparedGeography] = []
        for geo_id in payload.geo_ids:
            observation = observation_by_geo.get(geo_id)
            if observation is None:
                return PeriodUnavailable(
                    requested=str(selected_vintage),
                    available=[
                        f"{geo_id}: {', '.join(str(v) for v in available_by_geo[geo_id]) or 'none'}"
                        for geo_id in payload.geo_ids
                    ],
                )
            geography_result = repository.get_geography(geo_id)
            provenance.append(geography_result.provenance)
            compared.append(
                ComparedGeography(
                    geo_id=geo_id,
                    geography_name=(
                        geography_result.rows[0].name if geography_result.rows else geo_id
                    ),
                    value=observation.value,
                )
            )
        first_value = compared[0].value
        second_value = compared[1].value
        absolute_difference = second_value - first_value
        relative_difference = absolute_difference / first_value if first_value != 0 else None
        return Success(
            data=CompareSuccess(
                field_id=payload.field_id,
                vintage=selected_vintage,
                geographies=compared,
                absolute_difference=absolute_difference,
                relative_difference=relative_difference,
            ),
            provenance=provenance,
        )
