"""Результат 2, кроки 2-3: індекс для кожної стратегії (одна модель) + порівняння.
Запуск: python -m src.compare_chunking
Вхід:  eval/chunking_queries.jsonl (status=verified), kb/**/*.md
Вихід: docs/chunking_cmp.md, eval/chunking_results.json
"""
import json, time, re
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from .config import ROOT, EMB_MODELS, E5_QUERY_PREFIX, E5_PASSAGE_PREFIX, SEED
from .chunking import load_docs, STRATEGIES

MODEL_NAME = EMB_MODELS["e5"]
K = 5
DEEP = 60  # скільки кандидатів дістаємо, щоб набрати K різних контекстів

np.random.seed(SEED)
norm = lambda s: re.sub(r"\s+", "", s).lower()

queries = [json.loads(l) for l in open(ROOT / "eval" / "chunking_queries.jsonl", encoding="utf-8")]
queries = [q for q in queries if q.get("status") == "verified"]
print(f"Запитів: {len(queries)}")

docs = load_docs()
model = SentenceTransformer(MODEL_NAME)
q_emb = model.encode([E5_QUERY_PREFIX + q["question"] for q in queries],
                     normalize_embeddings=True).astype("float32")

results, per_query = {}, {}
for name, fn in STRATEGIES.items():
    chunks = fn(docs)
    t0 = time.time()
    emb = model.encode([E5_PASSAGE_PREFIX + c["text"] for c in chunks], batch_size=32,
                       normalize_embeddings=True, show_progress_bar=True).astype("float32")
    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb)
    build = time.time() - t0

    hits, rr, ctx_sizes, per_query[name] = [], [], [], []
    for qi, q in enumerate(queries):
        _, ids = index.search(q_emb[qi:qi + 1], min(DEEP, len(chunks)))
        contexts, seen = [], set()
        for i in ids[0]:
            c = chunks[i]["context"]
            if c not in seen:
                seen.add(c); contexts.append(c)
            if len(contexts) == K:
                break
        ev = norm(q["evidence"])
        rank = next((r for r, c in enumerate(contexts, 1) if ev in norm(c)), None)
        hits.append(rank is not None)
        rr.append(1 / rank if rank else 0.0)
        ctx_sizes.append(np.mean([len(c) for c in contexts]))
        per_query[name].append(rank)

    results[name] = {
        "chunks": len(chunks),
        "avg_text_chars": round(float(np.mean([len(c["text"]) for c in chunks]))),
        "recall@5": round(float(np.mean(hits)), 3),
        "mrr": round(float(np.mean(rr)), 3),
        "avg_context_chars": round(float(np.mean(ctx_sizes))),
        "build_s": round(build, 1),
    }
    print(name, results[name])

(ROOT / "eval").mkdir(exist_ok=True)
json.dump({"model": MODEL_NAME, "results": results, "per_query_rank": per_query},
          open(ROOT / "eval" / "chunking_results.json", "w"), indent=2)

L = ["# Порівняння стратегій chunking", "",
     f"Модель embeddings (фіксована): `{MODEL_NAME}`; індекс: FAISS IndexFlatIP (косинус); запитів: {len(queries)}; K={K}.",
     "Фрагмент вважається релевантним, якщо його контекст містить речення-доказ запиту (без урахування пробілів і регістру). "
     "Для кожного запиту береться топ-5 різних контекстів.", "",
     "| стратегія | фрагментів | сер. text, симв. | recall@5 | MRR | сер. розмір контексту, симв. | час побудови, с |",
     "|---|---|---|---|---|---|---|"]
for n, r in results.items():
    L.append(f"| {n} | {r['chunks']} | {r['avg_text_chars']} | {r['recall@5']} | {r['mrr']} | {r['avg_context_chars']} | {r['build_s']} |")
L += ["", "## Ранг правильного контексту по запитах (— означає: не потрапив у топ-5)", "",
      "| запит | " + " | ".join(results) + " |", "|---|" + "---|" * len(results)]
for qi, q in enumerate(queries):
    L.append(f"| {q['id']} | " + " | ".join(str(per_query[n][qi] or "—") for n in results) + " |")
L += ["", "## Вибір і обґрунтування", "", "(допишемо після аналізу таблиці)"]
(ROOT / "docs" / "chunking_cmp.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\nЗаписано docs/chunking_cmp.md")
