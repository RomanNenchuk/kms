-- СР12. Зіркова схема v1 (виправлена): виконання регулярних пасажирських рейсів.
-- ЗЕРНО: один рядок fact_flight = один виліт (flight leg) конкретного борту (версії борту) в конкретну дату
--        між парою аеропортів. Скасований рейс теж є рядком. Природного ключа немає (номер рейсу
--        у даних повторюється навіть в межах доби), тому унікальність забезпечує сурогатний flight_id.
-- Діалект: DuckDB. Скрипт запускається на порожній БД (src/build_db.py).

CREATE TABLE dim_date (
    date_key     INTEGER PRIMARY KEY,              -- YYYYMMDD
    full_date    DATE    NOT NULL UNIQUE,
    year         INTEGER NOT NULL,                 -- ієрархія: year > quarter > month > day
    quarter      INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month        INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name   VARCHAR NOT NULL,
    day          INTEGER NOT NULL,
    day_of_week  INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    day_name     VARCHAR NOT NULL,
    is_weekend   BOOLEAN NOT NULL,
    season       VARCHAR NOT NULL
);

CREATE TABLE dim_airport (                         -- SCD тип 1; role-playing: origin / destination
    airport_key  INTEGER PRIMARY KEY,
    iata         VARCHAR NOT NULL UNIQUE,
    name         VARCHAR NOT NULL,
    city         VARCHAR NOT NULL,                 -- ієрархія: country > city > airport
    country      VARCHAR NOT NULL,
    latitude     DOUBLE  NOT NULL,
    longitude    DOUBLE  NOT NULL,
    is_hub       BOOLEAN NOT NULL
);

CREATE TABLE dim_airline (                         -- SCD тип 1
    airline_key   INTEGER PRIMARY KEY,
    airline_code  VARCHAR NOT NULL UNIQUE,
    name          VARCHAR NOT NULL,
    country       VARCHAR NOT NULL,
    airline_type  VARCHAR NOT NULL                 -- ієрархія: airline_type > airline
);

CREATE TABLE dim_aircraft (                        -- SCD тип 2: нова версія при зміні seats
    aircraft_key   INTEGER PRIMARY KEY,            -- сурогатний ключ ВЕРСІЇ борту
    registration   VARCHAR NOT NULL,               -- бізнес-ключ борту (повторюється між версіями)
    aircraft_type  VARCHAR NOT NULL,               -- ієрархія: manufacturer > aircraft_type > registration
    manufacturer   VARCHAR NOT NULL,
    seats          INTEGER NOT NULL CHECK (seats > 0),
    valid_from     DATE    NOT NULL,               -- версія діє на [valid_from, valid_to)
    valid_to       DATE    NOT NULL,               -- 9999-12-31 для поточної версії
    is_current     BOOLEAN NOT NULL,
    UNIQUE (registration, valid_from),
    CHECK (valid_from < valid_to)
);

CREATE TABLE dim_delay_cause (                     -- вимір-таксономія, SCD тип 1
    delay_cause_key  INTEGER PRIMARY KEY,          -- ключ листа таксономії
    subclass_iri     VARCHAR NOT NULL UNIQUE,
    subclass_label   VARCHAR NOT NULL,             -- ієрархія: class > subclass
    class_iri        VARCHAR NOT NULL,
    class_label      VARCHAR NOT NULL
);

CREATE TABLE fact_flight (
    flight_id           BIGINT  PRIMARY KEY,       -- сурогатний ключ факту
    date_key            INTEGER NOT NULL REFERENCES dim_date (date_key),
    origin_airport_key  INTEGER NOT NULL REFERENCES dim_airport (airport_key),
    dest_airport_key    INTEGER NOT NULL REFERENCES dim_airport (airport_key),
    airline_key         INTEGER NOT NULL REFERENCES dim_airline (airline_key),
    aircraft_key        INTEGER NOT NULL REFERENCES dim_aircraft (aircraft_key),   -- версія на дату рейсу
    delay_cause_key     INTEGER NOT NULL REFERENCES dim_delay_cause (delay_cause_key),
    flight_number       VARCHAR NOT NULL,          -- вироджений вимір (не унікальний)
    scheduled_dep_hour  SMALLINT NOT NULL CHECK (scheduled_dep_hour BETWEEN 0 AND 23),
    -- адитивні міри
    distance_km         DOUBLE  NOT NULL CHECK (distance_km > 0),
    seats               INTEGER NOT NULL CHECK (seats > 0),
    passengers          INTEGER NOT NULL CHECK (passengers >= 0),
    delay_minutes       INTEGER NOT NULL CHECK (delay_minutes >= 0),
    fuel_kg             DOUBLE  NOT NULL CHECK (fuel_kg >= 0),
    revenue_usd         DOUBLE  NOT NULL CHECK (revenue_usd >= 0),
    cancelled           SMALLINT NOT NULL CHECK (cancelled IN (0, 1)),
    -- напівадитивна міра (лічильник): сумується по бортах, у часі беремо MAX/останнє
    airframe_hours      DOUBLE  NOT NULL,
    CHECK (passengers <= seats)
);
