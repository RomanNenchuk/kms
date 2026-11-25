"""Діаграма зірки з каталогу БД (щоб збігалася з DDL): results/star_diagram.dot (+ .png, якщо є graphviz)."""
from __future__ import annotations

import html
import shutil
import subprocess
import sys

import duckdb

from build_db import DB_PATH, ROOT

TABLES = ["fact_flight", "dim_date", "dim_airport", "dim_airline", "dim_aircraft", "dim_delay_cause"]
NOTE = {  # підпис SCD / ієрархії під назвою таблиці
    "fact_flight": "ФАКТ · зерно: один виліт",
    "dim_date": "рік › квартал › місяць › день",
    "dim_airport": "SCD 1 · країна › місто › аеропорт",
    "dim_airline": "SCD 1 · тип › авіакомпанія",
    "dim_aircraft": "SCD 2 · виробник › тип › борт",
    "dim_delay_cause": "SCD 1 · клас › підклас (IRI)",
}
MEASURE_KIND = {"airframe_hours": "напівадитивна", "cancelled": "адитивна (0/1)"}
ADDITIVE = {"distance_km", "seats", "passengers", "delay_minutes", "fuel_kg", "revenue_usd"}


def catalog(con):
    cols = {t: con.execute(f"SELECT column_name, data_type FROM information_schema.columns "
                           f"WHERE table_name='{t}' ORDER BY ordinal_position").fetchall() for t in TABLES}
    pk = {t: set() for t in TABLES}
    fks = []
    for t, ctype, ccols, ref, refcols in con.execute("""
            SELECT table_name, constraint_type, constraint_column_names, referenced_table, referenced_column_names
            FROM duckdb_constraints() WHERE schema_name='main'""").fetchall():
        if t not in TABLES:
            continue
        if ctype == "PRIMARY KEY":
            pk[t].update(ccols)
        elif ctype == "FOREIGN KEY":
            fks.append((t, ccols[0], ref))
    return cols, pk, fks


def make_dot(con) -> str:
    cols, pk, fks = catalog(con)
    fk_cols = {(t, c) for t, c, _ in fks}
    out = ['digraph star {', '  layout=twopi; root="fact_flight"; ranksep=3.0; overlap=false; splines=true;',
           '  node [shape=plain, fontname="DejaVu Sans"]; edge [color="#555555", arrowsize=0.8, fontname="DejaVu Sans", fontsize=10];']
    for t in TABLES:
        head = "#F3C58E" if t == "fact_flight" else "#BFD7EA"
        rows = [f'<TR><TD BGCOLOR="{head}" ALIGN="CENTER"><B>{t}</B></TD></TR>',
                f'<TR><TD ALIGN="CENTER"><I>{html.escape(NOTE[t])}</I></TD></TR>']
        for c, ty in cols[t]:
            tag = "PK" if c in pk[t] else ("FK" if (t, c) in fk_cols else "")
            extra = ""
            if t == "fact_flight" and c in ADDITIVE:
                extra = " · адит."
            elif t == "fact_flight" and c in MEASURE_KIND:
                extra = " · " + MEASURE_KIND[c]
            if t == "fact_flight" and c == "origin_airport_key":
                extra = " · роль: вильот"
            elif t == "fact_flight" and c == "dest_airport_key":
                extra = " · роль: призначення"
            label = f"{tag + '  ' if tag else '      '}{c} : {ty.lower()}{extra}"
            rows.append(f'<TR><TD ALIGN="LEFT" PORT="{c}">{html.escape(label)}</TD></TR>')
        out.append(f'  {t} [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3">' + "".join(rows) + "</TABLE>>];")
    for t, c, ref in fks:
        role = {"origin_airport_key": "origin", "dest_airport_key": "destination"}.get(c, "")
        if role:
            col = "#C0392B" if role == "origin" else "#1F618D"
            out.append(f'  {t}:{c} -> {ref} [color="{col}", penwidth=1.6];')
        else:
            out.append(f"  {t}:{c} -> {ref};")
    out.append("}")
    return "\n".join(out)


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    dot = make_dot(con)
    res = ROOT / "results"
    res.mkdir(exist_ok=True)
    (res / "star_diagram.dot").write_text(dot, encoding="utf-8")
    print("results/star_diagram.dot")
    if shutil.which("twopi"):
        subprocess.run(["twopi", "-Tpng", "-Gdpi=130", str(res / "star_diagram.dot"), "-o", str(res / "star_diagram.png")], check=True)
        print("results/star_diagram.png")
    else:
        print("graphviz не знайдено: sudo apt install graphviz, потім повторіть (.dot уже створено)", file=sys.stderr)


if __name__ == "__main__":
    main()
