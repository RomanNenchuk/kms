"""Результат 3: HNSW-індекс (FAISS) для моделей embeddings + upsert/delete.

Схема:
  документи -> chunking (hierarchical) -> embeddings тільки для child.text -> HNSW
  пошук: query -> embedding -> HNSW -> child -> його context (батьківський розділ), без дублікатів.
FAISS HNSW не вміє видаляти вектори, тому використовуємо tombstones (мітки «видалено»)
і rebuild() для компактизації.
"""
import json, time
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from .config import (ROOT, INDEXES, EMB_MODELS, E5_QUERY_PREFIX, E5_PASSAGE_PREFIX,
                     HNSW_M, HNSW_EF_CONSTRUCTION, HNSW_EF_SEARCH, SEED)
from .chunking import load_docs, STRATEGIES

faiss.omp_set_num_threads(1)  # один потік: побудова HNSW стає відтворюваною


class VectorIndex:
    def __init__(self, model_key, strategy="hierarchical", M=HNSW_M,
                 ef_construction=HNSW_EF_CONSTRUCTION, ef_search=HNSW_EF_SEARCH):
        self.model_key, self.strategy = model_key, strategy
        self.M, self.ef_construction, self.ef_search = M, ef_construction, ef_search
        self.model = SentenceTransformer(EMB_MODELS[model_key])
        self.q_prefix, self.p_prefix = ((E5_QUERY_PREFIX, E5_PASSAGE_PREFIX)
                                        if model_key == "e5" else ("", ""))
        self.chunks, self.emb, self.index = [], None, None
        self.alive = []            # alive[i] == False -> вектор i «видалений»
        self.stats = {}

    # ---------- допоміжне ----------
    def _new_hnsw(self, dim):
        idx = faiss.IndexHNSWFlat(dim, self.M, faiss.METRIC_INNER_PRODUCT)
        idx.hnsw.efConstruction = self.ef_construction
        idx.hnsw.efSearch = self.ef_search
        return idx

    def _embed_passages(self, chunks):
        return self.model.encode([self.p_prefix + c["text"] for c in chunks], batch_size=32,
                                 normalize_embeddings=True, show_progress_bar=False).astype("float32")

    def embed_query(self, q):
        return self.model.encode([self.q_prefix + q], normalize_embeddings=True).astype("float32")

    # ---------- побудова ----------
    def build(self, docs=None):
        docs = docs if docs is not None else load_docs()
        self.chunks = STRATEGIES[self.strategy](docs)
        t0 = time.time()
        self.emb = self._embed_passages(self.chunks)
        t_embed = time.time() - t0
        t0 = time.time()
        self.index = self._new_hnsw(self.emb.shape[1])
        self.index.add(self.emb)
        t_hnsw = time.time() - t0
        self.alive = [True] * len(self.chunks)
        self.stats = {"model": EMB_MODELS[self.model_key], "strategy": self.strategy,
                      "dim": int(self.emb.shape[1]), "chunks": len(self.chunks),
                      "M": self.M, "efConstruction": self.ef_construction, "efSearch": self.ef_search,
                      "embed_s": round(t_embed, 2), "hnsw_build_s": round(t_hnsw, 2),
                      "build_total_s": round(t_embed + t_hnsw, 2)}
        return self.stats

    # ---------- пошук ----------
    def search(self, query, k=5, deep=60, qvec=None):
        """Повертає до k різних контекстів. qvec — готовий embedding запиту (для вимірювання часу)."""
        qv = qvec if qvec is not None else self.embed_query(query)
        n_live = sum(self.alive)
        deep = min(deep + (len(self.alive) - n_live), len(self.chunks))  # запас на tombstones
        scores, ids = self.index.search(qv, deep)
        out, seen = [], set()
        for s, i in zip(scores[0], ids[0]):
            if i < 0 or not self.alive[i]:
                continue
            c = self.chunks[i]
            if c["context"] in seen:
                continue
            seen.add(c["context"])
            out.append({"score": float(s), "chunk_id": c["chunk_id"], "doc_id": c["doc_id"],
                        "title": c["title"], "section": c["section"], "context": c["context"]})
            if len(out) == k:
                break
        return out

    # ---------- оновлення ----------
    def delete(self, doc_id):
        """Позначає всі вектори документа як видалені. Повертає кількість."""
        n = 0
        for i, c in enumerate(self.chunks):
            if c["doc_id"] == doc_id and self.alive[i]:
                self.alive[i] = False; n += 1
        return n

    def upsert(self, doc):
        """doc = {'doc_id','title','body'}. Старі вектори -> tombstones, нові додаються в граф."""
        removed = self.delete(doc["doc_id"])
        new = STRATEGIES[self.strategy]([doc])
        if new:
            vecs = self._embed_passages(new)
            self.index.add(vecs)
            self.emb = np.vstack([self.emb, vecs])
            self.chunks.extend(new)
            self.alive.extend([True] * len(new))
        return {"removed": removed, "added": len(new)}

    def dead_fraction(self):
        return 1 - sum(self.alive) / max(len(self.alive), 1)

    def rebuild(self):
        """Компактизація: будуємо HNSW заново лише з «живих» векторів."""
        keep = [i for i, a in enumerate(self.alive) if a]
        self.chunks = [self.chunks[i] for i in keep]
        self.emb = self.emb[keep]
        self.index = self._new_hnsw(self.emb.shape[1])
        self.index.add(self.emb)
        self.alive = [True] * len(self.chunks)
        return len(self.chunks)

    @classmethod
    def load(cls, model_key, strategy="hierarchical"):
        """Завантажує готовий індекс з indexes/ без перебудови."""
        self = cls(model_key, strategy)
        base = INDEXES / f"{model_key}_{strategy}"
        self.index = faiss.read_index(str(base) + ".faiss")
        self.index.hnsw.efSearch = self.ef_search
        meta = json.load(open(str(base) + ".json", encoding="utf-8"))
        self.chunks, self.alive, self.stats = meta["chunks"], meta["alive"], meta["stats"]
        self.emb = np.load(str(base) + ".npy")
        return self

    # ---------- збереження ----------
    def save(self):
        INDEXES.mkdir(exist_ok=True)
        base = INDEXES / f"{self.model_key}_{self.strategy}"
        faiss.write_index(self.index, str(base) + ".faiss")
        json.dump({"chunks": self.chunks, "alive": self.alive, "stats": self.stats},
                  open(str(base) + ".json", "w", encoding="utf-8"), ensure_ascii=False)
        np.save(str(base) + ".npy", self.emb)
        return base


if __name__ == "__main__":
    import sys
    queries = [json.loads(l) for l in open(ROOT / "eval" / "queries_20.jsonl", encoding="utf-8")]
    queries = [q for q in queries if q.get("status") == "verified"]
    docs = load_docs()
    rows = {}
    for key in EMB_MODELS:
        print(f"\n=== {key}: {EMB_MODELS[key]} ===")
        vi = VectorIndex(key)
        st = vi.build(docs)
        qv = [vi.embed_query(q["question"]) for q in queries]       # час embedding запитів міряємо окремо
        t_q = []
        for q in queries:
            t0 = time.perf_counter(); vi.embed_query(q["question"]); t_q.append(time.perf_counter() - t0)
        REPEAT = 5
        t_s = []
        for _ in range(REPEAT):
            for v in qv:
                t0 = time.perf_counter(); vi.search("", k=5, qvec=v); t_s.append(time.perf_counter() - t0)
        st["queries"] = len(queries)
        st["query_embed_ms"] = round(1000 * float(np.mean(t_q)), 2)
        st["hnsw_search_ms"] = round(1000 * float(np.mean(t_s)), 3)
        vi.save()
        rows[key] = st
        print(json.dumps(st, ensure_ascii=False, indent=2))
    json.dump(rows, open(ROOT / "eval" / "index_build.json", "w"), indent=2, ensure_ascii=False)
    print("\nЗаписано eval/index_build.json; індекси збережено в indexes/")
