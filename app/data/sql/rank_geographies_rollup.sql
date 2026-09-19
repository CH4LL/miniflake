SELECT
    {{group_expression}} AS geo_id,
    SUM({{column_name}}) AS value,
    COUNT(*) AS block_groups_aggregated
FROM {{wide_table}}
WHERE 1 = 1
{{parent_filter}}
GROUP BY {{group_expression}}
ORDER BY value {{order_direction}}
LIMIT %(limit)s
