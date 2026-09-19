from pathlib import Path

import pytest

from app.data.catalog import build_state_names_values_sql, load_state_fips_names
from app.data.sql_loader import expand_in_list, load_sql_template, render_sql_template

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SQL_DIR = PROJECT_ROOT / "app" / "data" / "sql"
STATES = load_state_fips_names(PROJECT_ROOT / "fixtures" / "state_fips_names.json")


@pytest.mark.parametrize(
    "template_name",
    [
        "search_geographies.sql",
        "get_geography.sql",
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


def test_search_variables_template_renders_with_in_list() -> None:
    template = load_sql_template(SQL_DIR / "search_variables.sql")
    rendered = render_sql_template(
        template,
        identifiers={"metadata_table": "2020_METADATA_CBG_FIELD_DESCRIPTIONS"},
    )
    sql, params = expand_in_list(
        rendered,
        {
            "series_ids": ["B01003", "B19013"],
            "query": "population",
            "topic": None,
            "limit": 10,
        },
    )
    assert "series_ids_0" in params
    assert "IN (%(series_ids_0)s" in sql
    assert "%(query)s" in sql
    assert "LIMIT %(limit)s" in sql


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
