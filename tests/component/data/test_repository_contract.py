import os

import pytest

from app.data.errors import ReadOnlyViolationError, UnsupportedAggregationError
from app.data.fake_repository import FakeCensusRepository
from app.data.models import AggregationMethod, GeoLevel
from app.data.snowflake_repository import SnowflakeCensusRepository, assert_read_only

Repository = FakeCensusRepository | SnowflakeCensusRepository

RUN_LIVE = os.environ.get("RUN_LIVE_TESTS") == "1"


def fake_repository() -> FakeCensusRepository:
    return FakeCensusRepository()


def snowflake_repository() -> SnowflakeCensusRepository:
    return SnowflakeCensusRepository()


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param(
            "snowflake",
            marks=pytest.mark.live,
            id="snowflake",
        ),
    ]
)
def repository(request: pytest.FixtureRequest) -> Repository:
    if request.param == "snowflake":
        if not RUN_LIVE:
            pytest.skip("Set RUN_LIVE_TESTS=1 to run Snowflake contract tests")
        repo = snowflake_repository()
        request.addfinalizer(repo.close)
        return repo
    return fake_repository()


def test_search_texas_state_first(repository: Repository) -> None:
    result = repository.search_geographies("Texas", GeoLevel.STATE, limit=5)
    assert result.rows
    assert result.rows[0].name == "Texas"
    assert result.rows[0].level == GeoLevel.STATE


def test_get_observations_texas_population_rollup(repository: Repository) -> None:
    result = repository.get_observations("B01003e1", ["48"], vintage=2020)
    assert len(result.rows) == 1
    assert result.rows[0].value > 0
    assert result.provenance.aggregation_method == AggregationMethod.SUM
    assert result.provenance.block_groups_aggregated is not None
    assert result.provenance.block_groups_aggregated > 0


def test_median_at_county_raises(repository: Repository) -> None:
    with pytest.raises(UnsupportedAggregationError):
        repository.get_observations("B19013e1", ["17031"], vintage=2020)


def test_median_at_block_group_direct(repository: Repository) -> None:
    result = repository.get_observations("B19013e1", ["480359506002"], vintage=2020)
    assert len(result.rows) == 1
    assert result.rows[0].value > 0
    assert result.provenance.aggregation_method == AggregationMethod.DIRECT


def test_state_time_series_population_rollup(repository: Repository) -> None:
    result = repository.get_time_series("B01003e1", "48")
    assert len(result.rows) >= 1
    vintages = {row.vintage for row in result.rows}
    assert vintages
    assert all(row.geo_id == "48" for row in result.rows)
    assert all(row.value > 0 for row in result.rows)
    assert result.provenance.aggregation_method == AggregationMethod.SUM


def test_available_vintages_for_state_non_empty(repository: Repository) -> None:
    vintages = repository.available_vintages("B01003e1", "48")
    assert vintages
    assert all(isinstance(vintage, int) for vintage in vintages)


def test_median_time_series_at_county_raises(repository: Repository) -> None:
    with pytest.raises(UnsupportedAggregationError):
        repository.get_time_series("B19013e1", "17031")


def test_read_only_guard_rejects_non_select() -> None:
    with pytest.raises(ReadOnlyViolationError):
        assert_read_only("DELETE FROM t")
