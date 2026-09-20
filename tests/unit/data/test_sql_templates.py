from pathlib import Path

import pytest

from app.data.catalog import build_state_names_values_sql, load_state_fips_names
from app.data.snowflake_repository import build_search_variables_query
from app.data.sql_loader import expand_in_list, load_sql_template, render_sql_template

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SQL_DIR = PROJECT_ROOT / "app" / "data" / "sql"
STATES = load_state_fips_names(PROJECT_ROOT / "fixtures" / "state_fips_names.json")


@pytest.mark.parametrize(
    "template_name",
    [
        "search_geographies.sql",
        "get_geography.sql",
        "get_geographies.sql",
        "search_variables.sql",
        "get_variable.sql",
        "get_observation_block_group.sql",
        "get_observation_rollup.sql",
        "rank_geographies_rollup.sql",
        "get_latest_vintage.sql",
        "available_vintages.sql",
        "get_time_series.sql",
        "get_time_series_rollup.sql",
    ],
)
def test_template_loads(template_name: str) -> None:
    path = SQL_DIR / template_name
    assert path.exists()
    content = load_sql_template(path)
    assert content


def test_search_geographies_template_renders_with_binds() -> None:
    template = load_sql_template(SQL_DIR / "search_geographies.sql")
    rendered = render_sql_template(
        template,
        identifiers={
            "fips_table": "2020_METADATA_CBG_FIPS_CODES",
            "geographic_data_table": "2020_METADATA_CBG_GEOGRAPHIC_DATA",
        },
        fragments={
            "state_names_values": build_state_names_values_sql(STATES[:2]),
            "nation_geo_id": "US",
        },
    )
    assert "%(query)s" in rendered
    assert "%(level)s" in rendered
    assert "%(limit)s" in rendered
    assert "LIMIT %(limit)s" in rendered


def test_get_geographies_template_expands_in_list_everywhere() -> None:
    template = load_sql_template(SQL_DIR / "get_geographies.sql")
    rendered = render_sql_template(
        template,
        identifiers={
            "fips_table": "2020_METADATA_CBG_FIPS_CODES",
            "geographic_data_table": "2020_METADATA_CBG_GEOGRAPHIC_DATA",
        },
        fragments={
            "state_names_values": build_state_names_values_sql(STATES[:2]),
            "nation_geo_id": "US",
        },
    )
    sql, params = expand_in_list(rendered, {"geo_ids": ["48", "17031"], "limit": 2})
    assert ":in_geo_ids" not in sql
    assert sql.count("IN (%(geo_ids_0)s, %(geo_ids_1)s)") == 2
    assert params["geo_ids_1"] == "17031"


def test_search_variables_template_renders_with_in_list() -> None:
    rendered, params = build_search_variables_query(
        "2020_METADATA_CBG_FIELD_DESCRIPTIONS",
        series_ids=["B01003", "B19013"],
        query="population below poverty line",
        topic=None,
        limit=10,
        alias_series_ids=["B17001"],
    )
    sql, expanded = expand_in_list(rendered, params)
    assert "series_ids_0" in expanded
    assert "IN (%(series_ids_0)s" in sql
    assert "%(query)s" in sql
    assert "LIMIT %(limit)s" in sql
    assert expanded["token_0"] == "population"
    assert expanded["token_3"] == "line"
    where_clause = sql.split("ORDER BY", 1)[0]
    assert where_clause.count("LIKE '%%' || %(token_") == 4
    assert "%(token_3)s" in sql.split("ORDER BY", 1)[1]
    assert "OR TABLE_NUMBER IN (%(alias_series_ids_0)s)" in sql
    assert expanded["alias_series_ids_0"] == "B17001"


def test_search_variables_template_without_aliases_has_no_alias_clause() -> None:
    rendered, params = build_search_variables_query(
        "2020_METADATA_CBG_FIELD_DESCRIPTIONS",
        series_ids=["B01003"],
        query="of the",
        topic="Population",
        limit=5,
        alias_series_ids=[],
    )
    sql, expanded = expand_in_list(rendered, params)
    assert "alias_series_ids" not in sql
    assert "LOWER(%(query)s)" in sql
    assert expanded["topic"] == "Population"


def test_observation_block_group_template_renders() -> None:
    template = load_sql_template(SQL_DIR / "get_observation_block_group.sql")
    rendered = render_sql_template(
        template,
        identifiers={
            "block_group_column": "CENSUS_BLOCK_GROUP",
            "wide_table": "2020_CBG_B01",
        },
        fragments={"column_name": '"B01003e1"'},
    )
    assert ":in_geo_ids" in rendered
    assert "LIMIT %(limit)s" in rendered
