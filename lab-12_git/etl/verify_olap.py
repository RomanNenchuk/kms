"""Незалежна перевірка 2 результатів OLAP: pandas (лише з Parquet) vs DuckDB (sql/olap/*.sql).
Запуск: python etl/verify_olap.py
"""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
con = duckdb.connect(str(D / "hub.duckdb"), read_only=True)
fact = pd.read_parquet(D / "fact_flight.parquet")
airline = pd.read_parquet(D / "dim_airline.parquet")
cause = pd.read_parquet(D / "dim_delay_cause.parquet")


def check(name: str, ok: bool) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise SystemExit(1)


# --- Перевірка 1: 01_rollup (частка вчасних і середня затримка за типом авіакомпанії та загалом)
sql = con.execute((ROOT / "sql/olap/01_rollup.sql").read_text()).df()
sql = sql[sql["airline"] == "(усі)"].set_index("airline_type")

m = fact.merge(airline, on="airline_key")
m["on_time"] = (m["cancelled"] == 0) & (m["delay_minutes"] <= 14)
pdf = m.groupby("airline_type").agg(flights=("flight_id", "count"), on_time_pct=("on_time", "mean"),
                                    avg_delay=("delay_minutes", "mean"))
pdf["on_time_pct"] *= 100
pdf.loc["(усі типи)"] = [len(m), m["on_time"].mean() * 100, m["delay_minutes"].mean()]

ok = all(
    sql.loc[t, "flights"] == pdf.loc[t, "flights"]
    and abs(sql.loc[t, "on_time_pct"] - pdf.loc[t, "on_time_pct"]) <= 0.051
    and abs(sql.loc[t, "avg_delay_min"] - pdf.loc[t, "avg_delay"]) <= 0.051
    for t in pdf.index
)
print(pdf.round(1).to_string())
check("Q1 ROLLUP: on_time_pct / avg_delay збігаються з pandas", ok)

# --- Перевірка 2: 09_drilldown_taxonomy (сума хвилин затримки за підкласами та класами)
sql = con.execute((ROOT / "sql/olap/09_drilldown_taxonomy.sql").read_text()).df()
leaf = sql[(sql["cause_subclass"] != "(весь клас)")].set_index(["cause_class", "cause_subclass"])["total_delay_min"]
cls = sql[(sql["cause_subclass"] == "(весь клас)") & (sql["cause_class"] != "(усі класи)")].set_index("cause_class")["total_delay_min"]

m = fact[fact["cancelled"] == 0].merge(cause, on="delay_cause_key")
m = m[m["class_label"] != "No delay"]
p_leaf = m.groupby(["class_label", "subclass_label"])["delay_minutes"].sum()
p_cls = m.groupby("class_label")["delay_minutes"].sum()
p_total = int(m["delay_minutes"].sum())
sql_total = int(sql[sql["cause_class"] == "(усі класи)"]["total_delay_min"].iloc[0])

ok = (np.array_equal(leaf.sort_index().values, p_leaf.sort_index().values)
      and np.array_equal(cls.sort_index().values, p_cls.sort_index().values)
      and sql_total == p_total)
print(p_cls.sort_values(ascending=False).to_string(), f"\nвсього: {p_total}")
check("Q9 drill-down: суми за підкласами, класами та загалом збігаються з pandas", ok)
