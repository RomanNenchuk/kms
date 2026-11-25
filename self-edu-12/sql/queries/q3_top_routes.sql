-- BQ3. Які 10 маршрутів (вильот -> призначення) приносять найбільший дохід?
-- dim_airport використано двічі (role-playing): origin та destination.
SELECT o.iata    AS origin,
       de.iata   AS destination,
       o.country AS origin_country,
       COUNT(*)  AS flights,
       SUM(f.passengers)::BIGINT       AS passengers,
       ROUND(SUM(f.revenue_usd))::BIGINT AS revenue_usd
FROM fact_flight f
JOIN dim_airport o  ON f.origin_airport_key = o.airport_key
JOIN dim_airport de ON f.dest_airport_key   = de.airport_key
GROUP BY o.iata, de.iata, o.country
ORDER BY SUM(f.revenue_usd) DESC, origin, destination
LIMIT 10;
