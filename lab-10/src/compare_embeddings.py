"""Результат 3, крок 3: якість і затримка двох моделей на 20 запитах, EN та UK.
Запуск: python -m src.compare_embeddings
Вхід: eval/queries_20.jsonl, (опційно) eval/queries_20_uk.jsonl зі status=verified
Вихід: docs/embeddings_cmp.md, eval/embeddings_results.json
"""
import json, time, re
import numpy as np
from .config import ROOT, EMB_MODELS
from .chunking import load_docs
from .index import VectorIndex

K = 5
norm = lambda s: re.sub(r"\s+", "", s).lower()

def read(p): return [json.loads(l) for l in open(ROOT / p, encoding="utf-8")]

en = [q for q in read("eval/queries_20.jsonl") if q.get("status") == "verified"]
langs = {"en": {q["id"]: q["question"] for q in en}}
uk_path = ROOT / "eval" / "queries_20_uk.jsonl"
if uk_path.exists():
    langs["uk"] = {r["id"]: r["question_uk"] for r in read("eval/queries_20_uk.jsonl") if r.get("status") == "verified"}
evidence = {q["id"]: q["evidence"] for q in en}
print("Мови запитів:", {l: len(v) for l, v in langs.items()})

docs = load_docs()
results, per_query, build = {}, {}, {}
for key in EMB_MODELS:
    vi = VectorIndex(key)
    build[key] = vi.build(docs)
    vi.embed_query("warm up"); vi.search("warm up", k=K)           # прогрів, щоб перший виклик не псував час
    for lang, qs in langs.items():
        ranks, rr, t_emb, t_srch = [], [], [], []
        for qid, text in qs.items():
            t0 = time.perf_counter(); qv = vi.embed_query(text); t1 = time.perf_counter()
            res = vi.search(text, k=K, qvec=qv); t2 = time.perf_counter()
            ev = norm(evidence[qid])
            rank = next((r for r, x in enumerate(res, 1) if ev in norm(x["context"])), None)
            ranks.append(rank); rr.append(1 / rank if rank else 0.0)
            t_emb.append(t1 - t0); t_srch.append(t2 - t1)
        results[f"{key}/{lang}"] = {
            "queries": len(qs), "recall@5": round(float(np.mean([r is not None for r in ranks])), 3),
            "mrr": round(float(np.mean(rr)), 3),
            "embed_ms": round(1000 * float(np.mean(t_emb)), 2),
            "search_ms": round(1000 * float(np.mean(t_srch)), 3),
            "total_ms": round(1000 * float(np.mean(np.add(t_emb, t_srch))), 2)}
        per_query[f"{key}/{lang}"] = dict(zip(qs.keys(), ranks))
        print(key, lang, results[f"{key}/{lang}"])

json.dump({"results": results, "per_query_rank": per_query, "build": build},
          open(ROOT / "eval" / "embeddings_results.json", "w"), indent=2, ensure_ascii=False)

L = ["# Порівняння моделей embeddings", "",
     "Індекс: FAISS HNSW (inner product на нормалізованих векторах = косинус); стратегія chunking: hierarchical; "
     f"корпус: {len(docs)} документів; запитів: {len(en)} (EN) та {len(langs.get('uk', {}))} (UK, переклад); K={K}.", "",
     "## Параметри та час побудови", "",
     "| модель | dim | фрагментів | M | efConstruction | efSearch | embeddings, с | HNSW, с | разом, с |", "|---|---|---|---|---|---|---|---|---|"]
for k, b in build.items():
    L.append(f"| {b['model']} | {b['dim']} | {b['chunks']} | {b['M']} | {b['efConstruction']} | {b['efSearch']} | {b['embed_s']} | {b['hnsw_build_s']} | {b['build_total_s']} |")
L += ["", "## Якість і затримка (на запит)", "",
      "| модель / мова запиту | recall@5 | MRR | embedding запиту, мс | пошук HNSW, мс | разом, мс |", "|---|---|---|---|---|---|"]
for k, r in results.items():
    L.append(f"| {k} | {r['recall@5']} | {r['mrr']} | {r['embed_ms']} | {r['search_ms']} | {r['total_ms']} |")
L += ["", "## Ранг правильного контексту по запитах (— не потрапив у топ-5)", "",
      "| запит | " + " | ".join(results) + " |", "|---|" + "---|" * len(results)]
for qid in evidence:
    L.append(f"| {qid} | " + " | ".join(str(per_query[c].get(qid) or "—") for c in results) + " |")
L += ["", "## Upsert / delete (перевірка на 5 документах)", "", "(допишемо на наступному кроці)",
      "", "## Висновок", "", "(допишемо після аналізу таблиці)"]
(ROOT / "docs" / "embeddings_cmp.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\nЗаписано docs/embeddings_cmp.md")
