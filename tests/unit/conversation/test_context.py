from __future__ import annotations

from typing import Any

from app.agent.composer import ToolCallTrace
from app.agent.prompt import build_system_prompt
from app.config import Settings
from app.conversation.context import ResolvedContext
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


def test_update_from_get_value_trace() -> None:
    context = ResolvedContext()
    context.update_from_traces(
        [
            ToolCallTrace(
                name="get_value",
                input={},
                result_kind="success",
                duration_ms=1.0,
                data={
                    "field_id": "B01003e1",
                    "field_name": "Total Population",
                    "geo_id": "48",
                    "geography_name": "Texas",
                    "vintage": 2020,
                },
            )
        ]
    )
    assert context.field_id == "B01003e1"
    assert context.field_name == "Total Population"
    assert context.geo_ids == ["48"]
    assert context.geo_names == ["Texas"]
    assert context.vintage == 2020


def test_update_from_find_geography_trace() -> None:
    context = ResolvedContext()
    context.update_from_traces(
        [
            ToolCallTrace(
                name="find_geography",
                input={},
                result_kind="success",
                duration_ms=1.0,
                data={"geo_id": "12", "name": "Florida", "level": "State"},
            )
        ]
    )
    assert context.geo_ids == ["12"]
    assert context.geo_names == ["Florida"]


def test_as_facts_renders_in_system_prompt() -> None:
    context = ResolvedContext(
        field_id="B01003e1",
        field_name="Total Population",
        geo_ids=["48"],
        geo_names=["Texas"],
        vintage=2020,
    )
    prompt = build_system_prompt(
        default_registry(_settings()),
        _settings(),
        context_facts=context.as_facts(),
    )
    assert "Recently discussed" in prompt
    assert "Total Population" in prompt
    assert "Texas" in prompt
    assert "2020" in prompt
