from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings, get_settings
from app.data.snowflake_repository import SnowflakeCensusRepository

OUTPUT_DIR = Path("fixtures")
DATASET_PATH = Path("docs/data/dataset.md")
CATALOG_BEGIN = "<!-- catalog-snapshot-begin -->"
CATALOG_END = "<!-- catalog-snapshot-end -->"


def write_geographies(
    repo: SnowflakeCensusRepository, settings: Settings, output_dir: Path
) -> None:
    from app.data.models import GeoLevel

    nation = repo.get_geography(settings.nation_geo_id).rows[0]
    states = repo.search_geographies("", GeoLevel.STATE, limit=100).rows
    if not states:
        states = [
            repo.get_geography(item["fips"]).rows[0]
            for item in json.loads(settings.state_fips_names_file().read_text(encoding="utf-8"))
        ]
    counties = repo.search_geographies("County", GeoLevel.COUNTY, limit=50).rows
    orange_counties = repo.search_geographies("Orange County", GeoLevel.COUNTY, limit=10).rows
    county_by_id = {item.geo_id: item for item in counties}
    for item in orange_counties:
        county_by_id[item.geo_id] = item
    counties = list(county_by_id.values())
    block_group_ids = ["480359506002", "060371011101"]
    block_groups = [repo.get_geography(geo_id).rows[0] for geo_id in block_group_ids]
    payload = {
        "nation": nation.model_dump(),
        "states": [item.model_dump() for item in states[:56]],
        "counties": [item.model_dump() for item in counties[:20]],
        "block_groups": [item.model_dump() for item in block_groups],
    }
    (output_dir / "geographies.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def write_variables(repo: SnowflakeCensusRepository, output_dir: Path) -> list[dict[str, object]]:
    variables = []
    for topic_query in ("population", "income", "age", "poverty", "education", "housing"):
        result = repo.search_variables(topic_query, None, limit=50)
        for variable in result.rows:
            if variable.field_id.endswith("e1") or "Total" in variable.name:
                variables.append(variable.model_dump())
    deduped = {item["field_id"]: item for item in variables}
    payload = list(deduped.values())
    (output_dir / "variables.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


BLOCK_GROUP_GEO_IDS = ["480359506002", "060371011101"]
EVAL_FIELD_IDS = ["B01003e1", "B19013e1", "B01002e1"]


def write_sample_observations(
    repo: SnowflakeCensusRepository,
    settings: Settings,
    output_dir: Path,
    variables: list[dict[str, object]],
) -> None:
    observations: list[dict[str, object]] = []
    seen: set[tuple[str, str, int]] = set()
    field_ids = list(
        dict.fromkeys([str(item["field_id"]) for item in variables[:8]] + EVAL_FIELD_IDS)
    )
    for field_id in field_ids:
        for geo_id in BLOCK_GROUP_GEO_IDS:
            try:
                for vintage in settings.acs_vintages:
                    result = repo.get_observations(field_id, [geo_id], vintage=vintage)
                    for item in result.rows:
                        key = (item.geo_id, item.field_id, item.vintage)
                        if key in seen:
                            continue
                        seen.add(key)
                        observations.append(item.model_dump())
            except Exception:
                continue
    (output_dir / "sample_observations.json").write_text(
        json.dumps(observations, indent=2), encoding="utf-8"
    )


def render_catalog_section(variables: list[dict[str, object]]) -> str:
    topics = Counter(str(item.get("topic", "Other")) for item in variables)
    lines = [
        CATALOG_BEGIN,
        "",
        f"Generated on {datetime.now(UTC).isoformat()} by `scripts/snapshot_catalog.py`.",
        "",
        f"Curated field count: {len(variables)}.",
        "",
        "| Topic | Count |",
        "| :--- | ---: |",
    ]
    for topic, count in sorted(topics.items()):
        lines.append(f"| {topic} | {count} |")
    lines.extend(["", CATALOG_END])
    return "\n".join(lines)


def update_dataset_catalog_section(section: str) -> None:
    content = DATASET_PATH.read_text(encoding="utf-8")
    if CATALOG_BEGIN in content and CATALOG_END in content:
        before = content.split(CATALOG_BEGIN)[0]
        after = content.split(CATALOG_END)[1]
        content = before.rstrip() + "\n\n" + section + after
    else:
        marker = "## Variable catalog"
        replacement = "## Variable catalog\n\n" + section
        if marker in content and CATALOG_BEGIN not in content:
            content = content.replace(
                marker + "\n\nTo be populated by `scripts/snapshot_catalog.py` in S1.",
                replacement,
            )
        else:
            content += "\n\n## Variable catalog\n\n" + section + "\n"
    DATASET_PATH.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot catalog fixtures from Snowflake")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    get_settings.cache_clear()
    settings = Settings()
    args.output.mkdir(parents=True, exist_ok=True)
    repo = SnowflakeCensusRepository(settings)
    try:
        variables = write_variables(repo, args.output)
        write_geographies(repo, settings, args.output)
        write_sample_observations(repo, settings, args.output, variables)
        update_dataset_catalog_section(render_catalog_section(variables))
        print(f"Wrote fixtures to {args.output}")
    finally:
        repo.close()


if __name__ == "__main__":
    main()
