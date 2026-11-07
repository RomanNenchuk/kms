"""Перевірки якості. Кожна: (назва, опис, SQL), SQL повертає КІЛЬКІСТЬ порушень (0 = ок)."""


def _orphan(name: str, fk: str, dim: str, pk: str):
    return (f"orphan_{name}", f"Немає «сиріт»: fact_flight.{fk} -> {dim}.{pk}",
            f"SELECT COUNT(*) FROM fact_flight f LEFT JOIN {dim} d ON f.{fk} = d.{pk} WHERE d.{pk} IS NULL")


CHECKS = [
    # --- унікальність
    ("unique_flight_id", "flight_id унікальний",
     "SELECT COUNT(*) - COUNT(DISTINCT flight_id) FROM fact_flight"),
    ("unique_iata", "IATA-коди аеропортів унікальні",
     "SELECT COUNT(*) - COUNT(DISTINCT iata) FROM dim_airport"),
    ("unique_taxonomy_iri", "IRI підкласів унікальні",
     "SELECT COUNT(*) - COUNT(DISTINCT subclass_iri) FROM dim_delay_cause"),
    # --- not null
    ("not_null_fact", "Ключі та міри факту без NULL",
     """SELECT COUNT(*) FROM fact_flight WHERE date_key IS NULL OR origin_airport_key IS NULL
        OR dest_airport_key IS NULL OR airline_key IS NULL OR aircraft_key IS NULL
        OR delay_cause_key IS NULL OR distance_km IS NULL OR seats IS NULL OR passengers IS NULL
        OR delay_minutes IS NULL OR fuel_kg IS NULL OR revenue_usd IS NULL OR cancelled IS NULL"""),
    # --- діапазони
    ("range_passengers", "0 <= passengers <= seats",
     "SELECT COUNT(*) FROM fact_flight WHERE passengers < 0 OR passengers > seats"),
    ("range_delay", "0 <= delay_minutes <= 1440",
     "SELECT COUNT(*) FROM fact_flight WHERE delay_minutes < 0 OR delay_minutes > 1440"),
    ("range_distance", "0 < distance_km <= 5000",
     "SELECT COUNT(*) FROM fact_flight WHERE distance_km <= 0 OR distance_km > 5000"),
    ("range_money_fuel", "revenue_usd >= 0 та fuel_kg >= 0",
     "SELECT COUNT(*) FROM fact_flight WHERE revenue_usd < 0 OR fuel_kg < 0"),
    ("origin_ne_dest", "Аеропорт вильоту != аеропорт призначення",
     "SELECT COUNT(*) FROM fact_flight WHERE origin_airport_key = dest_airport_key"),
    # --- бізнес-правила
    ("cancelled_consistency", "cancelled ∈ {0,1}; скасований => пасажири/дохід/затримка = 0",
     """SELECT COUNT(*) FROM fact_flight WHERE cancelled NOT IN (0, 1)
        OR (cancelled = 1 AND (passengers <> 0 OR revenue_usd <> 0 OR delay_minutes <> 0))"""),
    ("on_time_cause", "Затримка <= 14 хв <=> причина NoDelay (для нескасованих)",
     """SELECT COUNT(*) FROM fact_flight f JOIN dim_delay_cause c USING (delay_cause_key)
        WHERE cancelled = 0 AND ((delay_minutes <= 14) <> (c.class_label = 'No delay'))"""),
    # --- SCD2
    ("scd2_one_current", "Для кожного борту рівно одна поточна версія",
     """SELECT COUNT(*) FROM (SELECT registration FROM dim_aircraft
        GROUP BY registration HAVING SUM(is_current::INT) <> 1)"""),
    ("scd2_no_overlap", "Версії борту не перетинаються",
     """SELECT COUNT(*) FROM dim_aircraft a JOIN dim_aircraft b
        ON a.registration = b.registration AND a.aircraft_key < b.aircraft_key
        AND a.valid_from < b.valid_to AND b.valid_from < a.valid_to"""),
    ("scd2_fact_in_validity", "Дата рейсу в інтервалі валідності версії борту",
     """SELECT COUNT(*) FROM fact_flight f
        JOIN dim_date d USING (date_key) JOIN dim_aircraft a USING (aircraft_key)
        WHERE d.full_date < a.valid_from OR d.full_date >= a.valid_to"""),
    ("seats_match_aircraft", "fact.seats = dim_aircraft.seats",
     "SELECT COUNT(*) FROM fact_flight f JOIN dim_aircraft a USING (aircraft_key) WHERE f.seats <> a.seats"),
    # --- сироти (C2)
    _orphan("date", "date_key", "dim_date", "date_key"),
    _orphan("origin", "origin_airport_key", "dim_airport", "airport_key"),
    _orphan("dest", "dest_airport_key", "dim_airport", "airport_key"),
    _orphan("airline", "airline_key", "dim_airline", "airline_key"),
    _orphan("aircraft", "aircraft_key", "dim_aircraft", "aircraft_key"),
    _orphan("delay_cause", "delay_cause_key", "dim_delay_cause", "delay_cause_key"),
]
