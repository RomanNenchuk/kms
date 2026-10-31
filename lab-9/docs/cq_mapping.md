# Результат 1. Графова схема під CQ

Артефакти: `docs/graph_schema.drawio` (редагована діаграма), `docs/graph_schema.png`, цей файл.

## 1. Схема (C1: ≥ 6 міток, ≥ 8 типів зв'язків)

**Мітки (10 основних + 4 додаткові):** Country, City, Airport, Airline, Aircraft, Flight, Pilot, Passenger, Risk, FlightDelay;
додаткові: Person (на Pilot/Passenger), PassengerFlight/CargoFlight (на Flight), WeatherRisk/TechnicalRisk (на Risk).

**Типи зв'язків (15):** IN_COUNTRY, LOCATED_IN, OWNED_BY, DEPARTS_FROM, ARRIVES_AT, OPERATED_BY, USES_AIRCRAFT, HAS_PILOT,
HAS_PASSENGER, AFFECTED_BY, AT_AIRPORT, HAS_DELAY, CAUSED_BY, NEXT_LEG, + похідні DIRECT_ROUTE та ROUTE_LINK (для аналізу маршрутів/GDS).

| Мітка | Ключ (UNIQUE) | Інші властивості |
|---|---|---|
| Country | code | name |
| City | cityId | name |
| Airport | iata | name, pagerank*, community* |
| Airline | code | name, homeCountry |
| Aircraft | registration | model, seatCapacity |
| Flight | flightId | flightNumber, scheduledDeparture, date |
| Pilot (+Person) | pilotId | name, flightHours |
| Passenger (+Person) | passengerId | name |
| Risk | riskId | name, level |
| FlightDelay | delayId | minutes, propagated |

\* записуються GDS (Результат 4).

## 2. Походження на зв'язках (C3)

Кожен зв'язок, завантажений з CSV або похідний, має властивості:
`source` (рядок: `iata-public-codes`, `synthetic-generator-v1`, `synthetic-risk-scenario`, `derived-from-flights`),
`confidence` (0..1), `validFrom` (date). NEXT_LEG додатково має `gapMin`; DIRECT_ROUTE/ROUTE_LINK — `flights`.
У RDF (ЛР 8) для цього потрібні reification або іменовані графи; у LPG властивості лежать прямо на ребрі.

## 3. CQ → шаблон шляху Cypher (C2: ≥ 8)

| № | Компетентнісне питання | Шаблон шляху | Запит |
|---|---|---|---|
| CQ1 | Які рейси вилітають із LWO в задану дату і куди? | `(Flight)-[:DEPARTS_FROM]->(Airport {iata}), (Flight)-[:ARRIVES_AT]->(Airport)` | Q1 |
| CQ2 | Куди можна дістатися з LWO за ≤ 3 перельоти? | `(Airport)-[:DIRECT_ROUTE*1..3]->(Airport)` | Q2 |
| CQ3 | Який найкоротший маршрут між двома аеропортами? | `shortestPath((Airport)-[:DIRECT_ROUTE*..6]->(Airport))` | Q3, Q3b |
| CQ4 | Скільки рейсів і хвилин затримок має кожна авіакомпанія? | `(Airline)<-[:OPERATED_BY]-(Flight) OPTIONAL MATCH (Flight)-[:HAS_DELAY]->(FlightDelay)` | Q4 |
| CQ5 | Які рейси під ризиком мають незафіксовану затримку? | `(Flight)-[:AFFECTED_BY]->(Risk)` + `OPTIONAL MATCH (Flight)-[:HAS_DELAY]->()` | Q5 |
| CQ6 | Які пасажири найбільше постраждали від затримок > 60 хв? | `(Passenger)<-[:HAS_PASSENGER]-(Flight)-[:HAS_DELAY]->(FlightDelay)` | Q6 |
| CQ7 | Які пілоти найактивніші і з скількох аеропортів літають? | `(Pilot)<-[:HAS_PILOT]-(Flight)-[:DEPARTS_FROM]->(Airport)` | Q7 |
| CQ8 | Які судна мають найбільшу середню затримку? | `(Aircraft)<-[:USES_AIRCRAFT]-(Flight)-[:HAS_DELAY]->(FlightDelay)` | Q8 |
| CQ9 | Які аеропорти розташовані в країні X? | `(Airport)-[:LOCATED_IN\|IN_COUNTRY*1..2]->(Country)` | Q9 |
| CQ10 | Які міжнародні напрямки найзавантаженіші? | `(Airport)-[:DIRECT_ROUTE]->(Airport)` + `(…)-[:LOCATED_IN]->(City)-[:IN_COUNTRY]->(Country)` | Q10 |
| CQ11 | Які аеропорти без рейсів? | `(Airport) OPTIONAL MATCH (Airport)<-[:DEPARTS_FROM\|ARRIVES_AT]-(Flight)` | Q11 |
| CQ12 | (вплив) Що постраждає далі від ризику X? | `(Risk)<-[:AFFECTED_BY]-(Flight)-[:NEXT_LEG*1..4]->(Flight)` | Q12 |
| CQ13 | (вплив) Що зачепить закриття аеропорту? | `(Airport)<-[:DEPARTS_FROM]-(Flight)-[:NEXT_LEG*0..3]->(Flight)-[:HAS_PASSENGER]->(Passenger)` | Q13 |

## 4. Порівняння з онтологією ЛР 7/8 (C4: ≥ 5 рядків)

| OWL/RDF (ЛР 7–8) | Property graph (ЛР 9) | Коментар |
|---|---|---|
| `owl:Class` (av:Airport, av:Flight, …) | мітка вузла (`:Airport`, `:Flight`) | 16 класів → 10 основних міток; Place/Country/City/Airport розділені |
| `rdfs:subClassOf` (PassengerFlight ⊂ Flight; Pilot ⊂ Person) | додаткові мітки (`:Flight:PassengerFlight`, `:Pilot:Person`) | у LPG немає автоматичного виведення — мітки проставляються явно при імпорті; у RDF це робив reasoner (І1 в ЛР 8) |
| `owl:ObjectProperty` (av:departsFrom) | тип зв'язку (`DEPARTS_FROM`) | домен/діапазон не декларуються схемою, а лише дисципліною імпорту |
| `owl:DatatypeProperty` (av:flightNumber, av:delayMinutes) | властивість вузла (`flightNumber`, `minutes`) | значення мають типи Neo4j (integer, datetime, date) замість xsd |
| `owl:FunctionalProperty` (departsFrom, arrivesAt) | немає прямого аналога | кардинальність не забезпечується; можна лише через UNIQUE на ключах і перевірки запитом |
| `owl:inverseOf` (delaysFlight ↔ hasDelay) | один зв'язок `HAS_DELAY`, обхід у будь-який бік | у LPG зв'язок напрямлений, але читається в обидва боки без дублювання тріплетів |
| `owl:TransitiveProperty` (locatedIn) | шлях змінної довжини `[:LOCATED_IN\|IN_COUNTRY*1..2]` | транзитивність обчислюється запитом, а не reasoner'ом |
| `owl:disjointWith` | немає; частково — окремі мітки + перевірочні запити | у ЛР 8 це робив SHACL/reasoner |
| IRI (`av:Flight_SU101`) | внутрішній id + бізнес-ключ з UNIQUE (`flightId`) | |
| Походження: reification/named graph, `dcterms:source` на ресурсі | `source`, `confidence`, `validFrom` на ребрі | головна ергономічна перевага LPG для provenance |
| `rdfs:label @en/@uk` | властивості `name` (мови — окремі властивості, якщо потрібно) | |
