"""Результат 5: оцінювання BM25 / dense / hybrid / hybrid+rerank на золотому наборі.
Запуск: python -m src.evaluate     Вихід: docs/search_eval.md, eval/search_eval_results.json

Метрики (лише для запитів з відповіддю; запити без відповіді аналізуються окремо):
 - recall@k  = частка речень-доказів запиту, що потрапили (у складі контексту) в топ-k;
 - MRR       = 1/позиція першого релевантного контексту (релевантний = містить хоч одне речення-доказ);
 - nDCG@10   = бінарна, ідеал = усі релевантні контексти корпусу (не більше 10).
"""
import json, math, re, time
import numpy as np
from .config import ROOT, SEED
from .chunking import load_docs
from .index import VectorIndex
from .hybrid import HybridSearcher, MODES, RRF_K

norm = lambda s: re.sub(r"\s+", "", s).lower()
K = 10
gold = [g for g in map(json.loads, open(ROOT / "eval" / "gold.jsonl", encoding="utf-8")) if g.get("status") == "verified"]
ans = [g for g in gold if g["evidence"]]
una = [g for g in gold if not g["evidence"]]
print(f"Запитів: {len(gold)} (з відповіддю {len(ans)}, без відповіді {len(una)})")

docs = load_docs()
vi = VectorIndex("e5"); vi.build(docs)
hs = HybridSearcher(vi, docs)
hs.search("warm up", "hybrid_rerank")
corpus_ctx = sorted({c["context"] for c in vi.chunks})
corpus_norm = [norm(c) for c in corpus_ctx]

def n_relevant_contexts(g):
    sp = [norm(e) for e in g["evidence"]]
    return sum(any(s in c for s in sp) for c in corpus_norm)

def metrics_for(g, res):
    sp = [norm(e) for e in g["evidence"]]
    cn = [norm(r["context"]) for r in res]
    rec = {k: sum(any(s in c for c in cn[:k]) for s in sp) / len(sp) for k in (5, 10)}
    first = next((i for i, c in enumerate(cn, 1) if any(s in c for s in sp)), None)
    rel = [int(any(s in c for s in sp)) for c in cn[:10]]
    dcg = sum(r / math.log2(i + 1) for i, r in enumerate(rel, 1))
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(max(n_relevant_contexts(g), 1), 10) + 1))
    return {"recall@5": rec[5], "recall@10": rec[10], "rr": 1 / first if first else 0.0, "ndcg@10": dcg / ideal}

def boot(v, n=2000):
    rng = np.random.default_rng(SEED); v = np.asarray(v, float)
    m = [rng.choice(v, len(v)).mean() for _ in range(n)]
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))

per = {m: {} for m in MODES}; lat = {m: [] for m in MODES}; top1_rr = {}
for g in gold:
    for m in MODES:
        t0 = time.perf_counter(); res = hs.search(g["question"], m, k=K); lat[m].append(time.perf_counter() - t0)
        if g["evidence"]:
            per[m][g["id"]] = metrics_for(g, res)
        elif m == "hybrid_rerank":
            top1_rr[g["id"]] = res[0]["rerank_score"] if res else -99.0
    if g["evidence"]:
        pass
ans_top1 = {}
for g in ans:
    res = hs.search(g["question"], "hybrid_rerank", k=K)
    ans_top1[g["id"]] = res[0]["rerank_score"] if res else -99.0

def agg(m, ids):
    rows = [per[m][i] for i in ids]
    out = {k: round(float(np.mean([r[k] for r in rows])), 3) for k in ("recall@5", "recall@10", "rr", "ndcg@10")}
    out["mrr"] = out.pop("rr")
    lo, hi = boot([r["rr"] for r in rows]); out["mrr_ci"] = (round(lo, 2), round(hi, 2))
    lo, hi = boot([r["recall@5"] for r in rows]); out["r5_ci"] = (round(lo, 2), round(hi, 2))
    return out

ids_all = [g["id"] for g in ans]
types = sorted({g["type"] for g in ans})
res_all = {m: agg(m, ids_all) for m in MODES}
res_type = {t: {m: agg(m, [g["id"] for g in ans if g["type"] == t]) for m in MODES} for t in types}
lat_ms = {m: round(1000 * float(np.mean(lat[m])), 1) for m in MODES}
for m in MODES: print(m, res_all[m], f"{lat_ms[m]} мс")

from sklearn.metrics import roc_auc_score
yy = [1] * len(ans_top1) + [0] * len(top1_rr)
auc = roc_auc_score(yy, list(ans_top1.values()) + list(top1_rr.values())) if top1_rr else None
una_stats = {"mean_top1_answerable": round(float(np.mean(list(ans_top1.values()))), 2),
             "mean_top1_unanswerable": round(float(np.mean(list(top1_rr.values()))), 2) if top1_rr else None,
             "auc": round(float(auc), 3) if auc is not None else None}
print("Без відповіді:", una_stats)

kp = ROOT / "eval" / "kappa_results.json"; kap = json.loads(kp.read_text()) if kp.exists() else None
json.dump({"n_answerable": len(ans), "n_unanswerable": len(una), "overall": res_all, "by_type": res_type,
           "latency_ms": lat_ms, "unanswerable": una_stats, "kappa": kap},
          open(ROOT / "eval" / "search_eval_results.json", "w"), indent=2, ensure_ascii=False)

NAMES = {"bm25": "BM25", "dense": "dense (e5, HNSW)", "hybrid": "hybrid (BM25+dense, RRF k=60)", "hybrid_rerank": "hybrid + reranker (топ-30 → топ-5/10)"}
L = ["# Оцінювання пошуку на золотому наборі", "",
     f"Золотий набір: {len(gold)} запитів (`eval/gold.jsonl`): з відповіддю {len(ans)} "
     f"({', '.join(f'{t} {sum(g['type']==t for g in ans)}' for t in types)}), без відповіді {len(una)}. "
     "Релевантним вважається контекст (батьківський розділ), що містить речення-доказ запиту; recall = частка речень-доказів, знайдених у топ-k.", "",
     "## Метрики (запити з відповіддю)", "",
     "| конфігурація | recall@5 [95% ДІ] | recall@10 | MRR [95% ДІ] | nDCG@10 | затримка, мс/запит |", "|---|---|---|---|---|---|"]
for m in MODES:
    r = res_all[m]
    L.append(f"| {NAMES[m]} | {r['recall@5']} {list(r['r5_ci'])} | {r['recall@10']} | {r['mrr']} {list(r['mrr_ci'])} | {r['ndcg@10']} | {lat_ms[m]} |")
L += ["", "ДІ — бутстреп-інтервал по запитах (2000 вибірок, seed 42).", "",
      "## За типами запитів (recall@5 / MRR)", "",
      "| тип (n) | " + " | ".join(NAMES[m].split(' (')[0] for m in MODES) + " |", "|---|" + "---|" * len(MODES)]
for t in types:
    n = sum(g["type"] == t for g in ans)
    L.append(f"| {t} ({n}) | " + " | ".join(f"{res_type[t][m]['recall@5']} / {res_type[t][m]['mrr']}" for m in MODES) + " |")
L += ["", "Примітка: «paraphrase» (20 запитів) використовувалися раніше для вибору chunking і моделі embeddings, тому на них результати можуть бути оптимістичнішими; "
          "«keyword» і «multistep» нові, не використовувалися при виборі.", "",
      "## Запити без відповіді", "",
      f"Для {len(una)} запитів без відповіді recall/MRR не визначені. Середня оцінка reranker для найкращого фрагмента: "
      f"{una_stats['mean_top1_unanswerable']} (без відповіді) проти {una_stats['mean_top1_answerable']} (з відповіддю); "
      f"AUC розрізнення за цією оцінкою = {una_stats['auc']}. Це основа для порога «не знаю» в ЛР 11.", ""]
if kap:
    L += ["## Узгодженість розмітки (κ)", "",
          f"Двоє розмітників: людина (студент) і Gemini; {kap['queries']} запитів, {kap['pairs']} пар «запит + фрагмент» (топ-4 hybrid+rerank). "
          f"Cohen's κ = {kap['kappa']} ({kap['scale']}), збіг {kap['agreement']:.1%}. Матриця (людина/Gemini): {kap['confusion']}. "
          f"Усі {len(kap['disagreements'])} розбіжностей у напрямку «людина 0, Gemini 1»: Gemini частіше зараховує фрагмент, що відповідає лише на частину "
          "двочастинного питання або лише збігається за темою. Для порівняння, κ людини із розміткою за реченнями-доказами "
          f"= {kap['kappa_human_vs_evidence']}, Gemini = {kap['kappa_gemini_vs_evidence']}. "
          "Обмеження: другий розмітник — LLM, тож κ вимірює згоду людини з моделлю, а не двох незалежних експертів.", ""]
L += ["## Висновок", "", "(допишемо після аналізу таблиці)"]
(ROOT / "docs" / "search_eval.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\nЗаписано docs/search_eval.md")
