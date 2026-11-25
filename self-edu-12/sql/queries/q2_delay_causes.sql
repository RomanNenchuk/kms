-- BQ2. Які класи й підкласи причин затримок дають найбільше хвилин затримки?
-- Drill-down по ієрархії таксономії клас -> підклас (ROLLUP дає підсумок класу та загальний).
SELECT c.class_label,
       c.subclass_label,
       SUM(f.delay_minutes)::BIGINT AS delay_min,
       COUNT(*)             AS flights
FROM fact_flight f
JOIN dim_delay_cause c ON f.delay_cause_key = c.delay_cause_key
WHERE c.class_label <> 'No delay'
GROUP BY ROLLUP (c.class_label, c.subclass_label)
ORDER BY c.class_label NULLS LAST, delay_min DESC;
