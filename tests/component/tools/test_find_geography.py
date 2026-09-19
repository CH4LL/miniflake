from app.data.fake_repository import FakeCensusRepository
from app.data.models import GeoLevel
from app.tools.find_geography import FindGeographyInput, FindGeographyTool
from app.tools.results import Ambiguous, NotFound, Success


def _tool() -> FindGeographyTool:
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
    return FindGeographyTool(settings, "search geographies")


def test_find_texas_state_success() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(
        repository,
        FindGeographyInput(query="Texas", level=GeoLevel.STATE),
    )
    assert isinstance(result, Success)
    assert result.data.name == "Texas"
    assert result.data.level == GeoLevel.STATE
    assert result.provenance


def test_find_orange_county_ambiguous() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(repository, FindGeographyInput(query="Orange County"))
    assert isinstance(result, Ambiguous)
    states = {candidate.state_abbreviation for candidate in result.candidates}
    assert len(states) > 1
    assert "state" in result.hint.lower()


def test_find_city_of_denver_not_found() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(repository, FindGeographyInput(query="city of Denver"))
    assert isinstance(result, NotFound)
    assert result.what == "city of Denver"


def test_find_atlantis_not_found() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(repository, FindGeographyInput(query="Atlantis"))
    assert isinstance(result, NotFound)
    assert result.what == "Atlantis"
