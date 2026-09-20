from __future__ import annotations

from pathlib import Path

from app.data.catalog import CatalogSeriesSpec, VariableCatalogSpec, load_variable_catalog_spec
from app.data.models import AggregationKind

SPEC_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "variable_catalog_spec.yaml"


def _spec() -> VariableCatalogSpec:
    return VariableCatalogSpec(
        series=[
            CatalogSeriesSpec(
                series_id="B01003",
                topic="Population",
                aggregation_kind=AggregationKind.COUNT,
                aliases=("population", "people", "residents"),
            ),
            CatalogSeriesSpec(
                series_id="B17001",
                topic="Poverty",
                aggregation_kind=AggregationKind.COUNT,
                aliases=("poverty", "poverty line", "poor"),
            ),
            CatalogSeriesSpec(
                series_id="B15003",
                topic="Education",
                aggregation_kind=AggregationKind.COUNT,
                aliases=("education", "degree"),
            ),
        ]
    )


def test_series_for_query_matches_alias_tokens() -> None:
    spec = _spec()
    assert spec.series_ids_for_query(["people", "below", "poverty", "line"]) == [
        "B01003",
        "B17001",
    ]


def test_series_for_query_matches_alias_stem() -> None:
    assert _spec().series_ids_for_query(["educated"]) == ["B15003"]


def test_series_for_query_requires_every_alias_token() -> None:
    spec = VariableCatalogSpec(
        series=[
            CatalogSeriesSpec(
                series_id="B19013",
                topic="Income",
                aggregation_kind=AggregationKind.MEDIAN,
                aliases=("median household income",),
            )
        ]
    )
    assert spec.series_ids_for_query(["median", "income"]) == []
    assert spec.series_ids_for_query(["household", "income", "median"]) == ["B19013"]


def test_series_for_query_without_match_is_empty() -> None:
    assert _spec().series_ids_for_query(["zebra"]) == []


def test_real_spec_tags_poverty_status_as_count() -> None:
    spec = load_variable_catalog_spec(SPEC_PATH)
    assert spec.aggregation_kind_for("B17001", "POVERTY STATUS IN THE PAST 12 MONTHS") == (
        AggregationKind.COUNT
    )
    assert spec.aggregation_kind_for("B17001", "Income in the past 12 months below poverty") == (
        AggregationKind.COUNT
    )


def test_real_spec_loads_aliases_for_thrash_prone_series() -> None:
    spec = load_variable_catalog_spec(SPEC_PATH)
    by_id = {item.series_id: item for item in spec.series}
    assert "poverty" in by_id["B17001"].aliases
    assert any(alias.startswith("educat") for alias in by_id["B15003"].aliases)
    assert "population" in by_id["B01003"].aliases
    assert spec.series_ids_for_query(["population", "below", "poverty", "line"]) == [
        "B01003",
        "B17001",
    ]
