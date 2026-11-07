"""ELT: DDL -> завантаження Parquet -> перевірки якості -> data/quality_report.json.
Запуск: python etl/load.py   (код виходу 1, якщо є порушення)
"""
import json
import sys
from pathlib import Path

import duckdb

from quality import CHECKS

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "hub.duckdb"
TABLES = ["dim_date", "dim_airport", "dim_airline", "dim_aircraft", "dim_delay_cause", "fact_flight"]


def main() -> int:
    if DB.exists():
        DB.unlink()  # завжди будуємо з нуля
    con = duckdb.connect(str(DB))
    con.execute((ROOT / "sql" / "ddl.sql").read_text())

    for t in TABLES:  # виміри перед фактом
        con.execute(f"INSERT INTO {t} BY NAME SELECT * FROM read_parquet('{DATA / (t + '.parquet')}')")
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
    print("Рядків:", counts)

    version = (DATA / "VERSION").read_text().strip().replace("\n", "; ")
    report = {"dataset": version, "row_counts": counts, "checks": []}
    for name, desc, sql in CHECKS:
        bad = con.execute(sql).fetchone()[0]
        report["checks"].append({"check": name, "description": desc, "violations": bad, "ok": bad == 0})
        print(f"[{'OK ' if bad == 0 else 'FAIL'}] {name}: {bad}")

    (DATA / "quality_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    failed = [c for c in report["checks"] if not c["ok"]]
    print(f"\nПеревірок: {len(CHECKS)}, провалено: {len(failed)}")
    con.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
