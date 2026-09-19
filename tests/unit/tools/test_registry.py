from typing import Any

import pytest
from pydantic import BaseModel

from app.config import Settings
from app.data.errors import RepositoryError, TransientRepositoryError
from app.data.fake_repository import FakeCensusRepository
from app.data.repository import CensusRepository
from app.tools.base import ToolInput
from app.tools.registry import ToolRegistry, default_registry
from app.tools.results import Success, ToolError, UnsupportedRequest


class EchoInput(ToolInput):
    message: str


class EchoData(BaseModel):
    message: str


class EchoTool:
    name = "echo"
    description = "Echo a message"
    input_model = EchoInput

    def run(self, repository: CensusRepository, input: BaseModel) -> Success[EchoData]:
        payload = EchoInput.model_validate(input)
        return Success(data=EchoData(message=payload.message), provenance=[])


class BrokenTool:
    name = "broken"
    description = "Always fails"
    input_model = EchoInput

    def run(self, repository: CensusRepository, input: BaseModel) -> Success[EchoData]:
        raise RepositoryError("repository failed")


class TransientBrokenTool:
    name = "transient_broken"
    description = "Transient failure"
    input_model = EchoInput

    def run(self, repository: CensusRepository, input: BaseModel) -> Success[EchoData]:
        raise TransientRepositoryError("transient failure")


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


def test_default_registry_schemas_are_unique_with_additional_properties_false() -> None:
    registry = default_registry(_settings())
    schemas = registry.schemas()
    names = [schema["name"] for schema in schemas]
    assert len(names) == len(set(names))
    assert len(names) == 6
    for schema in schemas:
        assert schema["input_schema"]["additionalProperties"] is False
        assert schema["description"]


def test_register_duplicate_raises() -> None:
    registry = ToolRegistry(_settings())
    registry.register(EchoTool())
    with pytest.raises(ValueError, match="Duplicate tool registration"):
        registry.register(EchoTool())


def test_register_missing_description_raises() -> None:
    registry = ToolRegistry(_settings())

    class NoDescriptionTool:
        name = "no_description"
        description = ""
        input_model = EchoInput

        def run(self, repository: CensusRepository, input: BaseModel) -> Success[EchoData]:
            return Success(data=EchoData(message="ok"), provenance=[])

    with pytest.raises(ValueError, match="Missing description"):
        registry.register(NoDescriptionTool())


def test_dispatch_validates_input() -> None:
    registry = ToolRegistry(_settings())
    registry.register(EchoTool())
    result = registry.dispatch("echo", {}, FakeCensusRepository())
    assert isinstance(result, UnsupportedRequest)


def test_dispatch_unknown_tool_returns_unsupported_request() -> None:
    registry = default_registry(_settings())
    result = registry.dispatch("missing", {"message": "hi"}, FakeCensusRepository())
    assert isinstance(result, UnsupportedRequest)


def test_dispatch_wraps_repository_error() -> None:
    registry = ToolRegistry(_settings())
    registry.register(BrokenTool())
    result = registry.dispatch("broken", {"message": "hi"}, FakeCensusRepository())
    assert isinstance(result, ToolError)
    assert result.retryable is False


def test_dispatch_wraps_transient_repository_error() -> None:
    registry = ToolRegistry(_settings())
    registry.register(TransientBrokenTool())
    result = registry.dispatch("transient_broken", {"message": "hi"}, FakeCensusRepository())
    assert isinstance(result, ToolError)
    assert result.retryable is True


def test_disabled_tools_are_absent_and_rejected() -> None:
    registry = default_registry(_settings(DISABLED_TOOLS="get_trend,compare"))
    schemas = registry.schemas()
    names = {schema["name"] for schema in schemas}
    assert "get_trend" not in names
    assert "compare" not in names
    result = registry.dispatch(
        "get_trend",
        {"field_id": "B01003e1", "geo_id": "48"},
        FakeCensusRepository(),
    )
    assert isinstance(result, UnsupportedRequest)
