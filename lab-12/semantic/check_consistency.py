"""Перевірка узгодженості: те саме питання трьома шляхами дає однаковий результат.
  (1) SQL, згенерований семантичним шаром; (2) вручну написаний OLAP-запит; (3) pandas з Parquet.
Запуск: python semantic/check_consistency.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import metric_sql  # noqa: E402

D = ROOT / "data"
OLAP = ROOT / "sql" / "olap"
TOL = 0.051  # допуск на різне округлення (ROUND у SQL проти pandas)


def _con():
    return duckdb.connect(str(D / "hub.duckdb"), read_only=True)


def _close(a: pd.Series, b: pd.Series, tol: float = TOL) -> bool:
    a, b = a.sort_index().astype(float), b.sort_index().astype(float)
    return list(a.index) == list(b.index) and bool(np.all(np.abs(a.values - b.values) <= tol))


def check_q1_on_time_by_type() -> bool:
    """flights_count, on_time_rate, avg_delay_min за типом авіакомпанії."""
    con = _con()
    sem = con.execute(metric_sql(["flights_count", "on_time_rate", "avg_delay_min"], group_by=["airline_type"])).df().set_index("airline_type")
    hand = con.execute((OLAP / "01_rollup.sql").read_text()).df()
    hand = hand[(hand["airline"] == "(усі)") & (hand["airline_type"] != "(усі типи)")].set_index("airline_type")
    m = pd.read_parquet(D / "fact_flight.parquet").merge(pd.read_parquet(D / "dim_airline.parquet"), on="airline_key")
    m["on_time"] = (m["cancelled"] == 0) & (m["delay_minutes"] <= 14)
    pdf = m.groupby("airline_type").agg(flights=("flight_id", "count"), ot=("on_time", "mean"), dl=("delay_minutes", "mean"))
    pdf["ot"] *= 100
    return all([
        _close(sem["flights_count"], hand["flights"], 0), _close(sem["flights_count"], pdf["flights"], 0),
        _close(sem["on_time_rate"], hand["on_time_pct"]), _close(sem["on_time_rate"], pdf["ot"], 1e-6),
        _close(sem["avg_delay_min"], hand["avg_delay_min"]), _close(sem["avg_delay_min"], pdf["dl"], 1e-6),
    ])


def check_q2_delay_by_class() -> bool:
    """total_delay_min за класом причини (лише затримані, нескасовані) — таксономія."""
    con = _con()
    sem = con.execute(metric_sql("total_delay_min", group_by=["cause_class"],
                                 filters=[("cancelled", "=", 0), ("cause_class", "<>", "No delay")])).df().set_index("cause_class")["total_delay_min"]
    hand = con.execute((OLAP / "09_drilldown_taxonomy.sql").read_text()).df()
    hand = hand[(hand["cause_subclass"] == "(весь клас)") & (hand["cause_class"] != "(усі класи)")].set_index("cause_class")["total_delay_min"]
    m = pd.read_parquet(D / "fact_flight.parquet").merge(pd.read_parquet(D / "dim_delay_cause.parquet"), on="delay_cause_key")
    m = m[(m["cancelled"] == 0) & (m["class_label"] != "No delay")]
    pdf = m.groupby("class_label")["delay_minutes"].sum()
    return _close(sem, hand, 0) and _close(sem, pdf, 0)


def check_q3_passengers_by_month() -> bool:
    """passengers за місяцем: семантика vs 06_window_cumulative vs pandas."""
    con = _con()
    sem = con.execute(metric_sql("passengers", group_by=["month"])).df().set_index("month")["passengers"]
    hand = con.execute((OLAP / "06_window_cumulative.sql").read_text()).df().set_index("month")["passengers"]
    m = pd.read_parquet(D / "fact_flight.parquet").merge(pd.read_parquet(D / "dim_date.parquet"), on="date_key")
    pdf = m.groupby("month")["passengers"].sum()
    return _close(sem, hand, 0) and _close(sem, pdf, 0)


def check_q4_ratios_vs_pandas() -> bool:
    """load_factor і revenue_per_pax за типом літака: семантика vs pandas (відношення сум)."""
    con = _con()
    sem = con.execute(metric_sql(["load_factor", "revenue_per_pax"], group_by=["aircraft_type"])).df().set_index("aircraft_type")
    m = pd.read_parquet(D / "fact_flight.parquet").merge(pd.read_parquet(D / "dim_aircraft.parquet"), on="aircraft_key", suffixes=("", "_ac"))
    ok = m[m["cancelled"] == 0].groupby("aircraft_type").agg(p=("passengers", "sum"), s=("seats", "sum"))
    lf = 100 * ok["p"] / ok["s"]
    g = m.groupby("aircraft_type").agg(r=("revenue_usd", "sum"), p=("passengers", "sum"))
    return _close(sem["load_factor"], lf, 1e-6) and _close(sem["revenue_per_pax"], g["r"] / g["p"], 1e-6)


CHECKS = [
    ("Q1 on_time_rate/avg_delay_min/flights_count за airline_type: семантика = 01_rollup = pandas", check_q1_on_time_by_type),
    ("Q2 total_delay_min за cause_class: семантика = 09_drilldown = pandas", check_q2_delay_by_class),
    ("Q3 passengers за month: семантика = 06_window_cumulative = pandas", check_q3_passengers_by_month),
    ("Q4 load_factor/revenue_per_pax за aircraft_type: семантика = pandas", check_q4_ratios_vs_pandas),
]

if __name__ == "__main__":
    failed = 0
    for name, fn in CHECKS:
        ok = fn()
        failed += not ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    sys.exit(1 if failed else 0)
