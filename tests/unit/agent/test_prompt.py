from typing import Any

from app.agent.prompt import build_system_prompt, load_templates
from app.config import Settings
from app.data.models import GeoLevel
from app.tools.registry import default_registry


def _settings(**overrides: Any) -> Settings:
    base = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def test_templates_load() -> None:
    templates = load_templates()
    assert "timeout" in templates
    assert templates["timeout"]


def test_system_prompt_lists_tools_and_geography_levels() -> None:
    registry = default_registry(_settings())
    prompt = build_system_prompt(registry, _settings(), context_facts=[])
    for schema in registry.schemas():
        assert schema["name"] in prompt
        assert schema["description"] in prompt
    for level in GeoLevel:
        assert level.value in prompt


def test_system_prompt_defaults_vintage_population_and_compare() -> None:
    registry = default_registry(_settings())
    prompt = build_system_prompt(registry, _settings(), context_facts=[])
    lowered = prompt.lower()
    assert "latest" in lowered
    assert "total population" in lowered
    assert "b01003" in lowered
    assert "`compare`" in lowered or "compare" in lowered
    assert "place searches" not in lowered
    assert "rolled up via SUM to Nation, State, and County" in prompt
    assert str(int(_settings().response_budget_seconds)) in prompt


def test_tool_descriptions_drop_place_and_default_vintage() -> None:
    registry = default_registry(_settings())
    by_name = {schema["name"]: schema["description"].lower() for schema in registry.schemas()}
    assert "place" not in by_name["find_geography"]
    assert "optional" in by_name["get_value"]
    assert "latest" in by_name["get_value"]
