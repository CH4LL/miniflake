from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class GeoLevel(StrEnum):
    BLOCK_GROUP = "BlockGroup"
    NATION = "Nation"
    STATE = "State"
    COUNTY = "County"


class AggregationKind(StrEnum):
    COUNT = "count"
    MEDIAN = "median"
    RATE = "rate"


class AggregationMethod(StrEnum):
    DIRECT = "direct"
    SUM = "sum"


class Geography(BaseModel):
    geo_id: str
    name: str
    level: GeoLevel
    parent_geo_id: str | None = None
    state_abbreviation: str | None = None


class Variable(BaseModel):
    field_id: str
    table_id: str
    series_id: str
    name: str
    topic: str
    aggregation_kind: AggregationKind
    description: str | None = None
    acs_table_name: str | None = None


class Observation(BaseModel):
    geo_id: str
    field_id: str
    vintage: int
    value: float


class Provenance(BaseModel):
    sql: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    row_count: int
    source: str
    executed_at: datetime
    duration_ms: float
    aggregation_method: AggregationMethod
    block_groups_aggregated: int | None = None


class QueryResult[T](BaseModel):
    rows: list[T]
    provenance: Provenance
