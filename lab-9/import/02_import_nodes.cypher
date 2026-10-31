// ЛР 9 / Результат 2 / Крок 3. Імпорт вузлів. Ідемпотентний (MERGE по ключу + SET).
// CSV мають лежати в каталозі import сервера Neo4j (Docker: /var/lib/neo4j/import).

LOAD CSV WITH HEADERS FROM 'file:///countries.csv' AS row
MERGE (c:Country {code: row.code})
SET c.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///cities.csv' AS row
MERGE (c:City {cityId: row.cityId})
SET c.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///airports.csv' AS row
MERGE (a:Airport {iata: row.iata})
SET a.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///airlines.csv' AS row
MERGE (al:Airline {code: row.code})
SET al.name = row.name, al.homeCountry = row.homeCountry;

LOAD CSV WITH HEADERS FROM 'file:///aircraft.csv' AS row
MERGE (ac:Aircraft {registration: row.registration})
SET ac.model = row.model, ac.seatCapacity = toInteger(row.seatCapacity);

LOAD CSV WITH HEADERS FROM 'file:///pilots.csv' AS row
MERGE (p:Pilot {pilotId: row.pilotId})
SET p:Person, p.name = row.name, p.flightHours = toInteger(row.flightHours);

LOAD CSV WITH HEADERS FROM 'file:///passengers.csv' AS row
MERGE (p:Passenger {passengerId: row.passengerId})
SET p:Person, p.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///flights.csv' AS row
MERGE (f:Flight {flightId: row.flightId})
SET f.flightNumber = row.flightNumber,
    f.scheduledDeparture = datetime(row.scheduledDeparture),
    f.date = date(row.date)
FOREACH (_ IN CASE WHEN row.kind = 'passenger' THEN [1] ELSE [] END | SET f:PassengerFlight)
FOREACH (_ IN CASE WHEN row.kind = 'cargo'     THEN [1] ELSE [] END | SET f:CargoFlight);

LOAD CSV WITH HEADERS FROM 'file:///risks.csv' AS row
MERGE (r:Risk {riskId: row.riskId})
SET r.name = row.name, r.level = toInteger(row.level)
FOREACH (_ IN CASE WHEN row.kind = 'weather'   THEN [1] ELSE [] END | SET r:WeatherRisk)
FOREACH (_ IN CASE WHEN row.kind = 'technical' THEN [1] ELSE [] END | SET r:TechnicalRisk);

LOAD CSV WITH HEADERS FROM 'file:///delays.csv' AS row
MERGE (d:FlightDelay {delayId: row.delayId})
SET d.minutes = toInteger(row.minutes), d.propagated = (row.propagated = 'true');
