from app.data.fake_repository import FakeCensusRepository
from app.tools.get_trend import GetTrendInput, GetTrendTool
from app.tools.results import PeriodUnavailable, Success


def _tool() -> GetTrendTool:
    from app.config import Settings

    settings = Settings(
        SNOWFLAKE_ACCOUNT="TEST",
        SNOWFLAKE_USER="TEST",
        SNOWFLAKE_ROLE="TEST",
        SNOWFLAKE_WAREHOUSE="TEST",
        SNOWFLAKE_DATABASE="TEST",
        SNOWFLAKE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        _env_file=None,
    )
    return GetTrendTool(settings, "get trend")


def test_get_trend_state_success() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(
        repository,
        GetTrendInput(field_id="B01003e1", geo_id="48"),
    )
    assert isinstance(result, Success)
    assert len(result.data.points) >= 1
    assert result.data.aggregation_method == "sum"
    assert result.data.measurement_period_note
    assert result.data.geography_name == "Texas"


def test_get_trend_filtered_range_unavailable() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(
        repository,
        GetTrendInput(field_id="B01003e1", geo_id="48", start_year=1990, end_year=1995),
    )
    assert isinstance(result, PeriodUnavailable)
    assert result.available
