"""Створює БД DuckDB: схема v1 (sql/v1_star.sql) + чернетка v0 (sql/v0_llm_draft.sql) для порівняння."""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SQL = ROOT / "sql"
DB_PATH = ROOT / "db" / "sr12.duckdb"

# порядок важливий: спочатку виміри, потім факт (зовнішні ключі)
LOAD_ORDER = ["dim_date", "dim_airport", "dim_airline", "dim_aircraft", "dim_delay_cause", "fact_flight"]


def run_script(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    con.execute(path.read_text(encoding="utf-8"))


def build_v1(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    run_script(con, SQL / "v1_star.sql")
    counts = {}
    for t in LOAD_ORDER:
        cols = [r[0] for r in con.execute(f"DESCRIBE {t}").fetchall()]
        col_list = ", ".join(cols)
        con.execute(f"INSERT INTO {t} ({col_list}) SELECT {col_list} FROM read_parquet('{(DATA / (t + '.parquet')).as_posix()}')")
        counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return counts


def build_v0(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Відтворює v0 з тих самих даних: рядки рейсів + місячні підсумки в одній таблиці."""
    run_script(con, SQL / "v0_llm_draft.sql")
    con.execute("""
        INSERT INTO v0_dim_airline
        SELECT airline_code, name, country, airline_type FROM dim_airline""")
    con.execute("""
        INSERT INTO v0_dim_aircraft
        SELECT registration, aircraft_type, manufacturer, seats, valid_from, valid_to FROM dim_aircraft""")
    con.execute("""
        INSERT INTO v0_fact_flight
        SELECT 'flight', d.full_date, f.flight_number, o.iata, de.iata, al.airline_code, a.registration,
               c.class_label, c.subclass_label, f.seats, f.passengers, f.delay_minutes, f.revenue_usd,
               f.cancelled, f.airframe_hours,
               f.passengers * 1.0 / f.seats,
               CASE WHEN f.cancelled = 0 AND f.delay_minutes <= 14 THEN 100.0 ELSE 0.0 END,
               f.delay_minutes
        FROM fact_flight f
        JOIN dim_date d ON f.date_key = d.date_key
        JOIN dim_airport o ON f.origin_airport_key = o.airport_key
        JOIN dim_airport de ON f.dest_airport_key = de.airport_key
        JOIN dim_airline al ON f.airline_key = al.airline_key
        JOIN dim_aircraft a ON f.aircraft_key = a.aircraft_key
        JOIN dim_delay_cause c ON f.delay_cause_key = c.delay_cause_key""")
    # «зручні» місячні підсумки в тій самій таблиці
    con.execute("""
        INSERT INTO v0_fact_flight
        SELECT 'airline_month', DATE_TRUNC('month', flight_date)::DATE, NULL, NULL, NULL, airline_code, NULL,
               NULL, NULL, SUM(seats), SUM(passengers), SUM(delay_minutes), SUM(revenue_usd),
               SUM(cancelled), NULL,
               SUM(passengers) * 1.0 / SUM(seats), AVG(on_time_pct), AVG(delay_minutes)
        FROM v0_fact_flight WHERE row_kind = 'flight'
        GROUP BY airline_code, DATE_TRUNC('month', flight_date)""")
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("v0_dim_airline", "v0_dim_aircraft", "v0_fact_flight")}


def build(path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = duckdb.connect(str(path))
    build_v1(con)
    build_v0(con)
    return con


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()
    con = build(Path(args.db))
    for t in LOAD_ORDER + ["v0_fact_flight"]:
        print(f"{t:18s} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>6d} рядків")
    con.close()


if __name__ == "__main__":
    main()
