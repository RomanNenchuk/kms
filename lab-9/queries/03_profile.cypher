// ЛР 9 / Результат 4, Крок 3. PROFILE: до/після оптимізації. Запускати блоками по одному.

// ===== Запит A (оптимізуємо індексом) =====
// ДО: прибираємо індекс
DROP INDEX flight_number_idx IF EXISTS;

PROFILE
MATCH (f:Flight {flightNumber: 'SU101'})
RETURN f.flightId, f.date;
// Очікуємо: NodeByLabelScan + Filter (скануються всі Flight). Запишіть db hits.

// ПІСЛЯ: створюємо індекс
CREATE INDEX flight_number_idx IF NOT EXISTS FOR (f:Flight) ON (f.flightNumber);
CALL db.awaitIndexes(60);

PROFILE
MATCH (f:Flight {flightNumber: 'SU101'})
RETURN f.flightId, f.date;
// Очікуємо: NodeIndexSeek. Порівняйте db hits і час.

// ===== Запит B (лише PROFILE; за бажанням — переписування) =====
PROFILE
MATCH (p:Passenger)<-[:HAS_PASSENGER]-(f:Flight)-[:HAS_DELAY]->(d:FlightDelay)
WHERE d.minutes > 60
RETURN p.name, collect(f.flightId), sum(d.minutes) AS total
ORDER BY total DESC LIMIT 10;
// Підказка: індекс delay_minutes_idx дозволяє почати з FlightDelay (NodeIndexSeek по minutes > 60), а не з Passenger.
