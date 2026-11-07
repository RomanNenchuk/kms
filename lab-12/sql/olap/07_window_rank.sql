-- Конструкція: віконна — RANK() з PARTITION BY + QUALIFY
-- Питання (Q4): які 5 маршрутів мають найбільшу середню затримку окремо для хабів і не-хабів вильоту (маршрути з >= 15 рейсів)?
WITH routes AS (
    SELECT o.iata || '-' || de.iata AS route,
           o.is_hub                 AS origin_is_hub,
           COUNT(*)                 AS flights,
           ROUND(AVG(f.delay_minutes), 1) AS avg_delay_min
    FROM fact_flight f
    JOIN dim_airport o  ON f.origin_airport_key = o.airport_key
    JOIN dim_airport de ON f.dest_airport_key   = de.airport_key
    WHERE f.cancelled = 0
    GROUP BY o.iata, de.iata, o.is_hub
    HAVING COUNT(*) >= 15
)
SELECT origin_is_hub, route, flights, avg_delay_min,
       RANK() OVER (PARTITION BY origin_is_hub ORDER BY avg_delay_min DESC) AS rnk
FROM routes
QUALIFY rnk <= 5
ORDER BY origin_is_hub DESC, rnk;
