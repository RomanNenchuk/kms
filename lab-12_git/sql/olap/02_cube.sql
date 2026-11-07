-- Конструкція: CUBE (усі комбінації підсумків)
-- Питання: як розподіляються сумарні хвилини затримки за порою року та класом причини (без NoDelay)?
SELECT
    CASE WHEN GROUPING(d.season) = 1 THEN '(усі сезони)' ELSE d.season END AS season,
    CASE WHEN GROUPING(c.class_label) = 1 THEN '(усі класи)' ELSE c.class_label END AS cause_class,
    COUNT(*)                AS delayed_flights,
    SUM(f.delay_minutes)    AS total_delay_min
FROM fact_flight f
JOIN dim_date d USING (date_key)
JOIN dim_delay_cause c USING (delay_cause_key)
WHERE c.class_label <> 'No delay' AND f.cancelled = 0
GROUP BY CUBE (d.season, c.class_label)
ORDER BY GROUPING(d.season), d.season, GROUPING(c.class_label), total_delay_min DESC;
