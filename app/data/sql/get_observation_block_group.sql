SELECT
    {{block_group_column}} AS geo_id,
    {{column_name}} AS value
FROM {{wide_table}}
WHERE {{block_group_column}} IN :in_geo_ids
AND {{column_name}} IS NOT NULL
LIMIT %(limit)s
