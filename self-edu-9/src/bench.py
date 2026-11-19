#!/usr/bin/env python3
"""Запускає Q1–Q5 у кожному сховищі: перевірка результату проти еталона + заміри часу.

Методика: на кожен запит WARMUP прогрівальних запусків (не рахуються), далі RUNS замірів.
Час — клієнтський (wall-clock від відправлення запиту до повного отримання всіх рядків),
тобто включає мережу loopback і серіалізацію. Це чесно для «зручного» порівняння, але не є
серверним профілем виконання.

Результати: results/results.json та results/report_tables.md (готові таблиці для звіту).
"""
import argparse
import json
import math
import statistics
import subprocess
import time

import dbs
import queries as Q

RESULTS = dbs.ROOT / "results"
CONTAINERS = {"Neo4j": "sr9-neo4j", "Memgraph": "sr9-memgraph", "GraphDB": "sr9-graphdb"}


def p95(xs):
    xs = sorted(xs)
    return xs[max(0, math.ceil(0.95 * len(xs)) - 1)]


def docker_memory():
    """Best-effort: використання пам'яті контейнерами (docker stats)."""
    try:
        out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.MemUsage}}"],
                             capture_output=True, text=True, timeout=60, check=True).stdout
    except Exception:
        return {}
    mem = {}
    for line in out.splitlines():
        name, _, usage = line.partition("|")
        for db, cname in CONTAINERS.items():
            if name == cname:
                mem[db] = usage.split("/")[0].strip()
    return mem


def bench_backend(b, oracle, runs, warmup):
    res = {"version": b.version(), "queries": {}}
    for q in Q.QUERIES:
        qid = q["id"]
        rows = b.run(q)  # перший запуск: і перевірка коректності, і частина прогріву
        for _ in range(warmup):
            b.run(q)
        times = []
        for _ in range(runs):
            t0 = time.perf_counter()
            b.run(q)
            times.append((time.perf_counter() - t0) * 1000)
        res["queries"][qid] = {
            "correct": rows == oracle[qid],
            "rows": len(rows),
            "median_ms": round(statistics.median(times), 2),
            "p95_ms": round(p95(times), 2),
            "min_ms": round(min(times), 2),
            "sample": rows[:3],
            "diff": None if rows == oracle[qid] else {"got": rows[:5], "expected": oracle[qid][:5]},
        }
        r = res["queries"][qid]
        print(f"  {qid}: {'✓' if r['correct'] else '✗ РОЗБІЖНІСТЬ'}  median {r['median_ms']} мс  p95 {r['p95_ms']} мс")
    return res


def render(results, load, mem, runs, warmup):
    names = list(results)
    L = []
    L.append(f"_Заміри: {runs} запусків на запит після {warmup} прогрівальних; клієнтський wall-clock, мс._\n")
    L.append("### Версії та завантаження\n")
    L.append("| Сховище | Версія | Завантаження, с | Обсяг | Пам'ять контейнера |")
    L.append("|---|---|---|---|---|")
    for n in names:
        ld = load.get(n, {})
        size = ", ".join(f"{k}: {v}" for k, v in ld.items() if k in ("nodes", "edges", "triples")) or "—"
        L.append(f"| {n} | {results[n]['version']} | {ld.get('load_seconds', '—')} | {size} | {mem.get(n, '—')} |")
    L.append("\n### Час виконання, median / p95 (мс)\n")
    L.append("| Запит | " + " | ".join(names) + " | Рядків |")
    L.append("|---|" + "---|" * (len(names) + 1))
    for q in Q.QUERIES:
        cells = []
        for n in names:
            r = results[n]["queries"][q["id"]]
            cells.append(f"{r['median_ms']} / {r['p95_ms']}")
        rows = results[names[0]]["queries"][q["id"]]["rows"]
        L.append(f"| {q['id']} — {q['title']} | " + " | ".join(cells) + f" | {rows} |")
    L.append("\n### Збіг результатів з еталоном (Python-оракул)\n")
    L.append("| Запит | " + " | ".join(names) + " |")
    L.append("|---|" + "---|" * len(names))
    for q in Q.QUERIES:
        L.append(f"| {q['id']} | " + " | ".join("✓" if results[n]["queries"][q["id"]]["correct"] else "✗" for n in names) + " |")
    bad = [(n, qid) for n in names for qid, r in results[n]["queries"].items() if not r["correct"]]
    if bad:
        L.append("\n**Розбіжності (потрібно пояснити у звіті):**")
        for n, qid in bad:
            d = results[n]["queries"][qid]["diff"]
            L.append(f"- {n} {qid}: отримано {d['got']} …, очікувалось {d['expected']} …")
    return "\n".join(L) + "\n"


def main(backends=None, runs=20, warmup=3):
    RESULTS.mkdir(exist_ok=True)
    oracle = json.loads((dbs.DATA / "oracle.json").read_text(encoding="utf-8"))
    load_path = RESULTS / "load.json"
    load = json.loads(load_path.read_text(encoding="utf-8")) if load_path.exists() else {}
    results = {}
    for b in backends or dbs.all_backends():
        print(f"[{b.name}]")
        b.wait_ready()
        results[b.name] = bench_backend(b, oracle, runs, warmup)
        b.close()
    mem = docker_memory()
    (RESULTS / "results.json").write_text(
        json.dumps({"runs": runs, "warmup": warmup, "results": results, "load": load, "memory": mem},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    md = render(results, load, mem, runs, warmup)
    (RESULTS / "report_tables.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print("Збережено: results/results.json, results/report_tables.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--warmup", type=int, default=3)
    a = ap.parse_args()
    main(runs=a.runs, warmup=a.warmup)
