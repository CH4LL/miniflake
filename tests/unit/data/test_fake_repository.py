from app.data.fake_repository import FakeCensusRepository
from app.data.models import GeoLevel
from app.data.search_utils import match_rank


def test_fixture_loading(fake_repository: FakeCensusRepository | None = None) -> None:
    repo = FakeCensusRepository()
    assert repo.get_variable("B01003e1").rows
    assert repo.get_geography("48").rows[0].name == "Texas"


def test_search_ordering_exact_before_contains() -> None:
    repo = FakeCensusRepository()
    result = repo.search_geographies("Texas", GeoLevel.STATE, limit=10)
    assert result.rows[0].name == "Texas"
    assert match_rank(result.rows[0].name, "Texas") == 0


def test_search_county_ambiguity_returns_multiple_orange_counties() -> None:
    repo = FakeCensusRepository()
    result = repo.search_geographies("Orange County", GeoLevel.COUNTY, limit=10)
    names = {row.name for row in result.rows}
    assert "Orange County" in names
    assert len(result.rows) >= 2
