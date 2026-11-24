"""Ручна перевірка faithfulness: аркуш для людини і узгодженість «суддя vs людина» (вимога: ≥ 5 оцінок вручну)."""
import csv
import json
import random
import sys
from . import config as C
from .queries import load_queries
from .runner import load_run

MIN_N = 5
HUMAN_COL = "human_faithful (1 = усі твердження підтверджені джерелами, 0 = ні)"


def make_sheet(n=8):
    tests = {q["id"]: q for q in load_queries()}
    results = load_run()
    pool = {}
    for rid, r in results.items():
        j = r.get("judge")
        if not r["abstained"] and j and j.get("faithfulness") is not None:
            pool.setdefault(tests[rid]["category"], []).append(rid)
    total = sum(len(v) for v in pool.values())
    if total < MIN_N:
        sys.exit(f"Для ручної перевірки є лише {total} оцінених відповідей (треба ≥ {MIN_N}). Спочатку `run` і `judge`.")
    rnd = random.Random(C.SEED)
    for v in pool.values():
        v.sort()
        rnd.shuffle(v)
    pick, cats = [], [c for c in C.CATEGORIES if c in pool]
    while len(pick) < min(n, total):                       # по черзі з кожної категорії
        for c in cats:
            if pool[c] and len(pick) < n:
                pick.append(pool[c].pop())
    with open(C.p("human_sheet.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "question", "answer", "cited_sources", HUMAN_COL, "human_note"])
        for rid in sorted(pick):
            r = results[rid]
            cited = r["citations"]["cited"] or list(r["contexts"])[:3]
            srcs = "\n\n".join(f"[{i}] {r['contexts'][i]}" for i in cited if i in r["contexts"])
            w.writerow([rid, tests[rid]["category"], tests[rid]["question"], r["answer"], srcs, "", ""])
    print(f"Аркуш: {C.p('human_sheet.csv')} ({len(pick)} рядків). Заповни колонку human_faithful (0/1), НЕ дивлячись на оцінки судді, потім `kappa`.")
    return pick


def cohen_kappa(h, j):
    n = len(h)
    a = sum(x == y for x, y in zip(h, j)) / n
    pe = sum((h.count(v) / n) * (j.count(v) / n) for v in (0, 1))
    return a, (None if pe == 1 else (a - pe) / (1 - pe))


def compute_kappa():
    results = load_run()
    h, j, ids = [], [], []
    with open(C.p("human_sheet.csv"), encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            col = next((k for k in row if k and k.startswith("human_faithful")), None)
            v = (row.get(col) or "").strip() if col else ""
            jf = results.get(row["id"], {}).get("judge", {}).get("faithfulness")
            if v in ("0", "1") and jf is not None:
                h.append(int(v))
                j.append(int(jf == 1.0))
                ids.append(row["id"])
    if len(h) < MIN_N:
        sys.exit(f"Заповнено лише {len(h)} оцінок; методичка вимагає ≥ {MIN_N}.")
    a, k = cohen_kappa(h, j)
    conf = {"human1_judge1": sum(x == y == 1 for x, y in zip(h, j)), "human0_judge0": sum(x == y == 0 for x, y in zip(h, j)),
            "human1_judge0": sum(x == 1 and y == 0 for x, y in zip(h, j)), "human0_judge1": sum(x == 0 and y == 1 for x, y in zip(h, j))}
    out = {"n": len(h), "agreement": a, "kappa": k, "confusion": conf, "ids": ids}
    C.p("kappa.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ks = "н/д (вироджений розподіл)" if k is None else f"{k:.2f}"
    print(f"n={len(h)} згода={a:.0%} κ={ks} {conf}")
    return out
