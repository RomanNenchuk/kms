-- Конструкція: віконна — ковзне середнє за 7 днів
-- Питання: який тренд добового пасажиропотоку після згладжування денних коливань?
WITH daily AS (
    SELECT d.full_date, SUM(f.passengers) AS passengers
    FROM fact_flight f JOIN dim_date d USING (date_key)
    GROUP BY d.full_date
)
SELECT full_date, passengers,
       ROUND(AVG(passengers) OVER (ORDER BY full_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS moving_avg_7d
FROM daily
ORDER BY full_date;
