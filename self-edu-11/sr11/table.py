"""Таблиця класифікації results/classification.csv: авто-вердикт + колонки для людини (human_*).

Повторний `classify` оновлює auto_* і НЕ стирає human_*. Підсумкове значення: human, якщо заповнено, інакше auto.
"""
import csv
from . import config as C
from .classify import evaluate
from .queries import load_queries
from .runner import load_run

COLS = ["id", "category", "subtype", "lang", "question", "expected", "abstained", "answer", "sources_docs", "doc_recall",
        "evidence_recall", "faithfulness", "auto_verdict", "auto_cause", "auto_detail", "needs_manual",
        "human_verdict", "human_cause", "human_note"]


def _fmt(x):
    return "" if x is None else (f"{x:.2f}" if isinstance(x, float) else x)


def build(queries=None, results=None):
    queries = queries or load_queries()
    results = results if results is not None else load_run()
    rows = []
    for q in queries:
        r = results.get(q["id"])
        if not r:
            continue
        ev = evaluate(q, r)
        m = ev["metrics"]
        rows.append({"id": q["id"], "category": q["category"], "subtype": q["subtype"], "lang": q["lang"], "question": q["question"],
                     "expected": q["expected"], "abstained": r["abstained"], "answer": r["answer"].replace("\n", " "),
                     "sources_docs": ";".join(m["retrieved_docs"]), "doc_recall": _fmt(m["doc_recall"]),
                     "evidence_recall": _fmt(m["evidence_recall"]), "faithfulness": _fmt(m["faithfulness"]),
                     "auto_verdict": ev["verdict"], "auto_cause": ev["cause"], "auto_detail": ev["detail"],
                     "needs_manual": "так" if ev["needs_manual"] else "",
                     "human_verdict": "", "human_cause": "", "human_note": ""})
    return rows


def load():
    f = C.p("classification.csv")
    if not f.exists():
        return []
    with open(f, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def save(rows):
    old = {r["id"]: r for r in load()}
    for r in rows:                                   # зберігаємо ручні правки
        o = old.get(r["id"])
        if o:
            for k in ("human_verdict", "human_cause", "human_note"):
                r[k] = o.get(k, "")
    with open(C.p("classification.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    return rows


def final(row):
    """(вердикт, причина) з урахуванням ручних правок."""
    v = row.get("human_verdict") or row["auto_verdict"]
    c = row.get("human_cause") or row["auto_cause"]
    if v == "правильно":
        c = "—"
    return v, c
