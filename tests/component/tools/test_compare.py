from app.config import Settings
from app.data.errors import RepositoryError
from app.data.fake_repository import FakeCensusRepository
from app.tools.compare import CompareInput, CompareTool
from app.tools.registry import default_registry
from app.tools.results import PeriodUnavailable, Success, ToolError, UnsupportedRequest


def _tool() -> CompareTool:
    settings = Settings(
        SNOWFLAKE_ACCOUNT="TEST",
        SNOWFLAKE_USER="TEST",
        SNOWFLAKE_ROLE="TEST",
        SNOWFLAKE_WAREHOUSE="TEST",
        SNOWFLAKE_DATABASE="TEST",
        SNOWFLAKE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        _env_file=None,
    )
    return CompareTool(settings, "compare")


def test_compare_common_vintage_success() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(
        repository,
        CompareInput(field_id="B01003e1", geo_ids=["480359506002", "060371011101"], vintage=2020),
    )
    assert isinstance(result, Success)
    assert len(result.data.geographies) == 2
    first = result.data.geographies[0].value
    second = result.data.geographies[1].value
    assert result.data.absolute_difference == second - first


def test_compare_no_common_vintage() -> None:
    class SplitVintageRepository(FakeCensusRepository):
        def available_vintages(self, field_id: str, geo_id: str) -> list[int]:
            if geo_id == "480359506002":
                return [2019]
            if geo_id == "060371011101":
                return [2020]
            return super().available_vintages(field_id, geo_id)

    result = _tool().run(
        SplitVintageRepository(),
        CompareInput(field_id="B01003e1", geo_ids=["480359506002", "060371011101"]),
    )
    assert isinstance(result, PeriodUnavailable)


def test_compare_single_geo_id_via_dispatch_is_unsupported() -> None:
    registry = default_registry(
        Settings(
            SNOWFLAKE_ACCOUNT="TEST",
            SNOWFLAKE_USER="TEST",
            SNOWFLAKE_ROLE="TEST",
            SNOWFLAKE_WAREHOUSE="TEST",
            SNOWFLAKE_DATABASE="TEST",
            SNOWFLAKE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
            _env_file=None,
        )
    )
    result = registry.dispatch(
        "compare",
        {"field_id": "B01003e1", "geo_ids": ["480359506002"]},
        FakeCensusRepository(),
    )
    assert isinstance(result, UnsupportedRequest)


def test_dispatch_repository_error_returns_tool_error() -> None:
    class FailingRepository:
        def search_geographies(self, query: str, level, limit: int):
            raise RepositoryError("boom")

        def get_geography(self, geo_id: str):
            raise RepositoryError("boom")

        def search_variables(self, query: str, topic, limit: int):
            raise RepositoryError("boom")

        def get_variable(self, field_id: str):
            raise RepositoryError("boom")

        def get_observations(self, field_id: str, geo_ids: list[str], vintage):
            raise RepositoryError("boom")

        def get_latest_vintage(self, field_id: str):
            raise RepositoryError("boom")

        def rank_geographies(self, field_id: str, level, vintage, parent_geo_id, descending, limit):
            raise RepositoryError("boom")

        def get_time_series(self, field_id: str, geo_id: str):
            raise RepositoryError("boom")

        def available_vintages(self, field_id: str, geo_id: str):
            raise RepositoryError("boom")

    registry = default_registry(
        Settings(
            SNOWFLAKE_ACCOUNT="TEST",
            SNOWFLAKE_USER="TEST",
            SNOWFLAKE_ROLE="TEST",
            SNOWFLAKE_WAREHOUSE="TEST",
            SNOWFLAKE_DATABASE="TEST",
            SNOWFLAKE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
            _env_file=None,
        )
    )
    result = registry.dispatch(
        "get_value",
        {"field_id": "B01003e1", "geo_id": "48"},
        FailingRepository(),
    )
    assert isinstance(result, ToolError)
