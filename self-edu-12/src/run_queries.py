"""Виконує 5 запитів до зірки v1 і зберігає результати: results/q*.csv та results/queries.json."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from build_db import DB_PATH, ROOT

QUERIES = ROOT / "sql" / "queries"
RESULTS = ROOT / "results"

TITLES = {
    "q1_load_factor": "BQ1. Коефіцієнт завантаження за типом авіакомпанії та кварталом",
    "q2_delay_causes": "BQ2. Хвилини затримки за класом і підкласом причин (таксономія)",
    "q3_top_routes": "BQ3. Топ-10 маршрутів за доходом",
    "q4_on_time_hub": "BQ4. Частка вчасних рейсів по місяцях: хаб / не-хаб",
    "q5_seats_scd2": "BQ5. Запропоновані місця за виробником і типом ПС (SCD2)",
}


def run_all(con: duckdb.DuckDBPyConnection):
    out = {}
    for f in sorted(QUERIES.glob("q*.sql")):
        df = con.execute(f.read_text(encoding="utf-8")).df()
        out[f.stem] = df
    return out


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    summary = {}
    for name, df in run_all(con).items():
        df.to_csv(RESULTS / f"{name}.csv", index=False)
        summary[name] = {"title": TITLES[name], "rows": len(df), "columns": list(df.columns),
                         "data": json.loads(df.to_json(orient="records"))}
        print(f"{name}: {len(df)} рядків -> results/{name}.csv")
    (RESULTS / "queries.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
