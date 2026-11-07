-- Конструкція: віконна — накопичувальна сума та частка наростаючим підсумком
-- Питання (Q7): як накопичуються пасажири впродовж року по місяцях?
WITH m AS (
    SELECT d.month, d.month_name, SUM(f.passengers)::BIGINT AS passengers
    FROM fact_flight f JOIN dim_date d USING (date_key)
    GROUP BY d.month, d.month_name
)
SELECT month, month_name, passengers,
       SUM(passengers) OVER (ORDER BY month)                                   AS cumulative_passengers,
       ROUND(100.0 * SUM(passengers) OVER (ORDER BY month) / SUM(passengers) OVER (), 1) AS cumulative_pct
FROM m
ORDER BY month;
