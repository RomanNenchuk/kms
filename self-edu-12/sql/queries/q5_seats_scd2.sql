-- BQ5. Скільки місць запропоновано за виробником і типом ПС і чи враховано переобладнання салону?
-- seats_at_flight_date — за версією борту на дату рейсу (SCD2); seats_if_current — якби брали лише поточну версію.
SELECT a.manufacturer,
       a.aircraft_type,
       COUNT(*)             AS flights,
       SUM(f.seats)::BIGINT AS seats_at_flight_date,
       SUM(cur.seats)::BIGINT AS seats_if_current,
       (SUM(cur.seats) - SUM(f.seats))::BIGINT AS error_if_current
FROM fact_flight f
JOIN dim_aircraft a   ON f.aircraft_key = a.aircraft_key
JOIN dim_aircraft cur ON cur.registration = a.registration AND cur.is_current
GROUP BY ROLLUP (a.manufacturer, a.aircraft_type)
ORDER BY a.manufacturer NULLS LAST, a.aircraft_type NULLS LAST;
