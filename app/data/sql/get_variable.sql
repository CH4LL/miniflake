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
WHERE TABLE_ID = %(field_id)s
AND TABLE_NUMBER IN :in_series_ids
AND UPPER(FIELD_LEVEL_1) = 'ESTIMATE'
LIMIT 1
