from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from tests.conftest import make_settings_env


def test_settings_load_from_environment(settings_env: dict[str, str]) -> None:
    settings = Settings(_env_file=None)
    assert settings.app_name == settings_env["APP_NAME"]
    assert settings.environment == settings_env["ENVIRONMENT"]
    assert settings.log_level == settings_env["LOG_LEVEL"]
    assert settings.health_version == settings_env["HEALTH_VERSION"]
    assert settings.snowflake_account == settings_env["SNOWFLAKE_ACCOUNT"]
    assert settings.snowflake_user == settings_env["SNOWFLAKE_USER"]
    assert settings.snowflake_role == settings_env["SNOWFLAKE_ROLE"]
    assert settings.snowflake_warehouse == settings_env["SNOWFLAKE_WAREHOUSE"]
    assert settings.snowflake_database == settings_env["SNOWFLAKE_DATABASE"]
    assert settings.snowflake_schema == settings_env["SNOWFLAKE_SCHEMA"]
    assert settings.snowflake_private_key_path == settings_env["SNOWFLAKE_PRIVATE_KEY_PATH"]


def test_settings_defaults_apply(isolated_env: None, apply_env) -> None:
    apply_env(
        {
            "SNOWFLAKE_ACCOUNT": "TEST-ACCOUNT",
            "SNOWFLAKE_USER": "TEST_USER",
            "SNOWFLAKE_ROLE": "TEST_ROLE",
            "SNOWFLAKE_WAREHOUSE": "TEST_WH",
            "SNOWFLAKE_DATABASE": "TEST_DB",
            "SNOWFLAKE_PRIVATE_KEY_PATH": "/tmp/test_key.p8",
        }
    )
    settings = Settings(_env_file=None)
    assert settings.app_name == "miniflake"
    assert settings.environment == "local"
    assert settings.log_level == "INFO"
    assert settings.health_version == "0.1.0"
    assert settings.snowflake_schema == "PUBLIC"


def test_missing_required_snowflake_field_raises_with_field_name(
    isolated_env: None, apply_env
) -> None:
    env = make_settings_env()
    del env["SNOWFLAKE_ACCOUNT"]
    apply_env(env)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    assert "snowflake_account" in str(exc_info.value).lower()


def test_missing_private_key_raises_with_field_name(isolated_env: None, apply_env) -> None:
    env = make_settings_env()
    del env["SNOWFLAKE_PRIVATE_KEY_PATH"]
    apply_env(env)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    assert "snowflake_private_key" in str(exc_info.value).lower()


def test_private_key_pem_content_accepted(isolated_env: None, apply_env) -> None:
    env = make_settings_env()
    del env["SNOWFLAKE_PRIVATE_KEY_PATH"]
    env["SNOWFLAKE_PRIVATE_KEY"] = "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
    apply_env(env)
    settings = Settings(_env_file=None)
    assert settings.snowflake_private_key is not None
    assert settings.snowflake_private_key_path is None


def test_get_settings_is_cached(settings_env: dict[str, str]) -> None:
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
    get_settings.cache_clear()


def test_data_layer_settings_defaults(isolated_env: None, apply_env) -> None:
    apply_env(
        {
            "SNOWFLAKE_ACCOUNT": "TEST-ACCOUNT",
            "SNOWFLAKE_USER": "TEST_USER",
            "SNOWFLAKE_ROLE": "TEST_ROLE",
            "SNOWFLAKE_WAREHOUSE": "TEST_WH",
            "SNOWFLAKE_DATABASE": "TEST_DB",
            "SNOWFLAKE_PRIVATE_KEY_PATH": "/tmp/test_key.p8",
        }
    )
    settings = Settings(_env_file=None)
    assert settings.snowflake_statement_timeout_seconds == 60
    assert settings.snowflake_query_tag == "miniflake"
    assert settings.snowflake_max_rows == 1000
    assert settings.snowflake_retry_attempts == 3
    assert settings.repository_search_limit == 25
    assert settings.acs_vintages == [2019, 2020]
    assert settings.nation_geo_id == "US"
    assert settings.acs_wide_table_name(2020, "B01") == "2020_CBG_B01"
    assert (
        settings.metadata_field_descriptions_table(2019) == "2019_METADATA_CBG_FIELD_DESCRIPTIONS"
    )
    assert settings.fixtures_path() == Path("fixtures")


def test_tool_settings_defaults(isolated_env: None, apply_env) -> None:
    apply_env(
        {
            "SNOWFLAKE_ACCOUNT": "TEST-ACCOUNT",
            "SNOWFLAKE_USER": "TEST_USER",
            "SNOWFLAKE_ROLE": "TEST_ROLE",
            "SNOWFLAKE_WAREHOUSE": "TEST_WH",
            "SNOWFLAKE_DATABASE": "TEST_DB",
            "SNOWFLAKE_PRIVATE_KEY_PATH": "/tmp/test_key.p8",
        }
    )
    settings = Settings(_env_file=None)
    assert settings.tool_max_variable_candidates == 5
    assert settings.tool_max_geography_candidates == 5
    assert settings.tool_rank_limit_max == 25
    assert settings.tool_compare_max_geographies == 5
    assert settings.tool_suggestion_limit == 5
    assert settings.disabled_tools == []


def test_disabled_tools_parsed_from_comma_separated_string(isolated_env: None, apply_env) -> None:
    apply_env(
        {
            "SNOWFLAKE_ACCOUNT": "TEST-ACCOUNT",
            "SNOWFLAKE_USER": "TEST_USER",
            "SNOWFLAKE_ROLE": "TEST_ROLE",
            "SNOWFLAKE_WAREHOUSE": "TEST_WH",
            "SNOWFLAKE_DATABASE": "TEST_DB",
            "SNOWFLAKE_PRIVATE_KEY_PATH": "/tmp/test_key.p8",
            "DISABLED_TOOLS": "get_trend, compare",
        }
    )
    settings = Settings(_env_file=None)
    assert settings.disabled_tools == ["get_trend", "compare"]
