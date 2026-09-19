import os

import pytest

from app.config import Settings, get_settings
from app.data.snowflake_repository import SnowflakeCensusRepository

pytestmark = pytest.mark.live

RUN_LIVE = os.environ.get("RUN_LIVE_TESTS") == "1"


@pytest.fixture(autouse=True)
def _skip_unless_live() -> None:
    if not RUN_LIVE:
        pytest.skip("Set RUN_LIVE_TESTS=1 to run live Snowflake repository tests")


@pytest.fixture
def repository() -> SnowflakeCensusRepository:
    get_settings.cache_clear()
    repo = SnowflakeCensusRepository(Settings())
    yield repo
    repo.close()


def test_search_geographies_smoke(repository: SnowflakeCensusRepository) -> None:
    from app.data.models import GeoLevel

    result = repository.search_geographies("Texas", GeoLevel.STATE, limit=5)
    assert result.rows
    assert result.provenance.source == "snowflake"


def test_get_variable_smoke(repository: SnowflakeCensusRepository) -> None:
    result = repository.get_variable("B01003e1")
    assert result.rows
    assert result.rows[0].field_id == "B01003e1"


def test_get_observations_texas_smoke(repository: SnowflakeCensusRepository) -> None:
    result = repository.get_observations("B01003e1", ["48"], vintage=2020)
    assert result.rows
    assert result.provenance.aggregation_method.value == "sum"
