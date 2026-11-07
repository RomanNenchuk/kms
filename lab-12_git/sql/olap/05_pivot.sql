-- Конструкція: PIVOT (рядки — підклас погоди, стовпці — пора року)
-- Питання (Q3): як пора року впливає на кількість погодних затримок за підкласами?
PIVOT (
    SELECT c.subclass_label AS weather_cause, d.season, f.flight_id
    FROM fact_flight f
    JOIN dim_date d USING (date_key)
    JOIN dim_delay_cause c USING (delay_cause_key)
    WHERE c.class_label = 'Weather'
) ON season USING COUNT(flight_id) GROUP BY weather_cause ORDER BY weather_cause;
