"""Підхід на embeddings: kNN (FAISS) по векторах документів. Вектор документа = нормоване середнє e5-векторів
його фрагментів (data/indexes). Профіль користувача = зважена сума векторів документів з історії train."""
import json
import faiss
import numpy as np
from . import config as C


class EmbedReco:
    name = "embed"

    def fit(self, ds, train):
        self.ds = ds
        d = json.loads(C.KB_INDEX_JSON.read_text(encoding="utf-8"))
        emb = np.load(C.KB_INDEX_NPY).astype("float32")
        by = {}
        for ch, v in zip(d["chunks"], emb):
            by.setdefault(ch["doc_id"], []).append(v)
        self.docs = sorted(ds.items)
        missing = [x for x in self.docs if x not in by]
        assert not missing, f"немає embeddings для {missing}"
        M = np.stack([np.mean(by[x], axis=0) for x in self.docs]).astype("float32")
        faiss.normalize_L2(M)
        self.vec = dict(zip(self.docs, M))
        self.index = faiss.IndexFlatIP(M.shape[1])         # косинус = скалярний добуток нормованих
        self.index.add(M)
        self.hist = {}
        for e in train:
            w = C.EVENT_WEIGHT[e["event"]]
            if w > 0:
                self.hist.setdefault(e["user_id"], {}).setdefault(e["doc_id"], 0.0)
                self.hist[e["user_id"]][e["doc_id"]] += w
        return self

    def profile(self, user_id):
        h = self.hist.get(user_id)
        if not h:
            return None                                      # холодний старт: розв'язується в explain/cold_start (Р3)
        p = sum(w * self.vec[d] for d, w in h.items()).astype("float32")[None, :]
        faiss.normalize_L2(p)
        return p

    def score(self, user_id, history=None):
        p = self.profile(user_id)
        if p is None:
            return {}
        sims, ids = self.index.search(p, len(self.docs))
        return {self.docs[i]: float(s) for s, i in zip(sims[0], ids[0])}

    def path(self, user_id, doc_id):
        """Пояснення для kNN: найближчий документ з історії користувача."""
        h = self.hist.get(user_id)
        if not h:
            return None
        near = max(h, key=lambda d: (float(self.vec[d] @ self.vec[doc_id]), d))
        return {"component": "embed", "topic": None, "similar_to": near,
                "cosine": round(float(self.vec[near] @ self.vec[doc_id]), 3)}
