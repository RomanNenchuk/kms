# Результат 3. Запити Cypher та їх результати

Артефакти: `queries/*.cypher`, цей файл. Для кожного запиту: CQ, запит, результат, інтерпретація.
Колонка «Очікується (незалежна перевірка)» — з `scripts/verify_expected.py` (pandas на тих самих CSV); порівняйте з тим, що повернув Neo4j.
Результат вставте скріншотом/таблицею після виконання; інтерпретацію напишіть своїми словами (2–3 речення).

## Q1 — CQ1: Які рейси вилітають із LWO 2026-11-02 і куди? (MATCH, WHERE, ORDER BY)

```cypher
MATCH (f:Flight)-[:DEPARTS_FROM]->(:Airport {iata: 'LWO'}),
      (f)-[:ARRIVES_AT]->(b:Airport)
WHERE f.date = date('2026-11-02')
RETURN f.flightNumber AS flight, f.scheduledDeparture AS departure, b.iata AS destination
ORDER BY departure;
```

**Очікується (незалежна перевірка):** 10 рейсів: CA101→WAW, CA105→KBP, CA109→IFO, CA113→WMI, SU111→FRA, SU115→IST, SU103→WAW, SU107→KIV, SU119→ODS, SU123→RZE (за часом вильоту)

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q2 — CQ2: Куди можна дістатися з LWO не більше ніж з 2 пересадками, тобто <=3 перельоти? (шлях змінної довжини)

```cypher
MATCH p = (a:Airport {iata: 'LWO'})-[:DIRECT_ROUTE*1..3]->(b:Airport)
WHERE a <> b
RETURN b.iata AS airport, min(length(p)) AS minLegs
ORDER BY minLegs, airport;
```

**Очікується (незалежна перевірка):** 44 аеропорти (≤1 політ: 15, ≤2: 34, ≤3: 44)

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q3 — CQ3: Найкоротший маршрут LWO -> OSL (shortestPath)

```cypher
MATCH (a:Airport {iata: 'LWO'}), (b:Airport {iata: 'OSL'})
MATCH p = shortestPath((a)-[:DIRECT_ROUTE*..6]->(b))
RETURN [n IN nodes(p) | n.iata] AS route, length(p) AS legs;
// Увага: найкоротших шляхів кілька (довжина 3), shortestPath повертає ОДИН довільний з них.
```

**Очікується (незалежна перевірка):** довжина 3; один із 5 рівнозначних шляхів (LWO-BER-CPH-OSL, LWO-BER-VNO-OSL, LWO-FRA-VNO-OSL, LWO-WAW-VNO-OSL, LWO-WAW-RIX-OSL)

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q3b — CQ3: усі найкоротші маршрути LWO -> OSL (allShortestPaths)

```cypher
MATCH (a:Airport {iata: 'LWO'}), (b:Airport {iata: 'OSL'})
MATCH p = allShortestPaths((a)-[:DIRECT_ROUTE*..6]->(b))
RETURN [n IN nodes(p) | n.iata] AS route, length(p) AS legs
ORDER BY route;
```

**Очікується (незалежна перевірка):** усі 5 шляхів довжини 3

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q4 — CQ4: Статистика за авіакомпаніями: рейси, затримані рейси, сумарні хвилини (OPTIONAL MATCH + агрегація)

```cypher
MATCH (al:Airline)<-[:OPERATED_BY]-(f:Flight)
OPTIONAL MATCH (f)-[:HAS_DELAY]->(d:FlightDelay)
RETURN al.name AS airline,
       count(DISTINCT f) AS flights,
       count(d) AS delayedFlights,
       coalesce(sum(d.minutes), 0) AS totalDelayMin
ORDER BY totalDelayMin DESC;
```

**Очікується (незалежна перевірка):** AeroLink Europe 48 / 27 / 1203; BaltiCair 32 / 14 / 517; Sky Ukraine 48 / 11 / 393; EuroNord 40 / 8 / 368; MedSky 32 / 3 / 288; CarpathAir 32 / 6 / 179; AlpineWings 24 / 0 / 0; DanubeJet 32 / 0 / 0

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q5 — CQ5: Рейси під ризиком рівня >= 2, для яких затримку НЕ зафіксовано (OPTIONAL MATCH + WITH + IS NULL)

```cypher
MATCH (f:Flight)-[:AFFECTED_BY]->(r:Risk)
WHERE r.level >= 2
OPTIONAL MATCH (f)-[:HAS_DELAY]->(d:FlightDelay)
WITH f, r, d
WHERE d IS NULL
RETURN f.flightId AS flight, r.name AS risk, r.level AS level
ORDER BY level DESC, flight;
```

**Очікується (незалежна перевірка):** 3 рядки: CA101-20261102 (Fog at Lviv, 3), SU122-20261103 (Snowfall at Warsaw, 3), BC110-20261102 (Crosswind at Gdansk, 2)

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q6 — CQ6: Які пасажири найбільше постраждали від затримок > 60 хв? (багатокрокове з'єднання + collect)

```cypher
MATCH (p:Passenger)<-[:HAS_PASSENGER]-(f:Flight)-[:HAS_DELAY]->(d:FlightDelay)
WHERE d.minutes > 60
RETURN p.name AS passenger, collect(f.flightId) AS flights, sum(d.minutes) AS totalMinutes
ORDER BY totalMinutes DESC, passenger
LIMIT 10;
```

**Очікується (незалежна перевірка):** — (перевірте логічно / порівняйте з Q-сусідами)

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q7 — CQ7: Топ-5 пілотів за кількістю рейсів і кількістю різних аеропортів вильоту (WITH + DISTINCT)

```cypher
MATCH (p:Pilot)<-[:HAS_PILOT]-(f:Flight)-[:DEPARTS_FROM]->(a:Airport)
WITH p, count(f) AS flights, count(DISTINCT a) AS airports
RETURN p.name AS pilot, flights, airports
ORDER BY flights DESC, pilot
LIMIT 5;
```

**Очікується (незалежна перевірка):** — (перевірте логічно / порівняйте з Q-сусідами)

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q8 — CQ8: Які судна мають найбільшу середню затримку (мінімум 2 затримки)? (WITH ... WHERE як HAVING)

```cypher
MATCH (ac:Aircraft)<-[:USES_AIRCRAFT]-(f:Flight)-[:HAS_DELAY]->(d:FlightDelay)
WITH ac, count(f) AS delayedFlights, avg(d.minutes) AS avgMin
WHERE delayedFlights >= 2
RETURN ac.registration AS aircraft, ac.model AS model, delayedFlights, round(avgMin, 1) AS avgDelayMin
ORDER BY avgDelayMin DESC;
```

**Очікується (незалежна перевірка):** — (перевірте логічно / порівняйте з Q-сусідами)

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q9 — CQ9: Які аеропорти розташовані в Україні? Транзитивний шлях Airport->City->Country (аналог транзитивності locatedIn з ЛР 8)

```cypher
MATCH (a:Airport)-[:LOCATED_IN|IN_COUNTRY*1..2]->(c:Country {code: 'UA'})
RETURN a.iata AS airport, a.name AS name
ORDER BY airport;
```

**Очікується (незалежна перевірка):** 8 аеропортів: CWC, DNK, HRK, IEV, IFO, KBP, LWO, ODS

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q10 — CQ10: Найбільш завантажені міжнародні напрямки між країнами (агрегація по шляху довжини 2+1+2)

```cypher
MATCH (a:Airport)-[r:DIRECT_ROUTE]->(b:Airport),
      (a)-[:LOCATED_IN]->(:City)-[:IN_COUNTRY]->(ca:Country),
      (b)-[:LOCATED_IN]->(:City)-[:IN_COUNTRY]->(cb:Country)
WHERE ca <> cb
RETURN ca.name AS fromCountry, cb.name AS toCountry, sum(r.flights) AS flights
ORDER BY flights DESC, fromCountry, toCountry
LIMIT 10;
```

**Очікується (незалежна перевірка):** — (перевірте логічно / порівняйте з Q-сусідами)

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q11 — CQ11: Які аеропорти не мають жодного рейсу? (OPTIONAL MATCH + IS NULL)

```cypher
MATCH (a:Airport)
OPTIONAL MATCH (a)<-[r:DEPARTS_FROM|ARRIVES_AT]-(:Flight)
WITH a, count(r) AS n
WHERE n = 0
RETURN a.iata AS airport, a.name AS name
ORDER BY airport;

// ================== АНАЛІЗ ВПЛИВУ (залежності на глибину >= 3) ==================
```

**Очікується (незалежна перевірка):** 5 аеропортів: BEG, CGN, DNK, LIS, TBS

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q12 — CQ12 (impact 1): Туман у Львові (RK01) — які наступні рейси тих самих літаків під ударом (до 4 ніг уперед)?

```cypher
MATCH (r:Risk {riskId: 'RK01'})<-[:AFFECTED_BY]-(f:Flight)
MATCH p = (f)-[:NEXT_LEG*1..4]->(g:Flight)
RETURN g.flightId AS downstreamFlight, min(length(p)) AS depth, count(DISTINCT f) AS fromAffectedFlights
ORDER BY depth, downstreamFlight;
```

**Очікується (незалежна перевірка):** 16 унікальних рейсів: по 4 на кожній глибині 1..4 (4 уражені рейси CA101/105/109/113 за 02.11)

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Q13 — CQ13 (impact 2): Закриття FRA 2026-11-02 — скільки рейсів і пасажирів зачеплено (вильоти з FRA + до 3 наступних ніг)

```cypher
MATCH (:Airport {iata: 'FRA'})<-[:DEPARTS_FROM]-(f:Flight)
WHERE f.date = date('2026-11-02')
MATCH (f)-[:NEXT_LEG*0..3]->(g:Flight)
WITH DISTINCT g
OPTIONAL MATCH (g)-[:HAS_PASSENGER]->(px:Passenger)
RETURN count(DISTINCT g) AS impactedFlights, count(DISTINCT px) AS impactedPassengers;
```

**Очікується (незалежна перевірка):** impactedFlights = 40, impactedPassengers = 48

**Результат у Neo4j:** _(вставте таблицю/скріншот)_

**Інтерпретація:** _(2–3 речення: що це означає для предметної області)_

## Ручна перевірка (C4: ≥ 3 запити)

Оберіть Q1, Q4 і Q13 (або інші 3). Для кожного: (1) відкрийте відповідні рядки в `data/*.csv`; (2) пораховуйте вручну/в Excel;
(3) порівняйте з виводом `python scripts/verify_expected.py` і з Neo4j. Запишіть у таблицю:

| Запит | Як перевіряли вручну | Ручний результат | Результат Neo4j | Збіг |
|---|---|---|---|---|
| Q1 | | | | |
| Q4 | | | | |
| Q13 | | | | |
