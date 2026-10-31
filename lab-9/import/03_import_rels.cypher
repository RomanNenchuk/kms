// ЛР 9 / Результат 2 / Крок 3. Імпорт зв'язків (з властивостями походження source, confidence, validFrom).
// Ідемпотентний: MERGE зв'язку + SET властивостей. Запускати ПІСЛЯ 02_import_nodes.cypher.

LOAD CSV WITH HEADERS FROM 'file:///rel_in_country.csv' AS row
MATCH (s:City {cityId: row.startId})
MATCH (e:Country {code: row.endId})
MERGE (s)-[r:IN_COUNTRY]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_located_in.csv' AS row
MATCH (s:Airport {iata: row.startId})
MATCH (e:City {cityId: row.endId})
MERGE (s)-[r:LOCATED_IN]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_owned_by.csv' AS row
MATCH (s:Aircraft {registration: row.startId})
MATCH (e:Airline {code: row.endId})
MERGE (s)-[r:OWNED_BY]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_departs_from.csv' AS row
MATCH (s:Flight {flightId: row.startId})
MATCH (e:Airport {iata: row.endId})
MERGE (s)-[r:DEPARTS_FROM]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_arrives_at.csv' AS row
MATCH (s:Flight {flightId: row.startId})
MATCH (e:Airport {iata: row.endId})
MERGE (s)-[r:ARRIVES_AT]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_operated_by.csv' AS row
MATCH (s:Flight {flightId: row.startId})
MATCH (e:Airline {code: row.endId})
MERGE (s)-[r:OPERATED_BY]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_uses_aircraft.csv' AS row
MATCH (s:Flight {flightId: row.startId})
MATCH (e:Aircraft {registration: row.endId})
MERGE (s)-[r:USES_AIRCRAFT]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_has_pilot.csv' AS row
MATCH (s:Flight {flightId: row.startId})
MATCH (e:Pilot {pilotId: row.endId})
MERGE (s)-[r:HAS_PILOT]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_has_passenger.csv' AS row
MATCH (s:Flight {flightId: row.startId})
MATCH (e:Passenger {passengerId: row.endId})
MERGE (s)-[r:HAS_PASSENGER]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_affected_by.csv' AS row
MATCH (s:Flight {flightId: row.startId})
MATCH (e:Risk {riskId: row.endId})
MERGE (s)-[r:AFFECTED_BY]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_at_airport.csv' AS row
MATCH (s:Risk {riskId: row.startId})
MATCH (e:Airport {iata: row.endId})
MERGE (s)-[r:AT_AIRPORT]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_has_delay.csv' AS row
MATCH (s:Flight {flightId: row.startId})
MATCH (e:FlightDelay {delayId: row.endId})
MERGE (s)-[r:HAS_DELAY]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_caused_by.csv' AS row
MATCH (s:FlightDelay {delayId: row.startId})
MATCH (e:Risk {riskId: row.endId})
MERGE (s)-[r:CAUSED_BY]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rel_next_leg.csv' AS row
MATCH (s:Flight {flightId: row.startId})
MATCH (e:Flight {flightId: row.endId})
MERGE (s)-[r:NEXT_LEG]->(e)
SET r.source = row.source, r.confidence = toFloat(row.confidence), r.validFrom = date(row.validFrom), r.gapMin = toInteger(row.gapMin);

// ---------- Похідні зв'язки (виводяться з рейсів) ----------
// DIRECT_ROUTE: прямий маршрут між аеропортами (аналог CONSTRUCT з ЛР 8, Q6); flights — кількість рейсів.
MATCH (f:Flight)-[:DEPARTS_FROM]->(a:Airport), (f)-[:ARRIVES_AT]->(b:Airport)
WITH a, b, count(f) AS n
MERGE (a)-[r:DIRECT_ROUTE]->(b)
SET r.flights = n, r.source = 'derived-from-flights', r.confidence = 1.0, r.validFrom = date('2026-11-02');

// ROUTE_LINK: один зв'язок на пару аеропортів (сума в обидва боки) — вхід для Louvain (без паралельних ребер).
MATCH (a:Airport)-[r:DIRECT_ROUTE]->(b:Airport)
WITH CASE WHEN a.iata < b.iata THEN a ELSE b END AS x,
     CASE WHEN a.iata < b.iata THEN b ELSE a END AS y,
     sum(r.flights) AS n
MERGE (x)-[l:ROUTE_LINK]->(y)
SET l.flights = n, l.source = 'derived-from-flights', l.confidence = 1.0, l.validFrom = date('2026-11-02');
