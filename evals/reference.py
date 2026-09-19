from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

from evals.loader import EvalItem


class ReferenceTarget(BaseModel):
    field_id: str
    geo_id: str
    vintage: int | None = None


class ReferenceSource(Protocol):
    def fetch_value(self, target: ReferenceTarget) -> float | None: ...


def resolve_target(item: EvalItem, response: dict[str, Any]) -> ReferenceTarget | None:
    if item.value_check is None:
        return None
    if item.value_check.field_id and item.value_check.geo_id:
        return ReferenceTarget(
            field_id=item.value_check.field_id,
            geo_id=item.value_check.geo_id,
            vintage=item.value_check.vintage,
        )
    for tool_call in response.get("tool_calls") or []:
        if tool_call.get("result_kind") != "success":
            continue
        if tool_call.get("name") != "get_value":
            continue
        data = tool_call.get("data") or {}
        field_id = data.get("field_id")
        geo_id = data.get("geo_id")
        if not isinstance(field_id, str) or not isinstance(geo_id, str):
            continue
        vintage = data.get("vintage")
        return ReferenceTarget(
            field_id=field_id,
            geo_id=geo_id,
            vintage=vintage if isinstance(vintage, int) else item.value_check.vintage,
        )
    return None


class RepositoryReference:
    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def fetch_value(self, target: ReferenceTarget) -> float | None:
        vintage = target.vintage
        if vintage is None:
            vintage = self._repository.get_latest_vintage(target.field_id)
        if vintage is None:
            return None
        result = self._repository.get_observations(target.field_id, [target.geo_id], vintage)
        if not result.rows:
            return None
        return float(result.rows[0].value)


def build_snowflake_reference() -> RepositoryReference:
    from app.config import get_settings
    from app.data.snowflake_repository import SnowflakeCensusRepository

    return RepositoryReference(SnowflakeCensusRepository(get_settings()))
