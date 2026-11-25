"""C3: DDL виконується, ключі й зерно працюють як обмеження; дані відповідають оголошеній семантиці."""
import duckdb
import pytest


def test_row_counts(con, frames):
    for t, df in frames.items():
        assert con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == len(df)


def test_pk_unique_and_not_null(con):
    assert con.execute("SELECT COUNT(*) - COUNT(DISTINCT flight_id) FROM fact_flight").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) - COUNT(DISTINCT aircraft_key) FROM dim_aircraft").fetchone()[0] == 0


def test_no_orphans(con):
    for col, dim, key in [("date_key", "dim_date", "date_key"), ("origin_airport_key", "dim_airport", "airport_key"),
                          ("dest_airport_key", "dim_airport", "airport_key"), ("airline_key", "dim_airline", "airline_key"),
                          ("aircraft_key", "dim_aircraft", "aircraft_key"), ("delay_cause_key", "dim_delay_cause", "delay_cause_key")]:
        n = con.execute(f"SELECT COUNT(*) FROM fact_flight f LEFT JOIN {dim} d ON f.{col}=d.{key} WHERE d.{key} IS NULL").fetchone()[0]
        assert n == 0, col


def test_foreign_key_is_enforced(con):
    with pytest.raises(duckdb.ConstraintException):
        con.execute("""INSERT INTO fact_flight (flight_id, date_key, origin_airport_key, dest_airport_key, airline_key, aircraft_key, delay_cause_key, flight_number, scheduled_dep_hour, distance_km, seats, passengers, delay_minutes, fuel_kg, revenue_usd, cancelled, airframe_hours)
                       VALUES (999999, 20250101, 999, 1, 1, 1, 1, 'X1', 10, 500, 100, 50, 0, 1000, 1000, 0, 100)""")


def test_check_constraint_passengers_le_seats(con):
    with pytest.raises(duckdb.ConstraintException):
        con.execute("""INSERT INTO fact_flight (flight_id, date_key, origin_airport_key, dest_airport_key, airline_key, aircraft_key, delay_cause_key, flight_number, scheduled_dep_hour, distance_km, seats, passengers, delay_minutes, fuel_kg, revenue_usd, cancelled, airframe_hours)
                       VALUES (999998, 20250101, 1, 2, 1, 1, 1, 'X1', 10, 500, 100, 150, 0, 1000, 1000, 0, 100)""")


def test_scd2_intervals_do_not_overlap_and_are_contiguous(con):
    rows = con.execute("""SELECT registration, valid_from, valid_to, is_current FROM dim_aircraft
                          ORDER BY registration, valid_from""").fetchall()
    by_reg = {}
    for reg, vf, vt, cur in rows:
        by_reg.setdefault(reg, []).append((vf, vt, cur))
    assert any(len(v) > 1 for v in by_reg.values()), "у даних має бути хоча б одна борт із декількома версіями"
    for reg, versions in by_reg.items():
        assert sum(1 for *_, cur in versions if cur) == 1, reg           # рівно одна поточна версія
        for (vf1, vt1, _), (vf2, _vt2, _) in zip(versions, versions[1:]):
            assert vt1 == vf2, reg                                        # без дір і перетинів


def test_each_flight_uses_the_aircraft_version_valid_on_its_date(con):
    bad = con.execute("""SELECT COUNT(*) FROM fact_flight f
                         JOIN dim_aircraft a ON f.aircraft_key = a.aircraft_key
                         JOIN dim_date d ON f.date_key = d.date_key
                         WHERE NOT (d.full_date >= a.valid_from AND d.full_date < a.valid_to)""").fetchone()[0]
    assert bad == 0


def test_fact_seats_equals_seats_of_that_version(con):
    bad = con.execute("""SELECT COUNT(*) FROM fact_flight f JOIN dim_aircraft a ON f.aircraft_key = a.aircraft_key
                         WHERE f.seats <> a.seats""").fetchone()[0]
    assert bad == 0


def test_cancelled_flights_carry_no_traffic(con):
    bad = con.execute("""SELECT COUNT(*) FROM fact_flight WHERE cancelled = 1
                         AND (passengers <> 0 OR revenue_usd <> 0 OR delay_minutes <> 0)""").fetchone()[0]
    assert bad == 0


def test_hierarchies_are_functional(con):
    """Кожен нижчий рівень має рівно одного предка (інакше drill-down задвоює)."""
    checks = {
        "dim_airport": "SELECT COUNT(*) FROM (SELECT city FROM dim_airport GROUP BY city HAVING COUNT(DISTINCT country) > 1)",
        "dim_delay_cause": "SELECT COUNT(*) FROM (SELECT subclass_label FROM dim_delay_cause GROUP BY subclass_label HAVING COUNT(DISTINCT class_label) > 1)",
        "dim_aircraft": "SELECT COUNT(*) FROM (SELECT aircraft_type FROM dim_aircraft GROUP BY aircraft_type HAVING COUNT(DISTINCT manufacturer) > 1)",
        "dim_date": "SELECT COUNT(*) FROM (SELECT month FROM dim_date GROUP BY month HAVING COUNT(DISTINCT quarter) > 1)",
        "dim_airline": "SELECT COUNT(*) FROM (SELECT name FROM dim_airline GROUP BY name HAVING COUNT(DISTINCT airline_type) > 1)",
    }
    for t, sql in checks.items():
        assert con.execute(sql).fetchone()[0] == 0, t
