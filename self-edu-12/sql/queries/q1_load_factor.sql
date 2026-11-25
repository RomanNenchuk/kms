-- BQ1. Який коефіцієнт завантаження за типом авіакомпанії та кварталом?
-- Відношення сум (SUM/SUM) за виконаними рейсами; скасовані місця не пропонувались.
SELECT al.airline_type,
       d.quarter,
       SUM(f.passengers)::BIGINT AS passengers,
       SUM(f.seats)::BIGINT      AS seats,
       ROUND(100.0 * SUM(f.passengers) / SUM(f.seats), 2) AS load_factor_pct
FROM fact_flight f
JOIN dim_airline al ON f.airline_key = al.airline_key
JOIN dim_date    d  ON f.date_key    = d.date_key
WHERE f.cancelled = 0
GROUP BY al.airline_type, d.quarter
ORDER BY al.airline_type, d.quarter;
