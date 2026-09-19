SELECT
    {{vintage}} AS vintage,
    {{block_group_column}} AS geo_id,
    {{column_name}} AS value
FROM {{wide_table}}
WHERE {{block_group_column}} = %(geo_id)s
AND {{column_name}} IS NOT NULL
