SELECT vintage
FROM (
    {{vintage_union}}
) vintages
ORDER BY vintage
