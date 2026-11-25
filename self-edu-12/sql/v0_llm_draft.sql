-- v0: ЧЕРНЕТКА, яку запропонувала LLM (до перевірки). Зберігається для порівняння з v1.
-- Не використовувати для роботи: у ній три навмисно залишені й задокументовані дефекти (див. src/flaws.py).

CREATE TABLE v0_dim_airline (
    airline_code  VARCHAR PRIMARY KEY,
    name          VARCHAR,
    country       VARCHAR,
    airline_type  VARCHAR
);

CREATE TABLE v0_dim_aircraft (                     -- SCD2, але БЕЗ сурогатного ключа версії
    registration   VARCHAR,
    aircraft_type  VARCHAR,
    manufacturer   VARCHAR,
    seats          INTEGER,
    valid_from     DATE,
    valid_to       DATE
);

CREATE TABLE v0_fact_flight (
    row_kind        VARCHAR,       -- 'flight' або 'airline_month' (готові місячні підсумки «для швидких звітів»)
    flight_date     DATE,
    flight_number   VARCHAR,
    origin_iata     VARCHAR,
    dest_iata       VARCHAR,
    airline_code    VARCHAR,
    registration    VARCHAR,       -- зв'язок з бортом за бізнес-ключем
    delay_class     VARCHAR,
    delay_subclass  VARCHAR,
    seats           INTEGER,
    passengers      INTEGER,
    delay_minutes   INTEGER,
    revenue_usd     DOUBLE,
    cancelled       INTEGER,
    airframe_hours  DOUBLE,
    load_factor     DOUBLE,        -- збережене відношення passengers / seats
    on_time_pct     DOUBLE,        -- збережене відношення
    avg_delay_min   DOUBLE         -- збережене середнє
);
