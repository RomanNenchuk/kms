"""Векторний пошук по базі знань (корпус ЛР 10/11, індекс e5 hierarchical).
Гібрид: dense (косинус по готових embeddings) + BM25, злиття RRF. Якщо sentence-transformers недоступний
(або EMBED_BACKEND=bm25) — працює лише BM25, у відповіді mode = "bm25".
Права: pre-filter за рівнем чутливості документа ДО ранжування."""
import json
import re
import sys
import numpy as np
from rank_bm25 import BM25Okapi
from . import config, guards


def _tok(s: str):
    return re.findall(r"\w+", s.lower())


def rrf(rankings, k=60):
    s = {}
    for r in rankings:
        for pos, i in enumerate(r):
            s[i] = s.get(i, 0.0) + 1.0 / (k + pos + 1)
    return sorted(s, key=s.get, reverse=True)


class KB:
    def __init__(self):
        d = json.loads(config.KB_INDEX_JSON.read_text(encoding="utf-8"))
        self.chunks, self.alive = d["chunks"], d["alive"]
        self.emb = np.load(config.KB_INDEX_NPY)
        assert len(self.chunks) == len(self.emb), "індекс і embeddings розійшлися"
        self.doc = self._doc_meta()
        self._load_extra()
        self.bm25 = BM25Okapi([_tok(c["text"]) for c in self.chunks])
        self._model = None
        self._model_failed = config.EMBED_BACKEND == "bm25"

    @staticmethod
    def _doc_meta():
        """doc_id -> {sensitivity, source_url, license}; найсуворіший рівень серед фрагментів + overrides."""
        meta = {}
        for line in open(config.KB_CORPUS, encoding="utf-8"):
            r = json.loads(line)
            lvl = r.get("sensitivity", "restricted")
            m = meta.setdefault(r["doc_id"], {"sensitivity": lvl, "source_url": r.get("source_url"), "license": r.get("license")})
            if config.LEVELS.get(lvl, 2) > config.LEVELS.get(m["sensitivity"], 2):
                m["sensitivity"] = lvl
        if config.KB_OVERRIDES.exists():
            for doc, lvl in json.loads(config.KB_OVERRIDES.read_text(encoding="utf-8")).items():
                if not doc.startswith("_") and doc in meta and lvl in config.LEVELS:
                    meta[doc]["sensitivity"] = lvl
        return meta

    def _load_extra(self):
        """Тільки для red teaming: KB_EXTRA=<jsonl> додає «отруєні» фрагменти (без embeddings: знаходяться через BM25)."""
        if not config.KB_EXTRA:
            return
        extra = []
        for line in open(config.KB_EXTRA, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                extra.append({"chunk_id": r["chunk_id"], "doc_id": r["doc_id"], "title": r["title"],
                              "section": r.get("section", r["title"]), "text": r["text"], "context": r["text"]})
                self.doc[r["doc_id"]] = {"sensitivity": r.get("sensitivity", "public"), "source_url": r.get("source_url"),
                                         "license": r.get("license")}
        self.chunks = self.chunks + extra
        self.alive = list(self.alive) + [True] * len(extra)
        self.emb = np.vstack([self.emb, np.zeros((len(extra), self.emb.shape[1]), dtype=self.emb.dtype)])

    def _embedder(self):
        if self._model is None and not self._model_failed:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(config.EMBED_MODEL)
            except Exception as e:  # немає пакета / немає мережі для завантаження моделі
                print(f"[vector] dense вимкнено ({type(e).__name__}); працює BM25", file=sys.stderr)
                self._model_failed = True
        return self._model

    def allowed(self, level: str) -> np.ndarray:
        lim = config.LEVELS[level]
        return np.array([i for i, c in enumerate(self.chunks)
                         if self.alive[i] and config.LEVELS.get(self.doc.get(c["doc_id"], {}).get("sensitivity", "restricted"), 2) <= lim],
                        dtype="int64")

    def search(self, query: str, k: int, level: str):
        ids = self.allowed(level)
        if len(ids) == 0:
            return [], "none"
        n = max(k * 6, 30)
        rankings, mode = [], "bm25"
        sc = self.bm25.get_scores(_tok(query))
        masked = np.full(len(sc), -np.inf)
        masked[ids] = sc[ids]
        rankings.append([int(i) for i in np.argsort(-masked)[:n] if masked[i] > 0])
        model = self._embedder()
        if model is not None:
            q = model.encode([config.E5_QUERY_PREFIX + query], normalize_embeddings=True).astype("float32")[0]
            sims = np.full(len(self.emb), -np.inf, dtype="float32")
            sims[ids] = self.emb[ids] @ q
            rankings.append([int(i) for i in np.argsort(-sims)[:n]])
            mode = "hybrid"
        out, seen = [], set()
        for i in rrf(rankings):
            c = self.chunks[i]
            if c["context"] in seen:        # один батьківський контекст — один раз
                continue
            seen.add(c["context"])
            out.append(i)
            if len(out) == k:
                break
        return out, mode


_kb: KB | None = None


def get_kb() -> KB:
    global _kb
    if _kb is None:
        _kb = KB()
    return _kb


def search(query: str, k: int = 5, level: str | None = None) -> dict:
    level = config.effective_level(level)
    k = max(1, min(int(k), config.MAX_K))
    kb = get_kb()
    idx, mode = kb.search(query, k, level)
    results, withheld = [], []
    for i in idx:
        c = kb.chunks[i]
        sid = f"kb:{c['chunk_id']}"
        text = c["context"][:config.MAX_CHUNK_CHARS]
        meta = kb.doc.get(c["doc_id"], {})
        if config.DEFENSES:
            flags = guards.scan_untrusted(text) or guards.scan_untrusted(c["title"] + " " + c["section"])
            if flags:                                   # карантин: підозрілий фрагмент моделі не віддаємо
                withheld.append({"id": sid, "reason": "possible_prompt_injection", "flags": flags})
                continue
            text = guards.wrap_untrusted(text, sid)
        results.append({"id": sid, "doc_id": c["doc_id"], "title": c["title"], "section": c["section"],
                        "source_url": meta.get("source_url"), "license": meta.get("license"), "text": text})
    return {"ok": True, "mode": mode, "query": query, "results": results, "withheld": withheld,
            "citation_ids": [r["id"] for r in results]}
