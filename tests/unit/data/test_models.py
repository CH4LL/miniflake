from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.data.models import (
    AggregationKind,
    AggregationMethod,
    Geography,
    GeoLevel,
    Observation,
    Provenance,
    QueryResult,
    Variable,
)


def test_geo_level_values() -> None:
    assert set(GeoLevel) == {
        GeoLevel.BLOCK_GROUP,
        GeoLevel.NATION,
        GeoLevel.STATE,
        GeoLevel.COUNTY,
    }
    assert GeoLevel.STATE == "State"


def test_aggregation_kind_parsing() -> None:
    assert AggregationKind("count") == AggregationKind.COUNT
    assert AggregationKind("median") == AggregationKind.MEDIAN
    assert AggregationKind("rate") == AggregationKind.RATE


def test_variable_model_round_trip() -> None:
    variable = Variable(
        field_id="B01003e1",
        table_id="B01003e1",
        series_id="B01003",
        name="Total Population",
        topic="Population",
        aggregation_kind=AggregationKind.COUNT,
        acs_table_name="2020_CBG_B01",
    )
    assert variable.aggregation_kind == AggregationKind.COUNT
    assert variable.series_id == "B01003"


def test_query_result_generic() -> None:
    provenance = Provenance(
        sql="SELECT 1",
        parameters={"field_id": "B01003e1"},
        row_count=1,
        source="fake",
        executed_at=datetime.now(UTC),
        duration_ms=1.0,
        aggregation_method=AggregationMethod.SUM,
        block_groups_aggregated=100,
    )
    result = QueryResult[Observation](
        rows=[
            Observation(geo_id="48", field_id="B01003e1", vintage=2020, value=123.0),
        ],
        provenance=provenance,
    )
    assert result.rows[0].value == 123.0
    assert result.provenance.aggregation_method == AggregationMethod.SUM


def test_geography_requires_name() -> None:
    with pytest.raises(ValidationError):
        Geography(geo_id="48", level=GeoLevel.STATE)
