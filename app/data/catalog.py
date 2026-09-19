from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.data.models import AggregationKind, Variable
from app.data.rollup import normalize_field_id, series_id_from_field_id


@dataclass(frozen=True)
class CatalogSeriesSpec:
    series_id: str
    topic: str
    aggregation_kind: AggregationKind


@dataclass(frozen=True)
class VariableCatalogSpec:
    series: list[CatalogSeriesSpec]
    margin_of_error_field_level: str = "Margin of Error"

    @property
    def series_ids(self) -> list[str]:
        return [item.series_id for item in self.series]

    def topic_for(self, series_id: str) -> str:
        for item in self.series:
            if item.series_id == series_id:
                return item.topic
        return "Other"

    def aggregation_kind_for(self, series_id: str, field_name: str) -> AggregationKind:
        for item in self.series:
            if item.series_id == series_id:
                return item.aggregation_kind
        lowered = field_name.lower()
        if "median" in lowered:
            return AggregationKind.MEDIAN
        if any(token in lowered for token in ("percent", "rate", "ratio")):
            return AggregationKind.RATE
        return AggregationKind.COUNT


def load_variable_catalog_spec(path: Path) -> VariableCatalogSpec:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    series = [
        CatalogSeriesSpec(
            series_id=item["series_id"],
            topic=item["topic"],
            aggregation_kind=AggregationKind(item["aggregation_kind"]),
        )
        for item in raw["series"]
    ]
    return VariableCatalogSpec(series=series)


def load_state_fips_names(path: Path) -> list[dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_state_names_values_sql(states: list[dict[str, str]]) -> str:
    rows = []
    for state in states:
        fips = state["fips"]
        name = state["name"].replace("'", "''")
        abbreviation = state["abbreviation"]
        rows.append(f"('{fips}', '{name}', '{abbreviation}')")
    return (
        "SELECT column1 AS fips, column2 AS name, column3 AS abbreviation "
        f"FROM VALUES {', '.join(rows)}"
    )


def variable_from_metadata_row(
    row: dict[str, Any],
    *,
    catalog: VariableCatalogSpec,
    vintage: int,
    settings_table_name: str,
) -> Variable:
    field_id = normalize_field_id(str(row["field_id"]))
    series_id = str(row.get("series_id") or series_id_from_field_id(field_id)).upper()
    name = str(row.get("name") or field_id)
    table_name = settings_table_name
    return Variable(
        field_id=field_id,
        table_id=normalize_field_id(str(row.get("table_id") or field_id)),
        series_id=series_id,
        name=name,
        topic=str(row.get("topic") or catalog.topic_for(series_id)),
        aggregation_kind=catalog.aggregation_kind_for(series_id, name),
        description=row.get("description"),
        acs_table_name=table_name,
    )


def is_estimate_field(field_level_1: str | None, margin_label: str) -> bool:
    if not field_level_1:
        return False
    return field_level_1.strip().lower() == "estimate"


FIELD_ID_PATTERN = re.compile(r"^B\d{5}e\d+$", re.IGNORECASE)


def is_acs_field_id(field_id: str) -> bool:
    return bool(FIELD_ID_PATTERN.match(field_id))
