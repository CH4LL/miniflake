from app.data.fake_repository import FakeCensusRepository
from app.data.models import GeoLevel
from app.tools.rank_geographies import RankGeographiesInput, RankGeographiesTool
from app.tools.results import Success, UnsupportedRequest


def _tool() -> RankGeographiesTool:
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
    return RankGeographiesTool(settings, "rank geographies")


def test_rank_counties_within_state_ordered_desc() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(
        repository,
        RankGeographiesInput(
            field_id="B01003e1",
            level=GeoLevel.COUNTY,
            within_geo_id="48",
            vintage=2020,
            order="desc",
            limit=5,
        ),
    )
    assert isinstance(result, Success)
    assert result.data.rankings
    values = [item.value for item in result.data.rankings]
    assert values == sorted(values, reverse=True)


def test_rank_median_at_county_unsupported() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(
        repository,
        RankGeographiesInput(
            field_id="B19013e1",
            level=GeoLevel.COUNTY,
            vintage=2020,
        ),
    )
    assert isinstance(result, UnsupportedRequest)
