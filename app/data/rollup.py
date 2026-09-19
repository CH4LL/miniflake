from __future__ import annotations

import re

from app.data.errors import UnsupportedAggregationError
from app.data.models import AggregationKind, AggregationMethod, GeoLevel

FIELD_ID_PATTERN = re.compile(r"^(B\d{5})([eE]\d+)$", re.IGNORECASE)
NATION_GEO_ID = "US"


def normalize_field_id(field_id: str) -> str:
    match = FIELD_ID_PATTERN.match(field_id)
    if match:
        return match.group(1).upper() + match.group(2).lower()
    return field_id.upper()


def series_id_from_field_id(field_id: str) -> str:
    match = FIELD_ID_PATTERN.match(field_id)
    if not match:
        raise ValueError(f"Invalid ACS field id: {field_id}")
    return match.group(1).upper()


def series_prefix_from_field_id(field_id: str) -> str:
    series = series_id_from_field_id(field_id)
    return series[:3]


def prefix_length(level: GeoLevel) -> int | None:
    if level == GeoLevel.BLOCK_GROUP:
        return 12
    if level == GeoLevel.COUNTY:
        return 5
    if level == GeoLevel.STATE:
        return 2
    if level == GeoLevel.NATION:
        return None
    raise ValueError(f"Unsupported geography level: {level}")


def level_for_geo_id(geo_id: str, nation_geo_id: str = NATION_GEO_ID) -> GeoLevel:
    if geo_id == nation_geo_id:
        return GeoLevel.NATION
    if len(geo_id) == 12 and geo_id.isdigit():
        return GeoLevel.BLOCK_GROUP
    if len(geo_id) == 5 and geo_id.isdigit():
        return GeoLevel.COUNTY
    if len(geo_id) == 2 and geo_id.isdigit():
        return GeoLevel.STATE
    raise ValueError(f"Cannot infer geography level from id: {geo_id}")


def resolve_method(kind: AggregationKind, level: GeoLevel) -> AggregationMethod:
    if level == GeoLevel.BLOCK_GROUP:
        return AggregationMethod.DIRECT
    if kind == AggregationKind.COUNT:
        return AggregationMethod.SUM
    raise UnsupportedAggregationError(
        f"{kind.value} fields cannot roll up to {level.value} geography"
    )


def rollup_group_expression(block_group_column: str, level: GeoLevel) -> str:
    quoted = f'"{block_group_column}"'
    if level == GeoLevel.NATION:
        return f"'{NATION_GEO_ID}'"
    prefix_len = prefix_length(level)
    if prefix_len is None:
        raise ValueError(f"No prefix length for {level}")
    return f"LEFT({quoted}, {prefix_len})"


def parent_geo_id_for(
    geo_id: str, level: GeoLevel, nation_geo_id: str = NATION_GEO_ID
) -> str | None:
    if level == GeoLevel.NATION:
        return None
    if level == GeoLevel.STATE:
        return nation_geo_id
    if level == GeoLevel.COUNTY:
        return geo_id[:2]
    if level == GeoLevel.BLOCK_GROUP:
        return geo_id[:5]
    return None
