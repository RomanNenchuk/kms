"""Результат 4: BM25 + dense + RRF(k=60) + cross-encoder rerank + pre-filter за метаданими.

Одиниця пошуку — «дитина» (child) з hierarchical-індексу; користувачу повертається її контекст
(батьківський розділ), без дублікатів.
Режими: "bm25", "dense", "hybrid" (RRF), "hybrid_rerank" (RRF -> топ-30 -> cross-encoder -> топ-5).
"""
import json, re, time
import numpy as np
import faiss
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from .config import ROOT, RERANKER, RRF_K
from .chunking import load_docs
from .index import VectorIndex

STOP = set("a an the of in on at to for and or is are was were be by with as from that this it its which what "
           "who when how why do does did can has have had not no into than then their there these those about "
           "over under between during after before".split())
tok = lambda s: [w for w in re.findall(r"\w+", s.lower()) if w not in STOP]
MODES = ("bm25", "dense", "hybrid", "hybrid_rerank")


def rrf(rank_lists, k=RRF_K):
    """Reciprocal Rank Fusion: score(d) = sum_i 1/(k + rank_i(d)), rank починається з 1."""
    score = {}
    for lst in rank_lists:
        for r, i in enumerate(lst, 1):
            score[i] = score.get(i, 0.0) + 1.0 / (k + r)
    return sorted(score, key=score.get, reverse=True), score


class HybridSearcher:
    def __init__(self, vi: VectorIndex, docs=None):
        self.vi = vi
        docs = docs if docs is not None else load_docs()
        self.meta = {d["doc_id"]: d["meta"] for d in docs}
        self.bm25 = BM25Okapi([tok(c["text"]) for c in vi.chunks])
        self.sens_override = {}      # doc_id -> sensitivity (лише для імітації в тестах)
        self._rr = None

    @property
    def reranker(self):
        if self._rr is None:
            self._rr = CrossEncoder(RERANKER)
        return self._rr

    # ---------- метадані й pre-filter ----------
    def _field(self, i, name):
        did = self.vi.chunks[i]["doc_id"]
        if name == "sensitivity" and did in self.sens_override:
            return self.sens_override[did]
        return self.meta.get(did, {}).get(name, "")

    def allowed_ids(self, filters=None):
        """filters: {'type': [...], 'sensitivity': [...], 'date_from': 'YYYY-MM-DD', 'date_to': '...'}"""
        f = filters or {}
        out = []
        for i in range(len(self.vi.chunks)):
            if not self.vi.alive[i]:
                continue
            if "type" in f and self._field(i, "type") not in f["type"]:
                continue
            if "sensitivity" in f and self._field(i, "sensitivity") not in f["sensitivity"]:
                continue
            d = self._field(i, "date")
            if "date_from" in f and not (d and d >= f["date_from"]):
                continue
            if "date_to" in f and not (d and d <= f["date_to"]):
                continue
            out.append(i)
        return np.array(out, dtype="int64")

    # ---------- два пошуки ----------
    def dense_ranked(self, qv, allowed, n):
        if len(allowed) == 0:
            return []
        p = faiss.SearchParametersHNSW()
        p.sel = faiss.IDSelectorBatch(allowed)           # pre-filter всередині пошуку по графу
        p.efSearch = max(self.vi.ef_search, n)
        _, I = self.vi.index.search(qv, min(n, len(allowed)), params=p)
        return [int(i) for i in I[0] if i >= 0]

    def bm25_ranked(self, query, allowed, n):
        if len(allowed) == 0:
            return []
        sc = self.bm25.get_scores(tok(query))[allowed]
        order = np.argsort(-sc)[:n]
        return [int(allowed[j]) for j in order if sc[j] > 0]   # без збігу слів — не кандидат

    # ---------- основний пошук ----------
    def _dedupe(self, ids, limit):
        out, seen = [], set()
        for i in ids:
            c = self.vi.chunks[i]["context"]
            if c not in seen:
                seen.add(c); out.append(i)
            if len(out) == limit:
                break
        return out

    def search(self, query, mode="hybrid_rerank", k=5, filters=None, pool=30, n_cand=60):
        assert mode in MODES
        allowed = self.allowed_ids(filters)
        qv = self.vi.embed_query(query) if mode != "bm25" else None
        dense = self.dense_ranked(qv, allowed, n_cand) if mode != "bm25" else []
        bm = self.bm25_ranked(query, allowed, n_cand) if mode != "dense" else []
        if mode == "bm25":      ids = bm
        elif mode == "dense":   ids = dense
        else:                   ids, _ = rrf([dense, bm])
        if mode == "hybrid_rerank":
            cand = self._dedupe(ids, pool)
            if not cand:
                return []
            sc = self.reranker.predict([(query, self.vi.chunks[i]["context"]) for i in cand])
            order = np.argsort(-np.asarray(sc))[:k]
            return [self._row(cand[j], rerank_score=float(sc[j])) for j in order]
        return [self._row(i) for i in self._dedupe(ids, k)]

    def _row(self, i, **extra):
        c = self.vi.chunks[i]
        return {"chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "title": c["title"], "section": c["section"],
                "type": self._field(i, "type"), "sensitivity": self._field(i, "sensitivity"),
                "context": c["context"], **extra}


# ======================================================================
if __name__ == "__main__":
    norm = lambda s: re.sub(r"\s+", "", s).lower()
    read = lambda p: [json.loads(l) for l in open(ROOT / p, encoding="utf-8")]
    en = [q for q in read("eval/queries_20.jsonl") if q.get("status") == "verified"]
    sets = {"en": {q["id"]: q["question"] for q in en}}
    if (ROOT / "eval/queries_20_uk.jsonl").exists():
        sets["uk"] = {r["id"]: r["question_uk"] for r in read("eval/queries_20_uk.jsonl") if r.get("status") == "verified"}
    ev = {q["id"]: q["evidence"] for q in en}

    docs = load_docs()
    vi = VectorIndex("e5"); vi.build(docs)
    hs = HybridSearcher(vi, docs)
    hs.search("warm up", "hybrid_rerank")                           # прогрів моделей

    def rank_in(res, qid):
        e = norm(ev[qid])
        return next((r for r, x in enumerate(res, 1) if e in norm(x["context"])), None)

    # ---- 1. чотири конфігурації ----
    metrics, ranks, tops, lat = {}, {}, {}, {}
    for lang, qs in sets.items():
        for mode in MODES:
            rr, rk, t = [], {}, []
            for qid, text in qs.items():
                t0 = time.perf_counter(); res = hs.search(text, mode); t.append(time.perf_counter() - t0)
                r = rank_in(res, qid); rk[qid] = r; rr.append(1 / r if r else 0.0)
                tops[(lang, mode, qid)] = [x["chunk_id"] for x in res]
                tops[(lang, mode, qid, "ctx")] = res[0]["context"][:220].replace("\n", " ") if res else ""
            ranks[(lang, mode)] = rk
            metrics[(lang, mode)] = {"recall@5": round(float(np.mean([v is not None for v in rk.values()])), 3),
                                     "mrr": round(float(np.mean(rr)), 3), "ms": round(1000 * float(np.mean(t)), 1)}
            print(lang, mode, metrics[(lang, mode)])

    # ---- 2. чи змінює reranker топ-5 ----
    changed = {}
    for lang, qs in sets.items():
        ch = [qid for qid in qs if tops[(lang, "hybrid", qid)] != tops[(lang, "hybrid_rerank", qid)]]
        changed[lang] = ch
        print(f"{lang}: reranker змінив топ-5 у {len(ch)} із {len(qs)} запитів")

    # ---- 3. тести pre-filter ----
    ft = []
    q0 = next(iter(sets["en"].values()))
    res = hs.search(q0, "hybrid", filters={"type": ["regulation"]})
    ft.append(("type=regulation", bool(res) and all(x["type"] == "regulation" for x in res), f"{len(res)} результатів, типи: {sorted({x['type'] for x in res})}"))
    first_doc = vi.chunks[0]["doc_id"]
    hs.sens_override[first_doc] = "restricted"                      # ІМІТАЦІЯ: лише в пам'яті
    base_q = [q["question"] for q in en if q["doc_id"] == first_doc]
    probe = base_q[0] if base_q else vi.chunks[0]["text"][:120]
    r_open = hs.search(probe, "hybrid", filters={"sensitivity": ["public", "restricted"]})
    r_pub = hs.search(probe, "hybrid", filters={"sensitivity": ["public"]})
    ft.append((f"sensitivity=public (імітація: {first_doc} -> restricted)",
              all(x["doc_id"] != first_doc for x in r_pub) and any(x["doc_id"] == first_doc for x in r_open),
              f"з restricted у видачі: {any(x['doc_id']==first_doc for x in r_open)}; у public-режимі: {any(x['doc_id']==first_doc for x in r_pub)}"))
    hs.sens_override.clear()
    r1 = hs.search(q0, "hybrid", filters={"date_from": "2999-01-01"}); r2 = hs.search(q0, "hybrid", filters={"date_from": "2000-01-01"})
    ft.append(("date_from (2999 / 2000)", len(r1) == 0 and len(r2) > 0, f"2999-01-01: {len(r1)} результатів; 2000-01-01: {len(r2)}"))
    r3 = hs.search(q0, "bm25", filters={"type": ["reference"]}); r4 = hs.search(q0, "dense", filters={"type": ["reference"]})
    ft.append(("type=reference у bm25 та dense", all(x["type"] == "reference" for x in r3 + r4), f"bm25: {len(r3)}, dense: {len(r4)}"))
    for n, ok, d in ft: print("FILTER", "OK " if ok else "FAIL", n, "|", d)

    # ---- 4. виграші / програші гібриду відносно dense ----
    big = 99
    cmp_rows = []
    for lang, qs in sets.items():
        for qid in qs:
            d, h = ranks[(lang, "dense")][qid] or big, ranks[(lang, "hybrid")][qid] or big
            if d != h:
                cmp_rows.append({"lang": lang, "id": qid, "dense": None if d == big else d, "hybrid": None if h == big else h,
                                 "bm25": ranks[(lang, "bm25")][qid], "question": sets[lang][qid], "evidence": ev[qid],
                                 "dense_top1": tops[(lang, "dense", qid, "ctx")], "hybrid_top1": tops[(lang, "hybrid", qid, "ctx")],
                                 "delta": d - h})
    wins = sorted([r for r in cmp_rows if r["delta"] > 0], key=lambda r: -r["delta"])
    losses = sorted([r for r in cmp_rows if r["delta"] < 0], key=lambda r: r["delta"])
    print(f"\nГібрид кращий за dense у {len(wins)} випадках, гірший у {len(losses)} (з {sum(len(q) for q in sets.values())} пар запит×мова)")
    for tag, lst in (("ВИГРАШ", wins[:5]), ("ПРОГРАШ", losses[:3])):
        for r in lst:
            print(f"\n{tag} [{r['lang']} {r['id']}] dense={r['dense']} hybrid={r['hybrid']} bm25={r['bm25']}\n  Q: {r['question']}\n  E: {r['evidence']}\n  dense top1: {r['dense_top1']}\n  hybrid top1: {r['hybrid_top1']}")

    # ---- 5. запис ----
    json.dump({"metrics": {f"{l}/{m}": v for (l, m), v in metrics.items()},
               "reranker_changed": changed, "filter_tests": [{"test": n, "ok": ok, "detail": d} for n, ok, d in ft],
               "wins": wins, "losses": losses},
              open(ROOT / "eval" / "hybrid_results.json", "w"), indent=2, ensure_ascii=False)
    L = ["# Звіт: гібридний пошук і reranking", "",
         f"Корпус: {len(docs)} документів, {len(vi.chunks)} дочірніх фрагментів; dense: `{vi.stats['model']}` (HNSW M={vi.M}, efSearch={vi.ef_search}); "
         f"BM25 (rank_bm25, токени без стоп-слів, без стемінгу); RRF k={RRF_K}; reranker `{RERANKER}` (топ-30 -> топ-5).", "",
         "## Конфігурації на 20 запитах", "", "| мова | режим | recall@5 | MRR | мс на запит |", "|---|---|---|---|---|"]
    for (l, m), v in metrics.items():
        L.append(f"| {l} | {m} | {v['recall@5']} | {v['mrr']} | {v['ms']} |")
    L += ["", "## Reranker змінює топ-5", ""]
    for lang, ch in changed.items():
        L.append(f"- {lang}: порядок/склад топ-5 після reranker змінився у {len(ch)} із {len(sets[lang])} запитів ({', '.join(ch) or '—'}).")
    L += ["", "## Pre-filter за метаданими", "", "| перевірка | результат | деталі |", "|---|---|---|"]
    for n, ok, d in ft: L.append(f"| {n} | {'пройдено' if ok else 'НЕ ПРОЙДЕНО'} | {d} |")
    L += ["", "Примітка: у корпусі всі документи мають sensitivity=public, тому перевірку фільтра за sensitivity виконано на імітації "
              "(в пам'яті один документ тимчасово позначено restricted); дані корпусу не змінювалися.", "",
          "## Приклади: де гібрид виграє / програє відносно dense", ""]
    for tag, lst in (("Виграш", wins[:3]), ("Програш", losses[:1])):
        for r in lst:
            L += [f"### {tag}: {r['lang']} {r['id']} (dense={r['dense'] or '—'}, hybrid={r['hybrid'] or '—'}, bm25={r['bm25'] or '—'})",
                  f"- Запит: {r['question']}", f"- Доказ: {r['evidence']}", "- Пояснення: (допишемо)", ""]
    (ROOT / "docs" / "hybrid_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\nЗаписано docs/hybrid_report.md, eval/hybrid_results.json")
