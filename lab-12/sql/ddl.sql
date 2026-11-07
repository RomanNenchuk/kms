-- DuckDB DDL. Зірка: fact_flight + 5 вимірів (dim_airport — role-playing: origin/destination).
-- FOREIGN KEY навмисно не оголошені (типова практика DW): цілісність ключів
-- перевіряється запитами «сиріт» у etl/quality.py. Зв'язки описано в коментарях.

CREATE TABLE IF NOT EXISTS dim_date (
    date_key     INTEGER PRIMARY KEY,          -- YYYYMMDD
    full_date    DATE NOT NULL,
    year         INTEGER NOT NULL,
    quarter      INTEGER NOT NULL,
    month        INTEGER NOT NULL,
    month_name   VARCHAR NOT NULL,
    day          INTEGER NOT NULL,
    day_of_week  INTEGER NOT NULL,             -- 1 = понеділок ... 7 = неділя
    day_name     VARCHAR NOT NULL,
    is_weekend   BOOLEAN NOT NULL,
    season       VARCHAR NOT NULL              -- Winter/Spring/Summer/Autumn
);

CREATE TABLE IF NOT EXISTS dim_airport (        -- SCD тип 1
    airport_key  INTEGER PRIMARY KEY,
    iata         VARCHAR NOT NULL UNIQUE,
    name         VARCHAR NOT NULL,
    city         VARCHAR NOT NULL,
    country      VARCHAR NOT NULL,             -- ієрархія: country -> city -> airport
    latitude     DOUBLE NOT NULL,
    longitude    DOUBLE NOT NULL,
    is_hub       BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_airline (        -- SCD тип 1
    airline_key   INTEGER PRIMARY KEY,
    airline_code  VARCHAR NOT NULL UNIQUE,
    name          VARCHAR NOT NULL,
    country       VARCHAR NOT NULL,
    airline_type  VARCHAR NOT NULL             -- full-service / low-cost / regional
);

CREATE TABLE IF NOT EXISTS dim_aircraft (       -- SCD тип 2 (переобладнання салону змінює seats)
    aircraft_key   INTEGER PRIMARY KEY,        -- сурогатний ключ версії
    registration   VARCHAR NOT NULL,           -- природний (бізнес) ключ
    aircraft_type  VARCHAR NOT NULL,           -- ієрархія: manufacturer -> aircraft_type -> registration
    manufacturer   VARCHAR NOT NULL,
    seats          INTEGER NOT NULL,
    valid_from     DATE NOT NULL,              -- інтервал [valid_from, valid_to)
    valid_to       DATE NOT NULL,              -- 9999-12-31 для поточної версії
    is_current     BOOLEAN NOT NULL,
    UNIQUE (registration, valid_from)
);

CREATE TABLE IF NOT EXISTS dim_delay_cause (    -- ВИМІР-ТАКСОНОМІЯ (IRI), SCD тип 1
    delay_cause_key  INTEGER PRIMARY KEY,      -- ключ листа таксономії (підкласу)
    subclass_iri     VARCHAR NOT NULL UNIQUE,  -- IRI підкласу
    subclass_label   VARCHAR NOT NULL,
    class_iri        VARCHAR NOT NULL,         -- IRI класу (рівень вище): клас -> підклас
    class_label      VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_flight (
    flight_id           BIGINT PRIMARY KEY,
    -- зв'язки з вимірами
    date_key            INTEGER NOT NULL,      -- -> dim_date
    origin_airport_key  INTEGER NOT NULL,      -- -> dim_airport (role: origin)
    dest_airport_key    INTEGER NOT NULL,      -- -> dim_airport (role: destination)
    airline_key         INTEGER NOT NULL,      -- -> dim_airline
    aircraft_key        INTEGER NOT NULL,      -- -> dim_aircraft (версія на дату рейсу)
    delay_cause_key     INTEGER NOT NULL,      -- -> dim_delay_cause (лист таксономії)
    -- вироджені виміри
    flight_number       VARCHAR NOT NULL,
    scheduled_dep_hour  SMALLINT NOT NULL,
    -- міри
    distance_km         DOUBLE NOT NULL,       -- адитивна
    seats               INTEGER NOT NULL,      -- адитивна (запропоновані місця)
    passengers          INTEGER NOT NULL,      -- адитивна
    delay_minutes       INTEGER NOT NULL,      -- адитивна
    fuel_kg             DOUBLE NOT NULL,       -- адитивна
    revenue_usd         DOUBLE NOT NULL,       -- адитивна
    cancelled           SMALLINT NOT NULL,     -- 0/1, адитивна (кількість скасувань)
    airframe_hours      DOUBLE NOT NULL        -- НАПІВАДИТИВНА (залишок/лічильник: сума по бортах, але не в часі)
);
