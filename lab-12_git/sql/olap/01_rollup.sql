-- Конструкція: ROLLUP + GROUPING
-- Питання (Q1): яка частка рейсів вчасно (без скасування, затримка <= 14 хв) за типом авіакомпанії та авіакомпанією?
SELECT
    CASE WHEN GROUPING(al.airline_type) = 1 THEN '(усі типи)' ELSE al.airline_type END AS airline_type,
    CASE WHEN GROUPING(al.name) = 1 THEN '(усі)' ELSE al.name END AS airline,
    COUNT(*)                                                       AS flights,
    SUM(f.cancelled)::INTEGER                                      AS cancelled,
    ROUND(100.0 * SUM(CASE WHEN f.cancelled = 0 AND f.delay_minutes <= 14 THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_pct,
    ROUND(AVG(f.delay_minutes), 1)                                 AS avg_delay_min
FROM fact_flight f
JOIN dim_airline al USING (airline_key)
GROUP BY ROLLUP (al.airline_type, al.name)
ORDER BY GROUPING(al.airline_type), al.airline_type, GROUPING(al.name), al.name;
