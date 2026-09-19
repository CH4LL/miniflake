WITH state_names AS (
    {{state_names_values}}
),
counties AS (
    SELECT DISTINCT
        LPAD(CAST(STATE_FIPS AS VARCHAR), 2, '0') || LPAD(CAST(COUNTY_FIPS AS VARCHAR), 3, '0') AS geo_id,
        COUNTY AS name,
        'County' AS level,
        LPAD(CAST(STATE_FIPS AS VARCHAR), 2, '0') AS parent_geo_id,
        STATE AS state_abbreviation
    FROM {{fips_table}}
),
states AS (
    SELECT
        sn.fips AS geo_id,
        sn.name AS name,
        'State' AS level,
        NULL AS parent_geo_id,
        sn.abbreviation AS state_abbreviation
    FROM state_names sn
),
nation AS (
    SELECT
        '{{nation_geo_id}}' AS geo_id,
        'United States' AS name,
        'Nation' AS level,
        NULL AS parent_geo_id,
        NULL AS state_abbreviation
),
block_groups AS (
    SELECT
        CENSUS_BLOCK_GROUP AS geo_id,
        CENSUS_BLOCK_GROUP AS name,
        'BlockGroup' AS level,
        LEFT(CENSUS_BLOCK_GROUP, 5) AS parent_geo_id,
        NULL AS state_abbreviation
    FROM {{geographic_data_table}}
),
all_geographies AS (
    SELECT * FROM nation
    UNION ALL
    SELECT * FROM states
    UNION ALL
    SELECT * FROM counties
    UNION ALL
    SELECT * FROM block_groups
)
SELECT
    geo_id,
    name,
    level,
    parent_geo_id,
    state_abbreviation,
    CASE
        WHEN LOWER(name) = LOWER(%(query)s) THEN 0
        WHEN LOWER(name) LIKE LOWER(%(query)s) || '%%' THEN 1
        WHEN LOWER(name) LIKE '%%' || LOWER(%(query)s) || '%%' THEN 2
        ELSE 3
    END AS match_rank
FROM all_geographies
WHERE (
    %(level)s IS NULL OR level = %(level)s
)
AND (
    LOWER(name) = LOWER(%(query)s)
    OR LOWER(name) LIKE LOWER(%(query)s) || '%%'
    OR LOWER(name) LIKE '%%' || LOWER(%(query)s) || '%%'
)
ORDER BY match_rank, name
LIMIT %(limit)s
