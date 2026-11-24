"""Завантаження й перевірка набору запитів (критерій C1)."""
import json
import re
from . import config as C


def load_queries(path=None):
    path = path or C.QUERIES
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def validate(queries, corpus_path=None):
    """Повертає (problems, summary). problems порожній -> набір відповідає C1 і докази є в корпусі."""
    problems = []
    ids = [q["id"] for q in queries]
    if len(queries) != 20:
        problems.append(f"має бути 20 запитів, є {len(queries)}")
    if len(set(ids)) != len(ids):
        problems.append("id не унікальні")
    cats = {}
    for q in queries:
        if q["category"] not in C.CATEGORIES:
            problems.append(f"{q['id']}: невідома категорія {q['category']}")
        cats[q["category"]] = cats.get(q["category"], 0) + 1
    if len(cats) < 4:
        problems.append(f"категорій {len(cats)}, треба ≥ 4")
    n_hard = cats.get("unanswerable", 0) + cats.get("harmful", 0)
    if n_hard < 4:
        problems.append(f"без відповіді + шкідливих {n_hard}, треба ≥ 4")

    corpus_path = corpus_path or C.CORPUS
    if corpus_path and corpus_path.exists():
        by_doc = {}
        for line in open(corpus_path, encoding="utf-8"):
            r = json.loads(line)
            by_doc.setdefault(r["doc_id"], []).append(norm(r["text"]))
        for q in queries:
            for d in q["gold_doc_ids"]:
                if d not in by_doc:
                    problems.append(f"{q['id']}: gold-документ {d} відсутній у корпусі")
            for e in q["evidence"]:
                pool = " ".join(t for d in q["gold_doc_ids"] for t in by_doc.get(d, []))
                if norm(e) not in pool:
                    problems.append(f"{q['id']}: evidence не знайдено дослівно в gold-документах: {e[:60]}…")
            fx_ids = [f["id"] for f in q["fixtures"]]
            if len(set(fx_ids)) != len(fx_ids):
                problems.append(f"{q['id']}: дублікати id фікстур")
    else:
        problems.append(f"корпус не знайдено ({corpus_path}) — докази не перевірено")
    summary = {"n": len(queries), "categories": cats, "unanswerable_or_harmful": n_hard,
               "uk_queries": sum(q["lang"] == "uk" for q in queries),
               "synthetic_fixtures": sum(bool(q["fixtures"]) for q in queries)}
    return problems, summary
