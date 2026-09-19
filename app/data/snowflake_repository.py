from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings
from app.data.catalog import (
    build_state_names_values_sql,
    load_state_fips_names,
    load_variable_catalog_spec,
    variable_from_metadata_row,
)
from app.data.errors import RepositoryError
from app.data.execute_guard import (
    assert_read_only,
    clamp_limit,
    execute_with_retry,
    is_transient_snowflake_error,
)
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
    resolve_method,
    rollup_group_expression,
    series_prefix_from_field_id,
)
from app.data.sql_loader import (
    expand_in_list,
    load_sql_template,
    quote_identifier,
    render_sql_template,
)
from scripts.discover_schema import connect_snowflake

SQL_DIR = Path(__file__).resolve().parent / "sql"
BLOCK_GROUP_COLUMN = "CENSUS_BLOCK_GROUP"


class SnowflakeCensusRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._connection = None
        self._catalog = load_variable_catalog_spec(self._settings.variable_catalog_spec_file())
        self._state_names = load_state_fips_names(self._settings.state_fips_names_file())
        self._state_names_values = build_state_names_values_sql(self._state_names)

    def search_geographies(
        self, query: str, level: GeoLevel | None, limit: int
    ) -> QueryResult[Geography]:
        vintage = self._settings.acs_vintages[-1]
        sql = render_sql_template(
            load_sql_template(SQL_DIR / "search_geographies.sql"),
            identifiers={
                "fips_table": self._settings.metadata_fips_codes_table(vintage),
                "geographic_data_table": self._settings.metadata_geographic_data_table(vintage),
            },
            fragments={
                "state_names_values": self._state_names_values,
                "nation_geo_id": self._settings.nation_geo_id,
            },
        )
        params = {
            "query": query,
            "level": level.value if level else None,
            "limit": clamp_limit(limit, self._settings.snowflake_max_rows),
        }
        rows, provenance = self._execute_query(sql, params, AggregationMethod.DIRECT)
        geographies = [
            Geography(
                geo_id=str(row[0]),
                name=str(row[1]),
                level=GeoLevel(str(row[2])),
                parent_geo_id=str(row[3]) if row[3] is not None else None,
                state_abbreviation=str(row[4]) if row[4] is not None else None,
            )
            for row in rows
        ]
        return QueryResult(rows=geographies, provenance=provenance)

    def get_geography(self, geo_id: str) -> QueryResult[Geography]:
        level = level_for_geo_id(geo_id, self._settings.nation_geo_id)
        vintage = self._settings.acs_vintages[-1]
        sql = render_sql_template(
            load_sql_template(SQL_DIR / "get_geography.sql"),
            identifiers={
                "fips_table": self._settings.metadata_fips_codes_table(vintage),
                "geographic_data_table": self._settings.metadata_geographic_data_table(vintage),
            },
            fragments={
                "state_names_values": self._state_names_values,
                "nation_geo_id": self._settings.nation_geo_id,
                "geo_predicate": self._geo_predicate(geo_id, level),
            },
        )
        rows, provenance = self._execute_query(sql, {}, AggregationMethod.DIRECT)
        geographies = [
            Geography(
                geo_id=str(row[0]),
                name=str(row[1]),
                level=GeoLevel(str(row[2])),
                parent_geo_id=str(row[3]) if row[3] is not None else None,
                state_abbreviation=str(row[4]) if row[4] is not None else None,
            )
            for row in rows
        ]
        return QueryResult(rows=geographies, provenance=provenance)

    def search_variables(self, query: str, topic: str | None, limit: int) -> QueryResult[Variable]:
        vintage = self._settings.acs_vintages[-1]
        sql = render_sql_template(
            load_sql_template(SQL_DIR / "search_variables.sql"),
            identifiers={
                "metadata_table": self._settings.metadata_field_descriptions_table(vintage),
            },
        )
        params = {
            "series_ids": self._catalog.series_ids,
            "query": query,
            "topic": topic,
            "limit": clamp_limit(limit, self._settings.snowflake_max_rows),
        }
        rows, provenance = self._execute_query(sql, params, AggregationMethod.DIRECT)
        variables = [self._variable_from_row(row, vintage) for row in rows]
        return QueryResult(rows=variables, provenance=provenance)

    def get_variable(self, field_id: str) -> QueryResult[Variable]:
        vintage = self._settings.acs_vintages[-1]
        sql = render_sql_template(
            load_sql_template(SQL_DIR / "get_variable.sql"),
            identifiers={
                "metadata_table": self._settings.metadata_field_descriptions_table(vintage),
            },
        )
        params = {"field_id": normalize_field_id(field_id), "series_ids": self._catalog.series_ids}
        rows, provenance = self._execute_query(sql, params, AggregationMethod.DIRECT)
        variables = [self._variable_from_row(row, vintage) for row in rows]
        return QueryResult(rows=variables, provenance=provenance)

    def get_observations(
        self, field_id: str, geo_ids: list[str], vintage: int | None
    ) -> QueryResult[Observation]:
        field_id = normalize_field_id(field_id)
        variable = self._require_variable(field_id)
        selected_vintage = vintage or self.get_latest_vintage(field_id)
        if selected_vintage is None:
            raise RepositoryError(f"No vintage available for {field_id}")
        observations: list[Observation] = []
        provenance: Provenance | None = None
        block_groups_aggregated = 0
        method = AggregationMethod.DIRECT
        for geo_id in geo_ids:
            level = level_for_geo_id(geo_id, self._settings.nation_geo_id)
            method = resolve_method(variable.aggregation_kind, level)
            if method == AggregationMethod.DIRECT:
                rows, prov = self._fetch_direct(field_id, [geo_id], selected_vintage)
                provenance = prov
                observations.extend(
                    Observation(
                        geo_id=str(row[0]),
                        field_id=field_id,
                        vintage=selected_vintage,
                        value=float(row[1]),
                    )
                    for row in rows
                )
            else:
                rows, prov = self._fetch_rollup(field_id, geo_id, level, selected_vintage, limit=1)
                provenance = prov
                for row in rows:
                    block_groups_aggregated += int(row[2])
                    observations.append(
                        Observation(
                            geo_id=str(row[0]),
                            field_id=field_id,
                            vintage=selected_vintage,
                            value=float(row[1]),
                        )
                    )
        if provenance is None:
            raise RepositoryError("No observations returned")
        provenance.aggregation_method = method
        provenance.block_groups_aggregated = block_groups_aggregated or None
        return QueryResult(rows=observations, provenance=provenance)

    def get_latest_vintage(self, field_id: str) -> int | None:
        vintages = self._column_vintages(normalize_field_id(field_id))
        return max(vintages) if vintages else None

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
        group_expression = rollup_group_expression(BLOCK_GROUP_COLUMN, level)
        parent_filter = self._parent_filter(parent_geo_id, level)
        order_direction = "DESC" if descending else "ASC"
        sql = render_sql_template(
            load_sql_template(SQL_DIR / "rank_geographies_rollup.sql"),
            identifiers={"wide_table": self._wide_table(field_id, vintage)},
            fragments={
                "column_name": quote_identifier(field_id),
                "group_expression": group_expression,
                "parent_filter": parent_filter,
                "order_direction": order_direction,
            },
        )
        params = {"limit": clamp_limit(limit, self._settings.snowflake_max_rows)}
        rows, provenance = self._execute_query(
            sql,
            params,
            AggregationMethod.SUM if level != GeoLevel.BLOCK_GROUP else AggregationMethod.DIRECT,
        )
        observations = [
            Observation(
                geo_id=str(row[0]),
                field_id=field_id,
                vintage=vintage,
                value=float(row[1]),
            )
            for row in rows
        ]
        if rows:
            provenance.block_groups_aggregated = sum(int(row[2]) for row in rows)
        return QueryResult(rows=observations, provenance=provenance)

    def get_time_series(self, field_id: str, geo_id: str) -> QueryResult[Observation]:
        field_id = normalize_field_id(field_id)
        variable = self._require_variable(field_id)
        level = level_for_geo_id(geo_id, self._settings.nation_geo_id)
        method = resolve_method(variable.aggregation_kind, level)
        fragments = []
        for vintage in self._column_vintages(field_id):
            if method == AggregationMethod.DIRECT:
                fragments.append(
                    render_sql_template(
                        load_sql_template(SQL_DIR / "get_time_series.sql"),
                        identifiers={"wide_table": self._wide_table(field_id, vintage)},
                        fragments={
                            "vintage": str(vintage),
                            "block_group_column": BLOCK_GROUP_COLUMN,
                            "column_name": quote_identifier(field_id),
                        },
                    )
                )
            else:
                group_expression = rollup_group_expression(BLOCK_GROUP_COLUMN, level)
                parent_filter, having_clause = self._rollup_geo_filters(geo_id, level)
                fragments.append(
                    render_sql_template(
                        load_sql_template(SQL_DIR / "get_time_series_rollup.sql"),
                        identifiers={"wide_table": self._wide_table(field_id, vintage)},
                        fragments={
                            "vintage": str(vintage),
                            "column_name": quote_identifier(field_id),
                            "group_expression": group_expression,
                            "parent_filter": parent_filter,
                            "having_clause": having_clause,
                        },
                    )
                )
        if not fragments:
            return QueryResult(
                rows=[],
                provenance=self._empty_provenance(
                    "get_time_series", {"field_id": field_id, "geo_id": geo_id}
                ),
            )
        sql = " UNION ALL ".join(fragments) + " ORDER BY vintage"
        params = {"geo_id": geo_id} if method == AggregationMethod.DIRECT else {}
        if method == AggregationMethod.DIRECT:
            aggregation_method = AggregationMethod.DIRECT
        else:
            aggregation_method = AggregationMethod.SUM
        rows, provenance = self._execute_query(sql, params, aggregation_method)
        observations = [
            Observation(
                geo_id=str(row[1]),
                field_id=field_id,
                vintage=int(row[0]),
                value=float(row[2]),
            )
            for row in rows
        ]
        if method == AggregationMethod.SUM and rows:
            provenance.block_groups_aggregated = sum(int(row[3]) for row in rows)
        return QueryResult(rows=observations, provenance=provenance)

    def available_vintages(self, field_id: str, geo_id: str) -> list[int]:
        field_id = normalize_field_id(field_id)
        level = level_for_geo_id(geo_id, self._settings.nation_geo_id)
        if level == GeoLevel.BLOCK_GROUP:
            series = self.get_time_series(field_id, geo_id)
            return [observation.vintage for observation in series.rows]
        return self._column_vintages(field_id)

    def _require_variable(self, field_id: str) -> Variable:
        result = self.get_variable(field_id)
        if not result.rows:
            raise RepositoryError(f"Unknown field id: {field_id}")
        return result.rows[0]

    def _variable_from_row(self, row: tuple[Any, ...], vintage: int) -> Variable:
        metadata = {
            "field_id": row[0],
            "table_id": row[1],
            "series_id": row[2],
            "name": row[3],
            "description": row[4],
            "topic": row[5],
        }
        table_name = self._wide_table(str(row[0]), vintage)
        return variable_from_metadata_row(
            metadata,
            catalog=self._catalog,
            vintage=vintage,
            settings_table_name=table_name,
        )

    def _wide_table(self, field_id: str, vintage: int) -> str:
        prefix = series_prefix_from_field_id(field_id)
        return self._settings.acs_wide_table_name(vintage, prefix)

    def _geo_predicate(self, geo_id: str, level: GeoLevel) -> str:
        if level == GeoLevel.NATION:
            return f"geo_id = '{self._settings.nation_geo_id}'"
        return f"geo_id = '{geo_id}'"

    def _rollup_geo_filters(self, geo_id: str, level: GeoLevel) -> tuple[str, str]:
        quoted = quote_identifier(BLOCK_GROUP_COLUMN)
        group_expression = rollup_group_expression(BLOCK_GROUP_COLUMN, level)
        if level == GeoLevel.NATION:
            parent_filter = ""
            having_clause = ""
        elif level == GeoLevel.STATE:
            parent_filter = f"AND LEFT({quoted}, 2) = '{geo_id}'"
            having_clause = f"HAVING {group_expression} = '{geo_id}'"
        elif level == GeoLevel.COUNTY:
            parent_filter = f"AND LEFT({quoted}, 5) = '{geo_id}'"
            having_clause = f"HAVING {group_expression} = '{geo_id}'"
        else:
            parent_filter = ""
            having_clause = ""
        return parent_filter, having_clause

    def _parent_filter(self, parent_geo_id: str | None, level: GeoLevel) -> str:
        if parent_geo_id is None or level == GeoLevel.NATION:
            return ""
        quoted = quote_identifier(BLOCK_GROUP_COLUMN)
        if level == GeoLevel.STATE:
            return ""
        if level == GeoLevel.COUNTY:
            return f"AND LEFT({quoted}, 2) = '{parent_geo_id}'"
        if level == GeoLevel.BLOCK_GROUP:
            return f"AND LEFT({quoted}, 5) = '{parent_geo_id}'"
        return ""

    def _fetch_direct(
        self, field_id: str, geo_ids: list[str], vintage: int
    ) -> tuple[list[tuple[Any, ...]], Provenance]:
        sql = render_sql_template(
            load_sql_template(SQL_DIR / "get_observation_block_group.sql"),
            identifiers={
                "wide_table": self._wide_table(field_id, vintage),
                "block_group_column": BLOCK_GROUP_COLUMN,
            },
            fragments={"column_name": quote_identifier(field_id)},
        )
        params = {
            "geo_ids": geo_ids,
            "limit": clamp_limit(len(geo_ids), self._settings.snowflake_max_rows),
        }
        return self._execute_query(sql, params, AggregationMethod.DIRECT)

    def _fetch_rollup(
        self,
        field_id: str,
        geo_id: str,
        level: GeoLevel,
        vintage: int,
        *,
        limit: int,
    ) -> tuple[list[tuple[Any, ...]], Provenance]:
        group_expression = rollup_group_expression(BLOCK_GROUP_COLUMN, level)
        quoted = quote_identifier(BLOCK_GROUP_COLUMN)
        if level == GeoLevel.NATION:
            parent_filter = ""
        elif level == GeoLevel.STATE:
            parent_filter = f"AND LEFT({quoted}, 2) = '{geo_id}'"
        elif level == GeoLevel.COUNTY:
            parent_filter = f"AND LEFT({quoted}, 5) = '{geo_id}'"
        else:
            parent_filter = ""
        if level in {GeoLevel.STATE, GeoLevel.COUNTY}:
            having_clause = f"HAVING {group_expression} = '{geo_id}'"
        else:
            having_clause = ""
        sql = render_sql_template(
            load_sql_template(SQL_DIR / "get_observation_rollup.sql"),
            identifiers={"wide_table": self._wide_table(field_id, vintage)},
            fragments={
                "column_name": quote_identifier(field_id),
                "group_expression": group_expression,
                "parent_filter": parent_filter,
                "having_clause": having_clause,
            },
        )
        params = {"limit": clamp_limit(limit, self._settings.snowflake_max_rows)}
        return self._execute_query(sql, params, AggregationMethod.SUM)

    def _column_vintages(self, field_id: str) -> list[int]:
        vintage_union = self._vintage_union_for_field(field_id)
        if not vintage_union:
            return []
        sql = render_sql_template(
            load_sql_template(SQL_DIR / "available_vintages.sql"),
            fragments={"vintage_union": vintage_union},
        )
        rows, _ = self._execute_query(
            sql,
            {
                "field_id": field_id,
                "database": self._settings.snowflake_database,
                "schema": self._settings.snowflake_schema,
            },
            AggregationMethod.DIRECT,
        )
        return [int(row[0]) for row in rows]

    def _vintage_union_for_field(self, field_id: str) -> str:
        prefix = series_prefix_from_field_id(field_id)
        parts = []
        for vintage in self._settings.acs_vintages:
            table = self._settings.acs_wide_table_name(vintage, prefix)
            parts.append(
                f"SELECT {vintage} AS vintage WHERE EXISTS ("
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_catalog = %(database)s "
                "AND table_schema = %(schema)s "
                f"AND table_name = '{table}' "
                "AND column_name = %(field_id)s)"
            )
        return " UNION ALL ".join(parts)

    def _connection_or_open(self):
        if self._connection is None or getattr(self._connection, "is_closed", False):
            self._connection = connect_snowflake(self._settings)
            cursor = self._connection.cursor()
            try:
                cursor.execute(
                    f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = "
                    f"{self._settings.snowflake_statement_timeout_seconds}"
                )
                cursor.execute(
                    f"ALTER SESSION SET QUERY_TAG = '{self._settings.snowflake_query_tag}'"
                )
            finally:
                cursor.close()
        return self._connection

    def _execute_query(
        self,
        sql: str,
        params: dict[str, Any],
        aggregation_method: AggregationMethod,
    ) -> tuple[list[tuple[Any, ...]], Provenance]:
        assert_read_only(sql)
        expanded_sql, expanded_params = expand_in_list(sql, params)

        def operation() -> tuple[list[tuple[Any, ...]], float]:
            connection = self._connection_or_open()
            cursor = connection.cursor()
            start = time.perf_counter()
            try:
                cursor.execute(expanded_sql, expanded_params)
                rows = cursor.fetchall()
            finally:
                cursor.close()
            duration_ms = (time.perf_counter() - start) * 1000
            return rows, duration_ms

        rows, duration_ms = execute_with_retry(
            operation,
            attempts=self._settings.snowflake_retry_attempts,
            backoff_seconds=self._settings.snowflake_retry_backoff_seconds,
            is_transient=is_transient_snowflake_error,
        )
        provenance = Provenance(
            sql=expanded_sql,
            parameters=expanded_params,
            row_count=len(rows),
            source="snowflake",
            executed_at=datetime.now(UTC),
            duration_ms=duration_ms,
            aggregation_method=aggregation_method,
        )
        return rows, provenance

    def _empty_provenance(self, operation: str, parameters: dict[str, Any]) -> Provenance:
        return Provenance(
            sql=f"snowflake://{operation}",
            parameters=parameters,
            row_count=0,
            source="snowflake",
            executed_at=datetime.now(UTC),
            duration_ms=0.0,
            aggregation_method=AggregationMethod.DIRECT,
        )

    def close(self) -> None:
        if self._connection is not None and not getattr(self._connection, "is_closed", True):
            self._connection.close()
        self._connection = None
