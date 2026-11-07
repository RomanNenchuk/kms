-- Конструкція: slice (фіксуємо ОДИН вимір: season = 'Winter')
-- Питання: які причини затримок домінують узимку і скільки вони коштують у хвилинах?
SELECT
    c.class_label        AS cause_class,
    COUNT(*)             AS flights,
    ROUND(AVG(f.delay_minutes), 1) AS avg_delay_min,
    SUM(f.cancelled)::INTEGER AS cancelled
FROM fact_flight f
JOIN dim_date d USING (date_key)
JOIN dim_delay_cause c USING (delay_cause_key)
WHERE d.season = 'Winter' AND c.class_label <> 'No delay'
GROUP BY c.class_label
ORDER BY flights DESC;
