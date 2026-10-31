// ЛР 9 / Результат 2 / Крок 2. Обмеження унікальності та індекси (Neo4j 5.x).
// Виконується ПЕРЕД імпортом. IF NOT EXISTS робить скрипт повторюваним.

// --- 8 обмежень унікальності (кожне автоматично створює індекс) ---
CREATE CONSTRAINT country_code   IF NOT EXISTS FOR (n:Country)   REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT city_id        IF NOT EXISTS FOR (n:City)      REQUIRE n.cityId IS UNIQUE;
CREATE CONSTRAINT airport_iata   IF NOT EXISTS FOR (n:Airport)   REQUIRE n.iata IS UNIQUE;
CREATE CONSTRAINT airline_code   IF NOT EXISTS FOR (n:Airline)   REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT aircraft_reg   IF NOT EXISTS FOR (n:Aircraft)  REQUIRE n.registration IS UNIQUE;
CREATE CONSTRAINT flight_id      IF NOT EXISTS FOR (n:Flight)    REQUIRE n.flightId IS UNIQUE;
CREATE CONSTRAINT pilot_id       IF NOT EXISTS FOR (n:Pilot)     REQUIRE n.pilotId IS UNIQUE;
CREATE CONSTRAINT passenger_id   IF NOT EXISTS FOR (n:Passenger) REQUIRE n.passengerId IS UNIQUE;
CREATE CONSTRAINT risk_id        IF NOT EXISTS FOR (n:Risk)      REQUIRE n.riskId IS UNIQUE;
CREATE CONSTRAINT delay_id       IF NOT EXISTS FOR (n:FlightDelay) REQUIRE n.delayId IS UNIQUE;

// --- Додаткові (не пов'язані з обмеженнями) індекси для запитів ---
CREATE INDEX flight_number_idx IF NOT EXISTS FOR (f:Flight) ON (f.flightNumber);
CREATE INDEX flight_date_idx   IF NOT EXISTS FOR (f:Flight) ON (f.date);
CREATE INDEX delay_minutes_idx IF NOT EXISTS FOR (d:FlightDelay) ON (d.minutes);

// --- Перевірка ---
SHOW CONSTRAINTS;
SHOW INDEXES;
