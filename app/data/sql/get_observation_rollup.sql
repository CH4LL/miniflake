SELECT
    {{group_expression}} AS geo_id,
    SUM({{column_name}}) AS value,
    COUNT(*) AS block_groups_aggregated
FROM {{wide_table}}
WHERE 1 = 1
{{parent_filter}}
GROUP BY {{group_expression}}
{{having_clause}}
LIMIT %(limit)s
