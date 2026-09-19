from __future__ import annotations

from typing import Protocol

from app.data.models import Geography, GeoLevel, Observation, QueryResult, Variable


class CensusRepository(Protocol):
    def search_geographies(
        self, query: str, level: GeoLevel | None, limit: int
    ) -> QueryResult[Geography]: ...

    def get_geography(self, geo_id: str) -> QueryResult[Geography]: ...

    def search_variables(
        self, query: str, topic: str | None, limit: int
    ) -> QueryResult[Variable]: ...

    def get_variable(self, field_id: str) -> QueryResult[Variable]: ...

    def get_observations(
        self, field_id: str, geo_ids: list[str], vintage: int | None
    ) -> QueryResult[Observation]: ...

    def get_latest_vintage(self, field_id: str) -> int | None: ...

    def rank_geographies(
        self,
        field_id: str,
        level: GeoLevel,
        vintage: int,
        parent_geo_id: str | None,
        descending: bool,
        limit: int,
    ) -> QueryResult[Observation]: ...

    def get_time_series(self, field_id: str, geo_id: str) -> QueryResult[Observation]: ...

    def available_vintages(self, field_id: str, geo_id: str) -> list[int]: ...
