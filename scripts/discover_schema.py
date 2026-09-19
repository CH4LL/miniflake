from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import snowflake.connector
from jinja2 import Environment, FileSystemLoader

from app.config import Settings, get_settings

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_PATH = Path(__file__).parent.parent / "docs" / "data" / "dataset.md"

ACS_TABLE_PATTERN = re.compile(r"(?:ACS\d{4}_5YR|\d{4}_CBG_B\d+)", re.IGNORECASE)
FIELD_DESCRIPTIONS_HINTS = ("METADATA_CBG_FIELD_DESCRIPTIONS", "FIELD_DESCRIPTION", "FIELD_DESC")
FIPS_MAPPING_HINTS = ("METADATA_CBG_FIPS_CODES", "FIPS_CODES", "GEOGRAPHY_MAPPING")
GEOGRAPHIC_DATA_HINTS = ("METADATA_CBG_GEOGRAPHIC_DATA", "GEOGRAPHIC_DATA", "GEO_DATA")
CBSA_HINTS = ("CBSA", "METRO")


@dataclass
class TableInfo:
    schema_name: str
    table_name: str
    row_count: int | None
    column_count: int
    columns: list[str] = field(default_factory=list)


@dataclass
class AcsWideTable:
    table_name: str
    row_count: int | None
    column_count: int
    vintage: int | None
    primary_key_column: str | None


@dataclass
class MetadataTable:
    table_name: str
    row_count: int | None
    columns: list[str]
    distinct_table_id_count: int | None = None
    sample_rows: list[dict[str, str]] = field(default_factory=list)
    has_cbsa_mapping: bool = False


@dataclass
class InspectionResult:
    database_name: str
    schemas: list[str]
    tables: list[TableInfo]
    acs_wide_tables: list[AcsWideTable]
    field_descriptions: MetadataTable | None
    fips_mapping: MetadataTable | None
    geographic_data: MetadataTable | None
    block_group_count: int | None
    cbsa_mapping_present: bool
    acquisition_date: str
    generated_at: str


def _execute_one(cursor, query: str, params: tuple | None = None) -> list[tuple]:
    cursor.execute(query, params or ())
    return cursor.fetchall()


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _fqn(database: str, schema: str, table: str) -> str:
    return f"{_quote(database)}.{_quote(schema)}.{_quote(table)}"


def _table_matches(name: str, hints: tuple[str, ...]) -> bool:
    upper = name.upper()
    return any(hint in upper for hint in hints)


def _parse_vintage(table_name: str) -> int | None:
    for pattern in (r"ACS(\d{4})_5YR", r"^(\d{4})_CBG_"):
        match = re.search(pattern, table_name, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _find_primary_key(columns: list[str]) -> str | None:
    for candidate in ("CENSUS_BLOCK_GROUP", "BLOCK_GROUP", "GEO_ID"):
        if candidate in columns:
            return candidate
    return None


def inspect_share(connection, database: str) -> InspectionResult:
    cursor = connection.cursor()
    try:
        schemas = [
            row[1]
            for row in _execute_one(
                cursor,
                f"SHOW SCHEMAS IN DATABASE {_quote(database)}",
            )
        ]

        tables: list[TableInfo] = []
        acs_wide_tables: list[AcsWideTable] = []
        field_descriptions: MetadataTable | None = None
        fips_mapping: MetadataTable | None = None
        geographic_data: MetadataTable | None = None

        for schema_name in schemas:
            if schema_name.upper() in ("INFORMATION_SCHEMA",):
                continue
            schema_tables = _execute_one(
                cursor,
                f"SHOW TABLES IN SCHEMA {_quote(database)}.{_quote(schema_name)}",
            )
            for table_row in schema_tables:
                table_name = table_row[1]
                fqn = _fqn(database, schema_name, table_name)
                columns = [
                    col[0]
                    for col in _execute_one(
                        cursor,
                        f"DESCRIBE TABLE {fqn}",
                    )
                ]
                count_rows = _execute_one(
                    cursor,
                    f"SELECT COUNT(*) FROM {fqn}",
                )
                row_count = int(count_rows[0][0]) if count_rows else None
                table_info = TableInfo(
                    schema_name=schema_name,
                    table_name=table_name,
                    row_count=row_count,
                    column_count=len(columns),
                    columns=columns,
                )
                tables.append(table_info)

                if ACS_TABLE_PATTERN.search(table_name):
                    acs_wide_tables.append(
                        AcsWideTable(
                            table_name=table_name,
                            row_count=row_count,
                            column_count=len(columns),
                            vintage=_parse_vintage(table_name),
                            primary_key_column=_find_primary_key(columns),
                        )
                    )

                if _table_matches(table_name, FIELD_DESCRIPTIONS_HINTS) and (
                    field_descriptions is None or "REDISTRICTING" not in table_name.upper()
                ):
                    field_descriptions = _build_metadata_table(
                        cursor, database, schema_name, table_name, columns, row_count
                    )
                elif _table_matches(table_name, FIPS_MAPPING_HINTS):
                    fips_mapping = _build_metadata_table(
                        cursor, database, schema_name, table_name, columns, row_count
                    )
                    if any(_table_matches(col, CBSA_HINTS) for col in columns):
                        fips_mapping.has_cbsa_mapping = True
                elif (
                    _table_matches(table_name, GEOGRAPHIC_DATA_HINTS)
                    and "REDISTRICTING" not in table_name.upper()
                ):
                    geographic_data = _build_metadata_table(
                        cursor, database, schema_name, table_name, columns, row_count
                    )

        block_group_count = _count_block_groups(cursor, database, acs_wide_tables)
        cbsa_mapping_present = bool(
            (fips_mapping and fips_mapping.has_cbsa_mapping)
            or any(_table_matches(t.table_name, CBSA_HINTS) for t in tables)
        )

        return InspectionResult(
            database_name=database,
            schemas=schemas,
            tables=tables,
            acs_wide_tables=acs_wide_tables,
            field_descriptions=field_descriptions,
            fips_mapping=fips_mapping,
            geographic_data=geographic_data,
            block_group_count=block_group_count,
            cbsa_mapping_present=cbsa_mapping_present,
            acquisition_date=datetime.now(UTC).strftime("%Y-%m-%d"),
            generated_at=datetime.now(UTC).isoformat(),
        )
    finally:
        cursor.close()


def _build_metadata_table(
    cursor,
    database: str,
    schema_name: str,
    table_name: str,
    columns: list[str],
    row_count: int | None,
) -> MetadataTable:
    distinct_count: int | None = None
    sample_rows: list[dict[str, str]] = []
    table_id_col = next(
        (c for c in columns if c.upper() in ("TABLE_ID", "SERIES_ID", "ACS_TABLE_ID", "COLUMN_ID")),
        None,
    )
    fqn = _fqn(database, schema_name, table_name)
    if table_id_col:
        count_result = _execute_one(
            cursor,
            f"SELECT COUNT(DISTINCT {_quote(table_id_col)}) FROM {fqn}",
        )
        distinct_count = int(count_result[0][0]) if count_result else None

    sample_cols = columns[:6]
    quoted_cols = ", ".join(_quote(c) for c in sample_cols)
    raw_rows = _execute_one(
        cursor,
        f"SELECT {quoted_cols} FROM {fqn} LIMIT 5",
    )
    for row in raw_rows:
        sample_rows.append(
            {
                col: str(val) if val is not None else ""
                for col, val in zip(sample_cols, row, strict=True)
            }
        )

    return MetadataTable(
        table_name=table_name,
        row_count=row_count,
        columns=columns,
        distinct_table_id_count=distinct_count,
        sample_rows=sample_rows,
    )


def _count_block_groups(cursor, database: str, acs_tables: list[AcsWideTable]) -> int | None:
    if not acs_tables:
        return None
    table = acs_tables[0]
    pk = table.primary_key_column or "CENSUS_BLOCK_GROUP"
    schema = "PUBLIC"
    fqn = _fqn(database, schema, table.table_name)
    try:
        result = _execute_one(
            cursor,
            f"SELECT COUNT(DISTINCT {_quote(pk)}) FROM {fqn}",
        )
        return int(result[0][0]) if result else None
    except Exception:
        result = _execute_one(cursor, f"SELECT COUNT(*) FROM {fqn}")
        return int(result[0][0]) if result else None


def render_dataset_doc(result: InspectionResult) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("dataset.md.j2")
    vintages = sorted({t.vintage for t in result.acs_wide_tables if t.vintage})
    return template.render(result=result, vintages=vintages)


def connect_snowflake(settings: Settings):
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    key_bytes = settings.load_private_key_bytes()
    passphrase = settings.snowflake_private_key_passphrase
    private_key = serialization.load_pem_private_key(
        key_bytes,
        password=passphrase.encode() if passphrase else None,
        backend=default_backend(),
    )
    pkb = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        role=settings.snowflake_role,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
        private_key=pkb,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover SafeGraph share schema")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Output path for dataset.md",
    )
    args = parser.parse_args()

    settings = get_settings()
    connection = connect_snowflake(settings)
    try:
        result = inspect_share(connection, settings.snowflake_database)
        doc = render_dataset_doc(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(doc, encoding="utf-8")
        print(f"Wrote {args.output}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
