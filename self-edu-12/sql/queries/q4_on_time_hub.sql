-- BQ4. Як змінюється частка рейсів, виконаних вчасно, по місяцях для хабів і не-хабів (аеропорт вильоту)?
-- Вчасно = не скасовано і затримка <= 14 хв. Частка — відношення сум, не середнє середніх.
SELECT d.month,
       o.is_hub,
       COUNT(*) AS flights,
       SUM(CASE WHEN f.cancelled = 0 AND f.delay_minutes <= 14 THEN 1 ELSE 0 END)::BIGINT AS on_time,
       ROUND(100.0 * SUM(CASE WHEN f.cancelled = 0 AND f.delay_minutes <= 14 THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_pct
FROM fact_flight f
JOIN dim_date    d ON f.date_key           = d.date_key
JOIN dim_airport o ON f.origin_airport_key = o.airport_key
GROUP BY d.month, o.is_hub
ORDER BY d.month, o.is_hub;
