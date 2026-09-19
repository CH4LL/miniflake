from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.data.catalog import VariableCatalogSpec, load_variable_catalog_spec
from app.data.errors import RepositoryError
from app.data.models import (
    AggregationMethod,
    Geography,
    GeoLevel,
    Observation,
    Provenance,
    QueryResult,
    Variable,
)
from app.data.rollup import (
    level_for_geo_id,
    normalize_field_id,
    prefix_length,
    resolve_method,
)
from app.data.search_utils import match_rank, matches_query


class FakeCensusRepository:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        fixtures_dir: Path | None = None,
        catalog: VariableCatalogSpec | None = None,
        nation_geo_id: str | None = None,
    ) -> None:
        self._settings = settings
        self._nation_geo_id = nation_geo_id or (
            settings.nation_geo_id if settings is not None else "US"
        )
        base = fixtures_dir
        if base is None:
            base = settings.fixtures_path() if settings is not None else Path("fixtures")
        catalog_path = (
            settings.variable_catalog_spec_file()
            if settings is not None
            else base.parent / "variable_catalog_spec.yaml"
        )
        if not catalog_path.exists():
            catalog_path = Path("fixtures/variable_catalog_spec.yaml")
        self._catalog = catalog or load_variable_catalog_spec(catalog_path)
        geographies = json.loads((base / "geographies.json").read_text(encoding="utf-8"))
        self._geographies: list[Geography] = []
        nation = geographies["nation"]
        self._geographies.append(Geography(**nation))
        for item in geographies.get("states", []):
            self._geographies.append(Geography(**item))
        for item in geographies.get("counties", []):
            self._geographies.append(Geography(**item))
        for item in geographies.get("block_groups", []):
            self._geographies.append(Geography(**item))
        self._geography_by_id = {geo.geo_id: geo for geo in self._geographies}
        self._variables = [
            Variable.model_validate(item)
            for item in json.loads((base / "variables.json").read_text(encoding="utf-8"))
        ]
        self._variable_by_id = {
            normalize_field_id(variable.field_id): variable for variable in self._variables
        }
        self._observations = [
            Observation.model_validate(
                {**item, "field_id": normalize_field_id(str(item["field_id"]))}
            )
            for item in json.loads((base / "sample_observations.json").read_text(encoding="utf-8"))
        ]

    def search_geographies(
        self, query: str, level: GeoLevel | None, limit: int
    ) -> QueryResult[Geography]:
        rows = [
            geo
            for geo in self._geographies
            if (level is None or geo.level == level) and matches_query(geo.name, query)
        ]
        rows.sort(key=lambda geo: (match_rank(geo.name, query), geo.name.lower()))
        limited = rows[: max(limit, 1)]
        return QueryResult(
            rows=limited,
            provenance=self._provenance(
                sql="fake://search_geographies",
                parameters={"query": query, "level": level, "limit": limit},
                row_count=len(limited),
                aggregation_method=AggregationMethod.DIRECT,
            ),
        )

    def get_geography(self, geo_id: str) -> QueryResult[Geography]:
        geography = self._geography_by_id.get(geo_id)
        if geography is None:
            return QueryResult(
                rows=[],
                provenance=self._provenance(
                    sql="fake://get_geography",
                    parameters={"geo_id": geo_id},
                    row_count=0,
                    aggregation_method=AggregationMethod.DIRECT,
                ),
            )
        return QueryResult(
            rows=[geography],
            provenance=self._provenance(
                sql="fake://get_geography",
                parameters={"geo_id": geo_id},
                row_count=1,
                aggregation_method=AggregationMethod.DIRECT,
            ),
        )

    def search_variables(self, query: str, topic: str | None, limit: int) -> QueryResult[Variable]:
        rows = []
        for variable in self._variables:
            if topic and topic.lower() not in variable.topic.lower():
                continue
            searchable = " ".join(
                part
                for part in (variable.field_id, variable.name, variable.series_id, variable.topic)
                if part
            )
            if matches_query(searchable, query):
                rows.append(variable)
        rows.sort(
            key=lambda variable: (
                match_rank(variable.field_id, query),
                match_rank(variable.name, query),
                variable.field_id,
            )
        )
        limited = rows[: max(limit, 1)]
        return QueryResult(
            rows=limited,
            provenance=self._provenance(
                sql="fake://search_variables",
                parameters={"query": query, "topic": topic, "limit": limit},
                row_count=len(limited),
                aggregation_method=AggregationMethod.DIRECT,
            ),
        )

    def get_variable(self, field_id: str) -> QueryResult[Variable]:
        variable = self._variable_by_id.get(normalize_field_id(field_id))
        rows = [variable] if variable else []
        return QueryResult(
            rows=rows,
            provenance=self._provenance(
                sql="fake://get_variable",
                parameters={"field_id": field_id},
                row_count=len(rows),
                aggregation_method=AggregationMethod.DIRECT,
            ),
        )

    def get_observations(
        self, field_id: str, geo_ids: list[str], vintage: int | None
    ) -> QueryResult[Observation]:
        field_id = normalize_field_id(field_id)
        variable = self._require_variable(field_id)
        selected_vintage = vintage or self.get_latest_vintage(field_id)
        if selected_vintage is None:
            raise RepositoryError(f"No vintage available for {field_id}")
        rows: list[Observation] = []
        block_groups_aggregated = 0
        method = AggregationMethod.DIRECT
        for geo_id in geo_ids:
            level = level_for_geo_id(geo_id, self._nation_geo_id)
            method = resolve_method(variable.aggregation_kind, level)
            if method == AggregationMethod.DIRECT:
                observation = self._direct_observation(field_id, geo_id, selected_vintage)
                if observation:
                    rows.append(observation)
            else:
                value, count = self._rollup_value(field_id, geo_id, level, selected_vintage)
                block_groups_aggregated += count
                rows.append(
                    Observation(
                        geo_id=geo_id,
                        field_id=field_id,
                        vintage=selected_vintage,
                        value=value,
                    )
                )
        return QueryResult(
            rows=rows,
            provenance=self._provenance(
                sql="fake://get_observations",
                parameters={"field_id": field_id, "geo_ids": geo_ids, "vintage": selected_vintage},
                row_count=len(rows),
                aggregation_method=method,
                block_groups_aggregated=block_groups_aggregated or None,
            ),
        )

    def get_latest_vintage(self, field_id: str) -> int | None:
        vintages = sorted(
            {
                observation.vintage
                for observation in self._observations
                if observation.field_id == normalize_field_id(field_id)
            },
            reverse=True,
        )
        return vintages[0] if vintages else None

    def rank_geographies(
        self,
        field_id: str,
        level: GeoLevel,
        vintage: int,
        parent_geo_id: str | None,
        descending: bool,
        limit: int,
    ) -> QueryResult[Observation]:
        field_id = normalize_field_id(field_id)
        variable = self._require_variable(field_id)
        resolve_method(variable.aggregation_kind, level)
        candidates = [
            geo
            for geo in self._geographies
            if geo.level == level and self._within_parent(geo, parent_geo_id)
        ]
        rows: list[Observation] = []
        block_groups_aggregated = 0
        for geo in candidates:
            if level == GeoLevel.BLOCK_GROUP:
                observation = self._direct_observation(field_id, geo.geo_id, vintage)
                if observation:
                    rows.append(observation)
            else:
                value, count = self._rollup_value(field_id, geo.geo_id, level, vintage)
                block_groups_aggregated += count
                rows.append(
                    Observation(
                        geo_id=geo.geo_id,
                        field_id=field_id,
                        vintage=vintage,
                        value=value,
                    )
                )
        rows.sort(key=lambda row: row.value, reverse=descending)
        limited = rows[: max(limit, 1)]
        rank_method = (
            AggregationMethod.SUM if level != GeoLevel.BLOCK_GROUP else AggregationMethod.DIRECT
        )
        return QueryResult(
            rows=limited,
            provenance=self._provenance(
                sql="fake://rank_geographies",
                parameters={
                    "field_id": field_id,
                    "level": level,
                    "vintage": vintage,
                    "parent_geo_id": parent_geo_id,
                    "descending": descending,
                    "limit": limit,
                },
                row_count=len(limited),
                aggregation_method=rank_method,
                block_groups_aggregated=block_groups_aggregated or None,
            ),
        )

    def get_time_series(self, field_id: str, geo_id: str) -> QueryResult[Observation]:
        field_id = normalize_field_id(field_id)
        variable = self._require_variable(field_id)
        level = level_for_geo_id(geo_id, self._nation_geo_id)
        method = resolve_method(variable.aggregation_kind, level)
        if method == AggregationMethod.DIRECT:
            rows = sorted(
                [
                    observation
                    for observation in self._observations
                    if observation.field_id == field_id and observation.geo_id == geo_id
                ],
                key=lambda observation: observation.vintage,
            )
            return QueryResult(
                rows=rows,
                provenance=self._provenance(
                    sql="fake://get_time_series",
                    parameters={"field_id": field_id, "geo_id": geo_id},
                    row_count=len(rows),
                    aggregation_method=AggregationMethod.DIRECT,
                ),
            )
        rows: list[Observation] = []
        block_groups_aggregated = 0
        for vintage in self.available_vintages(field_id, geo_id):
            value, count = self._rollup_value(field_id, geo_id, level, vintage)
            block_groups_aggregated += count
            rows.append(
                Observation(
                    geo_id=geo_id,
                    field_id=field_id,
                    vintage=vintage,
                    value=value,
                )
            )
        return QueryResult(
            rows=rows,
            provenance=self._provenance(
                sql="fake://get_time_series_rollup",
                parameters={"field_id": field_id, "geo_id": geo_id},
                row_count=len(rows),
                aggregation_method=AggregationMethod.SUM,
                block_groups_aggregated=block_groups_aggregated or None,
            ),
        )

    def available_vintages(self, field_id: str, geo_id: str) -> list[int]:
        field_id = normalize_field_id(field_id)
        level = level_for_geo_id(geo_id, self._nation_geo_id)
        if level == GeoLevel.BLOCK_GROUP:
            return sorted(
                {
                    observation.vintage
                    for observation in self._observations
                    if observation.field_id == field_id and observation.geo_id == geo_id
                }
            )
        prefix_len = prefix_length(level)
        return sorted(
            {
                observation.vintage
                for observation in self._observations
                if observation.field_id == field_id
                and self._is_block_group_grain(observation.geo_id)
                and (prefix_len is None or observation.geo_id.startswith(geo_id[:prefix_len]))
            }
        )

    def _require_variable(self, field_id: str) -> Variable:
        variable = self._variable_by_id.get(normalize_field_id(field_id))
        if variable is None:
            raise RepositoryError(f"Unknown field id: {field_id}")
        return variable

    def _direct_observation(self, field_id: str, geo_id: str, vintage: int) -> Observation | None:
        for observation in self._observations:
            if (
                observation.field_id == field_id
                and observation.geo_id == geo_id
                and observation.vintage == vintage
            ):
                return observation
        return None

    @staticmethod
    def _is_block_group_grain(geo_id: str) -> bool:
        return len(geo_id) == 12 and geo_id.isdigit()

    def _rollup_value(
        self, field_id: str, geo_id: str, level: GeoLevel, vintage: int
    ) -> tuple[float, int]:
        prefix_len = prefix_length(level)
        matching = [
            observation
            for observation in self._observations
            if observation.field_id == field_id
            and observation.vintage == vintage
            and self._is_block_group_grain(observation.geo_id)
            and (prefix_len is None or observation.geo_id.startswith(geo_id[:prefix_len]))
        ]
        if not matching:
            return 0.0, 0
        return sum(item.value for item in matching), len(matching)

    def _within_parent(self, geography: Geography, parent_geo_id: str | None) -> bool:
        if parent_geo_id is None:
            return True
        if geography.level == GeoLevel.STATE:
            return parent_geo_id == self._nation_geo_id
        if geography.level == GeoLevel.COUNTY:
            return geography.parent_geo_id == parent_geo_id
        if geography.level == GeoLevel.BLOCK_GROUP:
            return geography.parent_geo_id.startswith(parent_geo_id)
        return geography.geo_id.startswith(parent_geo_id)

    def _provenance(
        self,
        *,
        sql: str,
        parameters: dict[str, object],
        row_count: int,
        aggregation_method: AggregationMethod,
        block_groups_aggregated: int | None = None,
    ) -> Provenance:
        return Provenance(
            sql=sql,
            parameters=parameters,
            row_count=row_count,
            source="fake",
            executed_at=datetime.now(UTC),
            duration_ms=0.0,
            aggregation_method=aggregation_method,
            block_groups_aggregated=block_groups_aggregated,
        )
