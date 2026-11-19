#!/usr/bin/env python3
"""Офлайн-перевірка SPARQL-запитів без GraphDB: rdflib + data/avia.ttl проти data/oracle.json.

Потрібен rdflib (pip install rdflib). Корисно, щоб відловити помилки в запитах до запуску Docker.
"""
import json
from pathlib import Path

from rdflib import Graph, Literal

import queries as Q

DATA = Path(__file__).resolve().parent.parent / "data"


def main():
    g = Graph()
    g.parse(DATA / "avia.ttl", format="turtle")
    oracle = json.loads((DATA / "oracle.json").read_text(encoding="utf-8"))
    ok = True
    for q in Q.QUERIES:
        rows = [[v.toPython() if isinstance(v, Literal) else str(v) for v in row] for row in g.query(q["sparql"])]
        same = rows == oracle[q["id"]]
        ok &= same
        print(f"{q['id']}: {'OK' if same else 'MISMATCH'} ({len(rows)} рядків)")
        if not same:
            print("  rdflib:", rows[:5])
            print("  oracle:", oracle[q["id"]][:5])
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
