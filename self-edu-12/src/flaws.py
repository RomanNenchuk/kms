"""Три недоліки чернетки v0 (зерно, ключі, адитивність): числа на тих самих даних, що й для v1."""
from __future__ import annotations

import json

import duckdb

from build_db import DB_PATH, ROOT

RESULTS = ROOT / "results"


def measure(con: duckdb.DuckDBPyConnection) -> dict:
    q1 = lambda sql: con.execute(sql).fetchone()
    res: dict = {}

    # 1. ЗЕРНО: у факті змішано рядки рейсів і місячні підсумки -> SUM() рахує все двічі
    true_pax = q1("SELECT SUM(passengers) FROM fact_flight")[0]
    v0_pax_all = q1("SELECT SUM(passengers) FROM v0_fact_flight")[0]
    res["grain"] = {
        "flight_rows": q1("SELECT COUNT(*) FROM v0_fact_flight WHERE row_kind='flight'")[0],
        "summary_rows": q1("SELECT COUNT(*) FROM v0_fact_flight WHERE row_kind<>'flight'")[0],
        "true_passengers": int(true_pax),
        "v0_sum_passengers": int(v0_pax_all),
        "inflation_x": round(v0_pax_all / true_pax, 3),
    }

    # 2. КЛЮЧІ: зв'язок з бортом за бізнес-ключем registration, а версій у виміру декілька
    joined_rows, joined_pax = q1("""
        SELECT COUNT(*), SUM(f.passengers) FROM v0_fact_flight f
        JOIN v0_dim_aircraft a ON a.registration = f.registration WHERE f.row_kind='flight'""")
    res["keys"] = {
        "fact_rows": res["grain"]["flight_rows"],
        "rows_after_join": int(joined_rows),
        "extra_rows": int(joined_rows) - res["grain"]["flight_rows"],
        "true_passengers": int(true_pax),
        "joined_sum_passengers": int(joined_pax),
        "inflation_pct": round(100.0 * (joined_pax / true_pax - 1), 2),
        "aircraft_with_2_versions": q1("SELECT COUNT(*) FROM (SELECT registration FROM v0_dim_aircraft GROUP BY 1 HAVING COUNT(*)>1)")[0],
    }

    # 3. АДИТИВНІСТЬ: усереднення збережених відсотків по місячних підсумках (середнє середніх)
    rows = con.execute("""
        WITH bad AS (
            SELECT al.airline_type, ROUND(AVG(f.on_time_pct), 2) AS avg_of_ratios
            FROM v0_fact_flight f JOIN v0_dim_airline al USING (airline_code)
            WHERE f.row_kind = 'airline_month' GROUP BY 1),
        good AS (
            SELECT al.airline_type,
                   ROUND(100.0 * SUM(CASE WHEN f.cancelled = 0 AND f.delay_minutes <= 14 THEN 1 ELSE 0 END) / COUNT(*), 2) AS ratio_of_sums
            FROM v0_fact_flight f JOIN v0_dim_airline al USING (airline_code)
            WHERE f.row_kind = 'flight' GROUP BY 1)
        SELECT bad.airline_type, avg_of_ratios, ratio_of_sums, ROUND(avg_of_ratios - ratio_of_sums, 2) AS diff_pp
        FROM bad JOIN good USING (airline_type) ORDER BY 1""").fetchall()
    sum_hours = q1("SELECT SUM(airframe_hours) FROM fact_flight")[0]
    fleet_hours = q1("""SELECT SUM(m) FROM (SELECT MAX(f.airframe_hours) AS m FROM fact_flight f
                        JOIN dim_aircraft a USING (aircraft_key) GROUP BY a.registration)""")[0]
    res["additivity"] = {
        "on_time_by_type": [{"airline_type": r[0], "avg_of_ratios_pct": r[1],
                                 "ratio_of_sums_pct": r[2], "diff_pp": r[3]} for r in rows],
        "airframe_sum_over_flights": round(sum_hours, 1),
        "airframe_fleet_total_max": round(fleet_hours, 1),
        "airframe_overcount_x": round(sum_hours / fleet_hours, 1),
    }
    return res


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    res = measure(con)
    (RESULTS / "flaws.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    g, k, a = res["grain"], res["keys"], res["additivity"]
    print(f"[зерно]       SUM(passengers): v0 = {g['v0_sum_passengers']}, правильно = {g['true_passengers']} (×{g['inflation_x']})")
    print(f"[ключі]       після JOIN за registration: {k['rows_after_join']} рядків замість {k['fact_rows']} (+{k['inflation_pct']} % пасажирів)")
    for r in a["on_time_by_type"]:
        print(f"[адитивність] {r['airline_type']:12s} AVG(on_time_pct) = {r['avg_of_ratios_pct']} %, SUM/SUM = {r['ratio_of_sums_pct']} % (різниця {r['diff_pp']} п.п.)")
    print(f"[адитивність] SUM(airframe_hours) = {a['airframe_sum_over_flights']}, сума по бортах MAX = {a['airframe_fleet_total_max']} (×{a['airframe_overcount_x']})")


if __name__ == "__main__":
    main()
