from scripts.discover_schema import (
    AcsWideTable,
    InspectionResult,
    MetadataTable,
    TableInfo,
    render_dataset_doc,
)


def _sample_result() -> InspectionResult:
    return InspectionResult(
        database_name="US_OPEN_CENSUS_DATA_NEIGHBORHOOD_INSIGHTS_FREE_DATASET",
        schemas=["PUBLIC"],
        tables=[
            TableInfo(
                schema_name="PUBLIC",
                table_name="ACS2019_5YR",
                row_count=1000,
                column_count=50,
                columns=["CENSUS_BLOCK_GROUP", "B01003e1"],
            ),
            TableInfo(
                schema_name="PUBLIC",
                table_name="METADATA_FIELD_DESCRIPTIONS",
                row_count=500,
                column_count=8,
                columns=["TABLE_ID", "TABLE_TITLE", "FIELD_ID"],
            ),
        ],
        acs_wide_tables=[
            AcsWideTable(
                table_name="ACS2019_5YR",
                row_count=1000,
                column_count=50,
                vintage=2019,
                primary_key_column="CENSUS_BLOCK_GROUP",
            ),
            AcsWideTable(
                table_name="ACS2020_5YR",
                row_count=1100,
                column_count=52,
                vintage=2020,
                primary_key_column="CENSUS_BLOCK_GROUP",
            ),
        ],
        field_descriptions=MetadataTable(
            table_name="METADATA_FIELD_DESCRIPTIONS",
            row_count=500,
            columns=["TABLE_ID", "TABLE_TITLE", "FIELD_ID", "FIELD_TITLE"],
            distinct_table_id_count=120,
            sample_rows=[
                {"TABLE_ID": "B01003", "TABLE_TITLE": "Total Population"},
                {"TABLE_ID": "B19013", "TABLE_TITLE": "Median Household Income"},
            ],
        ),
        fips_mapping=MetadataTable(
            table_name="FIPS_BLOCK_GROUP_MAPPING",
            row_count=1000,
            columns=["CENSUS_BLOCK_GROUP", "STATE", "COUNTY", "CBSA"],
            has_cbsa_mapping=True,
        ),
        geographic_data=MetadataTable(
            table_name="GEOGRAPHIC_DATA",
            row_count=1000,
            columns=["CENSUS_BLOCK_GROUP", "LAND_AREA", "LATITUDE", "LONGITUDE"],
        ),
        block_group_count=1000,
        cbsa_mapping_present=True,
        acquisition_date="2026-09-19",
        generated_at="2026-09-19T10:00:00+00:00",
    )


def test_render_produces_acs_wide_tables_section() -> None:
    doc = render_dataset_doc(_sample_result())
    assert "## ACS wide tables" in doc
    assert "ACS2019_5YR" in doc
    assert "ACS2020_5YR" in doc
    assert "CENSUS_BLOCK_GROUP" in doc


def test_render_produces_metadata_sections() -> None:
    doc = render_dataset_doc(_sample_result())
    assert "### Field descriptions" in doc
    assert "METADATA_FIELD_DESCRIPTIONS" in doc
    assert "B01003" in doc
    assert "### FIPS / geography mapping" in doc
    assert "FIPS_BLOCK_GROUP_MAPPING" in doc
    assert "### Geographic data" in doc
    assert "GEOGRAPHIC_DATA" in doc


def test_render_includes_block_group_count() -> None:
    doc = render_dataset_doc(_sample_result())
    assert "Distinct block group count: 1000" in doc


def test_render_includes_cbsa_mapping() -> None:
    doc = render_dataset_doc(_sample_result())
    assert "CBSA mapping present:** yes" in doc


def test_render_includes_vintages() -> None:
    doc = render_dataset_doc(_sample_result())
    assert "## ACS vintages" in doc
    assert "2019" in doc
    assert "2020" in doc


def test_render_includes_database_name() -> None:
    doc = render_dataset_doc(_sample_result())
    assert "US_OPEN_CENSUS_DATA_NEIGHBORHOOD_INSIGHTS_FREE_DATASET" in doc
