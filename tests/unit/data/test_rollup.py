import pytest

from app.data.errors import UnsupportedAggregationError
from app.data.models import AggregationKind, AggregationMethod, GeoLevel
from app.data.rollup import (
    level_for_geo_id,
    normalize_field_id,
    prefix_length,
    resolve_method,
    series_id_from_field_id,
    series_prefix_from_field_id,
)


def test_series_resolution() -> None:
    assert series_id_from_field_id("B01003e1") == "B01003"
    assert series_prefix_from_field_id("B19013e1") == "B19"
    assert normalize_field_id("B01003E1") == "B01003e1"


def test_prefix_length_by_level() -> None:
    assert prefix_length(GeoLevel.BLOCK_GROUP) == 12
    assert prefix_length(GeoLevel.COUNTY) == 5
    assert prefix_length(GeoLevel.STATE) == 2
    assert prefix_length(GeoLevel.NATION) is None


def test_level_for_geo_id() -> None:
    assert level_for_geo_id("US") == GeoLevel.NATION
    assert level_for_geo_id("48") == GeoLevel.STATE
    assert level_for_geo_id("17031") == GeoLevel.COUNTY
    assert level_for_geo_id("481131210001") == GeoLevel.BLOCK_GROUP


def test_count_rollup_allowed_at_aggregate_levels() -> None:
    for level in (GeoLevel.NATION, GeoLevel.STATE, GeoLevel.COUNTY):
        assert resolve_method(AggregationKind.COUNT, level) == AggregationMethod.SUM


def test_count_direct_at_block_group() -> None:
    assert resolve_method(AggregationKind.COUNT, GeoLevel.BLOCK_GROUP) == AggregationMethod.DIRECT


def test_median_and_rate_direct_at_block_group() -> None:
    assert resolve_method(AggregationKind.MEDIAN, GeoLevel.BLOCK_GROUP) == AggregationMethod.DIRECT
    assert resolve_method(AggregationKind.RATE, GeoLevel.BLOCK_GROUP) == AggregationMethod.DIRECT


@pytest.mark.parametrize(
    ("kind", "level"),
    [
        (AggregationKind.MEDIAN, GeoLevel.STATE),
        (AggregationKind.MEDIAN, GeoLevel.COUNTY),
        (AggregationKind.MEDIAN, GeoLevel.NATION),
        (AggregationKind.RATE, GeoLevel.STATE),
        (AggregationKind.RATE, GeoLevel.COUNTY),
        (AggregationKind.RATE, GeoLevel.NATION),
    ],
)
def test_median_rate_rejected_above_block_group(kind: AggregationKind, level: GeoLevel) -> None:
    with pytest.raises(UnsupportedAggregationError):
        resolve_method(kind, level)
