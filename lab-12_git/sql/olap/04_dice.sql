-- Конструкція: dice (обмеження по КІЛЬКОХ вимірах: сезон, хаб вильоту, тип авіакомпанії)
-- Питання: яка середня затримка у літніх рейсах із хабів для low-cost і full-service авіакомпаній за місяцями?
SELECT
    d.month,
    al.airline_type,
    COUNT(*)                        AS flights,
    ROUND(AVG(f.delay_minutes), 1)  AS avg_delay_min,
    ROUND(100.0 * AVG(f.cancelled), 1) AS cancel_pct
FROM fact_flight f
JOIN dim_date d USING (date_key)
JOIN dim_airline al USING (airline_key)
JOIN dim_airport o ON f.origin_airport_key = o.airport_key
WHERE d.season = 'Summer'
  AND o.is_hub
  AND al.airline_type IN ('low-cost', 'full-service')
GROUP BY d.month, al.airline_type
ORDER BY d.month, al.airline_type;
