// ЛР 9 / Результат 3. Запити Cypher. Кожен запускати окремо в Neo4j Browser (або cypher-shell).
// Формат: CQ -> запит. Результат та інтерпретацію вписати в docs/cypher_results.md.

// ---------- Q1 | CQ1: Які рейси вилітають із LWO 2026-11-02 і куди? (MATCH, WHERE, ORDER BY) ----------
MATCH (f:Flight)-[:DEPARTS_FROM]->(:Airport {iata: 'LWO'}),
      (f)-[:ARRIVES_AT]->(b:Airport)
WHERE f.date = date('2026-11-02')
RETURN f.flightNumber AS flight, f.scheduledDeparture AS departure, b.iata AS destination
ORDER BY departure;

// ---------- Q2 | CQ2: Куди можна дістатися з LWO не більше ніж з 2 пересадками, тобто <=3 перельоти? (шлях змінної довжини) ----------
MATCH p = (a:Airport {iata: 'LWO'})-[:DIRECT_ROUTE*1..3]->(b:Airport)
WHERE a <> b
RETURN b.iata AS airport, min(length(p)) AS minLegs
ORDER BY minLegs, airport;

// ---------- Q3 | CQ3: Найкоротший маршрут LWO -> OSL (shortestPath) ----------
MATCH (a:Airport {iata: 'LWO'}), (b:Airport {iata: 'OSL'})
MATCH p = shortestPath((a)-[:DIRECT_ROUTE*..6]->(b))
RETURN [n IN nodes(p) | n.iata] AS route, length(p) AS legs;
// Увага: найкоротших шляхів кілька (довжина 3), shortestPath повертає ОДИН довільний з них.

// ---------- Q3b | CQ3: усі найкоротші маршрути LWO -> OSL (allShortestPaths) ----------
MATCH (a:Airport {iata: 'LWO'}), (b:Airport {iata: 'OSL'})
MATCH p = allShortestPaths((a)-[:DIRECT_ROUTE*..6]->(b))
RETURN [n IN nodes(p) | n.iata] AS route, length(p) AS legs
ORDER BY route;

// ---------- Q4 | CQ4: Статистика за авіакомпаніями: рейси, затримані рейси, сумарні хвилини (OPTIONAL MATCH + агрегація) ----------
MATCH (al:Airline)<-[:OPERATED_BY]-(f:Flight)
OPTIONAL MATCH (f)-[:HAS_DELAY]->(d:FlightDelay)
RETURN al.name AS airline,
       count(DISTINCT f) AS flights,
       count(d) AS delayedFlights,
       coalesce(sum(d.minutes), 0) AS totalDelayMin
ORDER BY totalDelayMin DESC;

// ---------- Q5 | CQ5: Рейси під ризиком рівня >= 2, для яких затримку НЕ зафіксовано (OPTIONAL MATCH + WITH + IS NULL) ----------
MATCH (f:Flight)-[:AFFECTED_BY]->(r:Risk)
WHERE r.level >= 2
OPTIONAL MATCH (f)-[:HAS_DELAY]->(d:FlightDelay)
WITH f, r, d
WHERE d IS NULL
RETURN f.flightId AS flight, r.name AS risk, r.level AS level
ORDER BY level DESC, flight;

// ---------- Q6 | CQ6: Які пасажири найбільше постраждали від затримок > 60 хв? (багатокрокове з'єднання + collect) ----------
MATCH (p:Passenger)<-[:HAS_PASSENGER]-(f:Flight)-[:HAS_DELAY]->(d:FlightDelay)
WHERE d.minutes > 60
RETURN p.name AS passenger, collect(f.flightId) AS flights, sum(d.minutes) AS totalMinutes
ORDER BY totalMinutes DESC, passenger
LIMIT 10;

// ---------- Q7 | CQ7: Топ-5 пілотів за кількістю рейсів і кількістю різних аеропортів вильоту (WITH + DISTINCT) ----------
MATCH (p:Pilot)<-[:HAS_PILOT]-(f:Flight)-[:DEPARTS_FROM]->(a:Airport)
WITH p, count(f) AS flights, count(DISTINCT a) AS airports
RETURN p.name AS pilot, flights, airports
ORDER BY flights DESC, pilot
LIMIT 5;

// ---------- Q8 | CQ8: Які судна мають найбільшу середню затримку (мінімум 2 затримки)? (WITH ... WHERE як HAVING) ----------
MATCH (ac:Aircraft)<-[:USES_AIRCRAFT]-(f:Flight)-[:HAS_DELAY]->(d:FlightDelay)
WITH ac, count(f) AS delayedFlights, avg(d.minutes) AS avgMin
WHERE delayedFlights >= 2
RETURN ac.registration AS aircraft, ac.model AS model, delayedFlights, round(avgMin, 1) AS avgDelayMin
ORDER BY avgDelayMin DESC;

// ---------- Q9 | CQ9: Які аеропорти розташовані в Україні? Транзитивний шлях Airport->City->Country (аналог транзитивності locatedIn з ЛР 8) ----------
MATCH (a:Airport)-[:LOCATED_IN|IN_COUNTRY*1..2]->(c:Country {code: 'UA'})
RETURN a.iata AS airport, a.name AS name
ORDER BY airport;

// ---------- Q10 | CQ10: Найбільш завантажені міжнародні напрямки між країнами (агрегація по шляху довжини 2+1+2) ----------
MATCH (a:Airport)-[r:DIRECT_ROUTE]->(b:Airport),
      (a)-[:LOCATED_IN]->(:City)-[:IN_COUNTRY]->(ca:Country),
      (b)-[:LOCATED_IN]->(:City)-[:IN_COUNTRY]->(cb:Country)
WHERE ca <> cb
RETURN ca.name AS fromCountry, cb.name AS toCountry, sum(r.flights) AS flights
ORDER BY flights DESC, fromCountry, toCountry
LIMIT 10;

// ---------- Q11 | CQ11: Які аеропорти не мають жодного рейсу? (OPTIONAL MATCH + IS NULL) ----------
MATCH (a:Airport)
OPTIONAL MATCH (a)<-[r:DEPARTS_FROM|ARRIVES_AT]-(:Flight)
WITH a, count(r) AS n
WHERE n = 0
RETURN a.iata AS airport, a.name AS name
ORDER BY airport;

// ================== АНАЛІЗ ВПЛИВУ (залежності на глибину >= 3) ==================

// ---------- Q12 | CQ12 (impact 1): Туман у Львові (RK01) — які наступні рейси тих самих літаків під ударом (до 4 ніг уперед)? ----------
MATCH (r:Risk {riskId: 'RK01'})<-[:AFFECTED_BY]-(f:Flight)
MATCH p = (f)-[:NEXT_LEG*1..4]->(g:Flight)
RETURN g.flightId AS downstreamFlight, min(length(p)) AS depth, count(DISTINCT f) AS fromAffectedFlights
ORDER BY depth, downstreamFlight;

// ---------- Q13 | CQ13 (impact 2): Закриття FRA 2026-11-02 — скільки рейсів і пасажирів зачеплено (вильоти з FRA + до 3 наступних ніг) ----------
MATCH (:Airport {iata: 'FRA'})<-[:DEPARTS_FROM]-(f:Flight)
WHERE f.date = date('2026-11-02')
MATCH (f)-[:NEXT_LEG*0..3]->(g:Flight)
WITH DISTINCT g
OPTIONAL MATCH (g)-[:HAS_PASSENGER]->(px:Passenger)
RETURN count(DISTINCT g) AS impactedFlights, count(DISTINCT px) AS impactedPassengers;
