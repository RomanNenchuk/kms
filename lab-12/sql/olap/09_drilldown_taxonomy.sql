-- Конструкція: drill-down по ієрархії таксономії клас -> підклас (ROLLUP) + частка у класі
-- Питання (Q2): які класи й підкласи причин дають найбільше хвилин затримки?
WITH agg AS (
    SELECT
        CASE WHEN GROUPING(c.class_label) = 1 THEN '(усі класи)' ELSE c.class_label END       AS cause_class,
        CASE WHEN GROUPING(c.subclass_label) = 1 THEN '(весь клас)' ELSE c.subclass_label END AS cause_subclass,
        GROUPING(c.class_label) AS g_class, GROUPING(c.subclass_label) AS g_sub,
        COUNT(*) AS flights, SUM(f.delay_minutes)::BIGINT AS total_delay_min
    FROM fact_flight f JOIN dim_delay_cause c USING (delay_cause_key)
    WHERE c.class_label <> 'No delay' AND f.cancelled = 0
    GROUP BY ROLLUP (c.class_label, c.subclass_label)
),
x AS (
    SELECT *,
           MAX(total_delay_min) OVER (PARTITION BY cause_class) AS class_total
    FROM agg
)
SELECT cause_class, cause_subclass, flights, total_delay_min,
       ROUND(100.0 * total_delay_min / class_total, 1) AS pct_of_class
FROM x
ORDER BY g_class, class_total DESC, cause_class, g_sub DESC, total_delay_min DESC;
