"""Результат 1: RAG-конвеєр із цитуванням.

запит -> гібридний пошук (dense HNSW + BM25, RRF) з pre-filter за правами
      -> reranking (cross-encoder) -> промпт (prompts/rag_v1.md) -> LLM (Gemini)
      -> перевірка цитат -> журнал llm_log/rag_calls.jsonl

Запуск:  python -m src.rag "питання"      |      python -m src.rag --demo [N]
"""
import os, re, sys, json, time, uuid, datetime as dt, pathlib
import numpy as np
import faiss
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from google import genai
from google.genai import types
from .config import ROOT, SEED
from .index import VectorIndex

LEVELS = {"public": 0, "internal": 1, "restricted": 2}   # чим більше, тим чутливіше
PROMPT_PATH = ROOT / "prompts" / "rag_v1.md"
LOG_PATH = ROOT / "llm_log" / "rag_calls.jsonl"
RERANKER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
MAX_CTX_CHARS = 3000            # скільки символів одного контексту йде в промпт
CITE_RE = re.compile(r"\[([^\[\]]+)\]")


def tok(s):
    return re.findall(r"\w+", s.lower())


def load_prompt(path=PROMPT_PATH):
    raw = pathlib.Path(path).read_text(encoding="utf-8")
    m = re.search(r"##\s*SYSTEM\s*\n(.*?)\n##\s*USER\s*\n(.*)", raw, re.S)
    return m.group(1).strip(), m.group(2).strip()


def load_doc_meta(path=ROOT / "data" / "corpus.jsonl", overrides=ROOT / "data" / "sensitivity_overrides.json"):
    """doc_id -> sensitivity (найсуворіша серед фрагментів), source_url, license. Невідомий doc = restricted.
    data/sensitivity_overrides.json (якщо є) підвищує рівень окремих документів — демо ролей API; перебудова індексу не потрібна."""
    meta = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        lvl = r.get("sensitivity", "restricted")
        m = meta.setdefault(r["doc_id"], {"sensitivity": lvl, "source_url": r.get("source_url"), "license": r.get("license")})
        if LEVELS.get(lvl, 2) > LEVELS.get(m["sensitivity"], 2):
            m["sensitivity"] = lvl
    if pathlib.Path(overrides).exists():
        for doc, lvl in json.load(open(overrides, encoding="utf-8")).items():
            if doc.startswith("_"):
                continue
            if doc not in meta or lvl not in LEVELS:
                raise ValueError(f"sensitivity_overrides: невідомий документ або рівень: {doc}={lvl}")
            meta[doc]["sensitivity"] = lvl
    return meta


def rrf(rankings, k=60):
    """Reciprocal Rank Fusion: зливає кілька ранжувань у одне."""
    s = {}
    for r in rankings:
        for pos, i in enumerate(r):
            s[i] = s.get(i, 0.0) + 1.0 / (k + pos + 1)
    return sorted(s, key=s.get, reverse=True)


def validate_citations(answer, allowed_ids):
    """Крок 3: чи всі цитовані id є серед наданого контексту."""
    cited = []
    for grp in CITE_RE.findall(answer):
        cited += [p.strip() for p in re.split(r"[;,]", grp) if p.strip()]
    allowed = set(allowed_ids)
    return {"cited": sorted({c for c in cited if c in allowed}),
            "invalid": sorted({c for c in cited if c not in allowed})}


class RAG:
    def __init__(self, model_key="e5", strategy="hierarchical", prompt_path=PROMPT_PATH):
        self.vi = VectorIndex.load(model_key, strategy)
        self.meta = load_doc_meta()
        self.system, self.user_tpl = load_prompt(prompt_path)
        self.prompt_version = pathlib.Path(prompt_path).stem
        self.bm25 = BM25Okapi([tok(c["text"]) for c in self.vi.chunks])
        self.reranker = CrossEncoder(RERANKER)
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])  # один клієнт на весь процес
        self.model = os.environ["GEMINI_MODEL"]
        self.temperature = float(os.getenv("GEN_TEMPERATURE", "0"))
        self.seed = int(os.getenv("SEED", SEED))
        self.max_per_doc = int(os.getenv("MAX_PER_DOC", "0")) or None   # Результат 5: ліміт контекстів з одного документа

    # ---------- пошук ----------
    def _allowed_ids(self, max_level):
        lim = LEVELS[max_level]
        return np.array([i for i, c in enumerate(self.vi.chunks)
                         if self.vi.alive[i]
                         and LEVELS.get(self.meta.get(c["doc_id"], {}).get("sensitivity", "restricted"), 2) <= lim],
                        dtype="int64")

    def _dense(self, query, ids, n):
        params = faiss.SearchParametersHNSW()
        params.efSearch = max(self.vi.ef_search, n)
        params.sel = faiss.IDSelectorBatch(ids)          # pre-filter: недозволені вектори не потрапляють у видачу
        _, found = self.vi.index.search(self.vi.embed_query(query), n, params=params)
        return [int(i) for i in found[0] if i >= 0]

    def _bm25(self, query, ids, n):
        sc = self.bm25.get_scores(tok(query))
        masked = np.full(len(sc), -np.inf)
        masked[ids] = sc[ids]
        return [int(i) for i in np.argsort(-masked)[:n] if masked[i] > 0]

    def retrieve(self, query, max_level="public", n_cand=30, n_ctx=15, top_k=5):
        t0 = time.perf_counter()
        ids = self._allowed_ids(max_level)
        if len(ids) == 0:
            return [], {"retrieve": 0.0, "rerank": 0.0}
        fused = rrf([self._dense(query, ids, n_cand), self._bm25(query, ids, n_cand)])
        cands, seen, per_doc = [], set(), {}
        for i in fused:                                   # один батьківський контекст — один раз
            c = self.vi.chunks[i]
            if c["context"] in seen:
                continue
            if self.max_per_doc and per_doc.get(c["doc_id"], 0) >= self.max_per_doc:
                continue                                   # ліміт контекстів з одного документа
            seen.add(c["context"])
            per_doc[c["doc_id"]] = per_doc.get(c["doc_id"], 0) + 1
            cands.append(c)
            if len(cands) == n_ctx:
                break
        t1 = time.perf_counter()
        scores = self.reranker.predict([(query, f'{c["title"]} — {c["section"]}: {c["text"]}') for c in cands])
        order = np.argsort(-np.asarray(scores))[:top_k]
        src = [{"id": cands[j]["chunk_id"], "doc_id": cands[j]["doc_id"], "title": cands[j]["title"],
                "section": cands[j]["section"], "text": cands[j]["context"][:MAX_CTX_CHARS],
                "rerank_score": float(scores[j])} for j in order]
        t2 = time.perf_counter()
        return src, {"retrieve": 1000 * (t1 - t0), "rerank": 1000 * (t2 - t1)}

    # ---------- промпт і генерація ----------
    def build_prompt(self, query, sources):
        ctx = "\n\n".join(f"### SOURCE [{s['id']}] — {s.get('header') or s['title'] + ' / ' + s['section']}\n{s['text']}"
                          for s in sources)
        vals = {"context": ctx, "question": query}
        return re.sub(r"\{(context|question)\}", lambda m: vals[m.group(1)], self.user_tpl)  # один прохід

    def _generate(self, user):
        cfg = types.GenerateContentConfig(system_instruction=self.system,
                                          temperature=self.temperature, seed=self.seed)
        for attempt in range(4):
            try:
                r = self.client.models.generate_content(model=self.model, contents=user, config=cfg)
                break
            except Exception as e:
                if attempt < 3 and any(x in str(e) for x in ("429", "500", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                    time.sleep(2 ** attempt * 2)
                    continue
                raise
        um = r.usage_metadata
        usage = {"prompt": um.prompt_token_count, "output": um.candidates_token_count,
                 "thoughts": getattr(um, "thoughts_token_count", None), "total": um.total_token_count}
        return r.text or "", usage

    # ---------- головний виклик ----------
    def ask(self, query, max_level="public", extra_sources=None, top_k=5, tag=None):
        """extra_sources: [{'id','header','text'}] — додаткові цитовані джерела (напр. підграф у ЛР 11, результат 2)."""
        t0 = time.perf_counter()
        sources, tm = self.retrieve(query, max_level, top_k=top_k)
        sources = sources + (extra_sources or [])
        t_llm0 = time.perf_counter()
        if sources:
            raw, usage = self._generate(self.build_prompt(query, sources))
        else:                                              # нема дозволених джерел -> LLM не викликаємо
            raw, usage = "NO_ANSWER: у доступних вам джерелах немає інформації.", {"prompt": 0, "output": 0, "thoughts": 0, "total": 0}
        t_llm = time.perf_counter() - t_llm0
        abstained = raw.lstrip().upper().startswith("NO_ANSWER")
        answer = re.sub(r"^\s*NO_ANSWER\s*:?\s*", "", raw, flags=re.I) if abstained else raw.strip()
        cit = validate_citations(answer, [s["id"] for s in sources])
        cit["ok"] = not cit["invalid"] and (abstained or bool(cit["cited"]))
        res = {"request_id": uuid.uuid4().hex[:12], "query": query, "answer": answer, "abstained": abstained,
               "sources": [{"id": s["id"], "doc_id": s.get("doc_id"), "rerank_score": s.get("rerank_score")} for s in sources],
               "citations": cit, "tokens": usage, "model": self.model, "tag": tag,
               "latency_ms": {"retrieve": round(tm["retrieve"], 1), "rerank": round(tm["rerank"], 1),
                              "llm": round(1000 * t_llm, 1), "total": round(1000 * (time.perf_counter() - t0), 1)}}
        self._log(res, raw, max_level)
        return res

    def _log(self, res, raw, max_level):
        LOG_PATH.parent.mkdir(exist_ok=True)
        rec = {"date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               **res, "raw_output": raw, "access_level": max_level, "prompt_version": self.prompt_version,
               "params": {"temperature": self.temperature, "seed": self.seed, "max_per_doc": self.max_per_doc}, "human_decision": None}
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _print(res, extra=""):
    print(f"\nQ: {res['query']} {extra}\nA: {res['answer']}")
    print(f"   джерела: {[s['id'] for s in res['sources']]}")
    print(f"   цитати: {res['citations']} | abstained={res['abstained']} | токени={res['tokens']['total']} | {res['latency_ms']['total']} мс")


if __name__ == "__main__":
    args = sys.argv[1:]
    rag = RAG()
    if args and args[0] == "--demo":
        n = int(args[1]) if len(args) > 1 else 6
        gold = [json.loads(l) for l in open(ROOT / "eval" / "gold.jsonl", encoding="utf-8")]
        gold = [g for g in gold if g.get("status") == "verified"]
        by_type = {}
        for g in gold:
            by_type.setdefault(g["type"], []).append(g)
        picked, i = [], 0
        while len(picked) < n and any(i < len(v) for v in by_type.values()):   # по черзі з кожного типу
            picked += [v[i] for v in by_type.values() if i < len(v)]
            i += 1
        for g in picked[:n]:
            _print(rag.ask(g["question"]), f"[{g['type']}, очікується {g['doc_ids'] or 'NO_ANSWER'}]")
    else:
        _print(rag.ask(" ".join(args)))
