"""Виконує всі sql/olap/*.sql, друкує результати й зберігає CSV у data/olap_out/."""
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "olap_out"
OUT.mkdir(parents=True, exist_ok=True)
pd.set_option("display.width", 200, "display.max_columns", 30, "display.max_rows", 40)

con = duckdb.connect(str(ROOT / "data" / "hub.duckdb"), read_only=True)
for f in sorted((ROOT / "sql" / "olap").glob("*.sql")):
    df = con.execute(f.read_text()).df()
    df.to_csv(OUT / f"{f.stem}.csv", index=False)
    print(f"\n=== {f.name} ({len(df)} рядків) ===")
    print(df.head(40).to_string(index=False))
