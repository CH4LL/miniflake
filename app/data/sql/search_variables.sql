SELECT
    TABLE_ID AS field_id,
    TABLE_ID AS table_id,
    TABLE_NUMBER AS series_id,
    COALESCE(
        NULLIF(FIELD_LEVEL_2, ''),
        NULLIF(FIELD_LEVEL_1, ''),
        TABLE_TITLE
    ) AS name,
    TABLE_TITLE AS description,
    TABLE_TOPICS AS topic
FROM {{metadata_table}}
WHERE TABLE_NUMBER IN :in_series_ids
AND UPPER(FIELD_LEVEL_1) = 'ESTIMATE'
AND (
    {{token_clauses}}
    {{alias_clause}}
)
AND (%(topic)s IS NULL OR LOWER(TABLE_TOPICS) LIKE '%%' || LOWER(%(topic)s) || '%%')
ORDER BY
    CASE
        WHEN LOWER(TABLE_ID) = LOWER(%(query)s) THEN 0
        WHEN LOWER(COALESCE(FIELD_LEVEL_2, '')) = LOWER(%(query)s) THEN 1
        WHEN LOWER(TABLE_TITLE) = LOWER(%(query)s) THEN 2
        WHEN LOWER(TABLE_ID) LIKE LOWER(%(query)s) || '%%' THEN 3
        WHEN LOWER(COALESCE(FIELD_LEVEL_2, '')) LIKE LOWER(%(query)s) || '%%' THEN 4
        WHEN LOWER(TABLE_TITLE) LIKE '%%' || LOWER(%(query)s) || '%%' THEN 5
        WHEN {{title_token_clauses}} THEN 6
        ELSE 7
    END,
    TABLE_ID
LIMIT %(limit)s
