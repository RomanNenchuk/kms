#!/usr/bin/env python3
"""Завантажує датасет у Neo4j, Memgraph і GraphDB та зберігає час завантаження в results/load.json."""
import json

import dbs

RESULTS = dbs.ROOT / "results"


def main(backends=None):
    RESULTS.mkdir(exist_ok=True)
    out = {}
    for b in backends or dbs.all_backends():
        print(f"[{b.name}] чекаю на готовність…")
        b.wait_ready()
        print(f"[{b.name}] версія: {b.version()}; завантажую…")
        secs = b.load()
        counts = b.counts()
        out[b.name] = {"version": b.version(), "load_seconds": round(secs, 3), **counts}
        print(f"[{b.name}] готово за {secs:.2f}с: {counts}")
        b.close()
    (RESULTS / "load.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
