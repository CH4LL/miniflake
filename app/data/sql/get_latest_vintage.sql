SELECT MAX(vintage) AS latest_vintage
FROM (
    {{vintage_union}}
) vintages
