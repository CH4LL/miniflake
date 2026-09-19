from app.data.fake_repository import FakeCensusRepository
from app.tools.get_value import GetValueInput, GetValueTool
from app.tools.results import PeriodUnavailable, Success, UnsupportedRequest


def _tool() -> GetValueTool:
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
    return GetValueTool(settings, "get value")


def test_get_value_latest_vintage_success() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(
        repository,
        GetValueInput(field_id="B01003e1", geo_id="480359506002"),
    )
    assert isinstance(result, Success)
    assert result.data.vintage == 2020
    assert result.data.value > 0
    assert result.provenance


def test_get_value_unavailable_vintage() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(
        repository,
        GetValueInput(field_id="B01003e1", geo_id="480359506002", vintage=1990),
    )
    assert isinstance(result, PeriodUnavailable)
    assert "2019" in result.available
    assert "2020" in result.available


def test_get_value_median_at_county_unsupported() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(
        repository,
        GetValueInput(field_id="B19013e1", geo_id="48361", vintage=2020),
    )
    assert isinstance(result, UnsupportedRequest)


def test_get_value_median_at_block_group_success() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(
        repository,
        GetValueInput(field_id="B19013e1", geo_id="480359506002", vintage=2020),
    )
    assert isinstance(result, Success)
    assert result.data.aggregation_method == "direct"
