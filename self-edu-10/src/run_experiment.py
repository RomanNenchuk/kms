#!/usr/bin/env python3
"""СР10. Експеримент з embeddings на корпусі й золотій розмітці з ЛР 10.

Метрики: recall@5, MRR, затримка запиту, розмір індексу, вплив мови (EN / UK запити до англійського корпусу).

    python src/run_experiment.py                  # усі enabled-моделі з models.json
    python src/run_experiment.py --with-baseline  # + лексичний baseline (char n-gram hashing)
    python src/run_experiment.py --dry-run        # лише baseline, без завантаження моделей (перевірка пайплайна)
    python src/run_experiment.py --download-only  # лише завантажити моделі в кеш
"""
from __future__ import annotations

import argparse, csv, json, os, platform, statistics, sys, time, zlib
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA, RES = ROOT / "data", ROOT / "results"

# сценарій: поле з текстом запиту (корпус завжди англійський)
SCENARIOS = {"en->en": "en", "en_para->en": "en_para", "uk->en": "uk"}
MAIN = "en->en"


# ---------------------------------------------------------------- embedders
class HashingEmbedder:
    """Лексичний baseline без моделі: хешовані символьні 3-5-грами. Також для --dry-run."""
    key, hf_id, dim, n_params, max_seq = "hashing-baseline", "char n-gram hashing (без моделі)", 4096, 0, None

    def encode(self, texts, kind="doc"):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            t = f" {t.lower()} "
            for n in (3, 4, 5):
                for j in range(len(t) - n + 1):
                    out[i, zlib.crc32(t[j:j + n].encode()) % self.dim] += 1
        return np.log1p(out)

    def count_tokens(self, texts):
        return sum(len(t.split()) for t in texts)

    def truncated_share(self, texts):
        return 0.0


class STEmbedder:
    def __init__(self, cfg):
        from sentence_transformers import SentenceTransformer
        self.key, self.hf_id = cfg["key"], cfg["hf_id"]
        self.qp, self.dp = cfg.get("query_prefix", ""), cfg.get("doc_prefix", "")
        self.model = SentenceTransformer(self.hf_id, device="cpu")
        if cfg.get("max_seq_length"):
            self.model.max_seq_length = cfg["max_seq_length"]
        self.max_seq = self.model.max_seq_length
        self.dim = self.model.get_sentence_embedding_dimension()
        self.n_params = sum(p.numel() for p in self.model.parameters())

    def encode(self, texts, kind="doc"):
        p = self.qp if kind == "query" else self.dp
        # нормалізацію робимо самі, щоб порівняти cosine з «сирим» dot product
        return self.model.encode([p + t for t in texts], batch_size=32, convert_to_numpy=True,
                                 normalize_embeddings=False, show_progress_bar=False).astype(np.float32)

    def _lens(self, texts):
        tok = self.model.tokenizer
        return [len(x) for x in tok([self.dp + t for t in texts], add_special_tokens=True)["input_ids"]]

    def count_tokens(self, texts):
        return sum(self._lens(texts))

    def truncated_share(self, texts):
        """Частка фрагментів, довших за max_seq_length (їх «хвіст» модель не бачить)."""
        return sum(n > self.max_seq for n in self._lens(texts)) / len(texts)


# ---------------------------------------------------------------- метрики
def l2(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-12)


def evaluate(scores, queries, id2idx, k=5):
    """recall@k = частка речень-доказів, чий фрагмент є в top-k (як у ЛР 10); MRR — за першим релевантним фрагментом."""
    rec, rr, per_q = [], [], []
    for i, q in enumerate(queries):
        order = np.argsort(-scores[i])
        pos = np.empty(len(order), dtype=int)
        pos[order] = np.arange(1, len(order) + 1)          # ранг кожного фрагмента
        best = [min(pos[id2idx[c]] for c in ev) for ev in q["relevant_chunks"]]  # ранг кращого фрагмента для кожного доказу
        rec.append(np.mean([b <= k for b in best]))
        first = min(best)
        rr.append(1.0 / first)
        per_q.append({"qid": q["id"], "type": q["type"], "rank": int(first), "ranks_each": [int(b) for b in best],
                      "top": [int(j) for j in order[:5]]})
    return float(np.mean(rec)), float(np.mean(rr)), per_q


def load_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def md_table(header, rows):
    s = "| " + " | ".join(header) + " |\n|" + "|".join("---" for _ in header) + "|\n"
    return s + "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows) + "\n"


# ---------------------------------------------------------------- один прогін моделі
def run_model(emb, corpus, queries, reps, k):
    texts = [d["text"] for d in corpus]
    id2idx = {d["id"]: i for i, d in enumerate(corpus)}
    emb.encode(texts[:2], "doc")  # прогрів
    t0 = time.perf_counter()
    D = emb.encode(texts, "doc")
    build_s = time.perf_counter() - t0
    Dn = l2(D)

    Q = {f: emb.encode([q[f] for q in queries], "query") for f in SCENARIOS.values()}

    # затримка одного запиту (batch=1): кодування + точний пошук (brute force) окремо
    for q in queries[:5]:
        Dn @ l2(emb.encode([q["en"]], "query"))[0]
    t_enc, t_srch = [], []
    for _ in range(reps):
        for q in queries:
            t = time.perf_counter(); v = l2(emb.encode([q["en"]], "query")); t1 = time.perf_counter()
            s = Dn @ v[0]; np.argpartition(-s, k)[:k]; t2 = time.perf_counter()
            t_enc.append((t1 - t) * 1000); t_srch.append((t2 - t1) * 1000)
    tot = sorted(a + b for a, b in zip(t_enc, t_srch))

    RES.joinpath("index").mkdir(exist_ok=True, parents=True)
    npy = RES / "index" / f"{emb.key}.npy"
    np.save(npy, D)

    info = {
        "model": emb.key, "hf_id": emb.hf_id, "dim": emb.dim, "params_M": round(emb.n_params / 1e6, 1),
        "max_seq": emb.max_seq, "truncated_share": round(emb.truncated_share(texts), 3),
        "enc_ms": round(statistics.median(t_enc), 1), "search_ms": round(statistics.median(t_srch), 3),
        "lat_median_ms": round(statistics.median(tot), 1), "lat_p95_ms": round(tot[int(0.95 * (len(tot) - 1))], 1),
        "index_build_s": round(build_s, 2), "index_MB": round(os.path.getsize(npy) / 1e6, 2),
        "GB_per_1M_chunks": round(emb.dim * 4 / 1000, 2), "corpus_tokens": emb.count_tokens(texts),
        "raw_norm_mean": round(float(np.linalg.norm(D, axis=1).mean()), 3),
    }

    rows, perq = [], []
    for name, field in SCENARIOS.items():
        r5, mrr, pq = evaluate(l2(Q[field]) @ Dn.T, queries, id2idx, k)
        row = {**info, "scenario": name, f"recall@{k}": round(r5, 3), "MRR": round(mrr, 3)}
        if name == MAIN:  # абляція нормалізації
            a, b, _ = evaluate(Q[field] @ D.T, queries, id2idx, k)
            row[f"recall@{k}_no_norm"], row["MRR_no_norm"] = round(a, 3), round(b, 3)
        rows.append(row)
        perq += [{"model": emb.key, "scenario": name, **p} for p in pq]
    return rows, perq


# ---------------------------------------------------------------- розбіжності
def disagreements(perq, models, corpus, queries, scenario, n):
    by = {}
    for p in perq:
        if p["scenario"] == scenario:
            by.setdefault(p["qid"], {})[p["model"]] = p
    qmap = {q["id"]: q for q in queries}
    field = SCENARIOS[scenario]
    scored = []
    for qid, m in by.items():
        ranks = [m[x]["rank"] for x in models]
        scored.append((min(ranks) <= 5 < max(ranks), max(ranks) - min(ranks), qid))
    scored.sort(reverse=True)
    pick = [s for s in scored if s[1] > 0][:n]
    out = [f"# Розбіжності моделей (сценарій `{scenario}`)\n",
           f"Відібрано {len(pick)} запитів: спершу ті, де одна модель має золотий фрагмент у top-5, а інша ні; далі за розкидом рангів. "
           f"Ранг — позиція першого релевантного фрагмента серед {len(corpus)}.\n"]
    for i, (_, _, qid) in enumerate(pick, 1):
        q = qmap[qid]
        out.append(f"\n## {i}. {qid} ({q['type']}): {q[field]}\n")
        out.append(f"Доказ: _{q['evidence'][0][:200]}_ — {q['doc_ids'][0]}\n\n")
        rows = []
        for m in models:
            p = by[qid][m]
            top = "; ".join(f"{corpus[j]['title']} › {corpus[j]['section']}" for j in p["top"][:3])
            rows.append([m, p["rank"], "✓" if p["rank"] <= 5 else "✗", top])
        out.append(md_table(["модель", "ранг золотого", "top-5", "top-3 знайдено"], rows))
        out.append("\n**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_\n")
    return "\n".join(out)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="ключі з models.json через кому (за замовчуванням — усі enabled)")
    ap.add_argument("--with-baseline", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--download-only", action="store_true")
    ap.add_argument("--latency-reps", type=int, default=3)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--n-disagreements", type=int, default=8)
    a = ap.parse_args()

    corpus, queries = load_jsonl(DATA / "corpus.jsonl"), load_jsonl(DATA / "queries.jsonl")
    assert len(queries) >= 30, "потрібно ≥ 30 запитів"
    cfgs = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
    want = a.models.split(",") if a.models else [c["key"] for c in cfgs if c.get("enabled", True)]

    embs = []
    if a.dry_run:
        embs.append(HashingEmbedder())
    else:
        for c in cfgs:
            if c["key"] in want:
                print(f"[load] {c['hf_id']}", flush=True)
                embs.append(STEmbedder(c))
        if a.with_baseline:
            embs.append(HashingEmbedder())
    if a.download_only:
        print("Моделі завантажено в кеш.")
        return
    if not a.dry_run and sum(e.key != "hashing-baseline" for e in embs) < 3:
        print("УВАГА: для критерію C1 потрібно ≥ 3 моделі (зараз менше).", file=sys.stderr)

    RES.mkdir(exist_ok=True)
    rows, perq = [], []
    for e in embs:
        print(f"[run] {e.key}", flush=True)
        r, p = run_model(e, corpus, queries, a.latency_reps, a.k)
        rows += r
        perq += p

    k = a.k
    cols = ["model", "scenario", f"recall@{k}", "MRR", f"recall@{k}_no_norm", "MRR_no_norm", "dim", "params_M", "max_seq", "truncated_share",
            "enc_ms", "search_ms", "lat_median_ms", "lat_p95_ms", "index_build_s", "index_MB", "GB_per_1M_chunks", "corpus_tokens", "raw_norm_mean", "hf_id"]
    with open(RES / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    with open(RES / "per_query.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "scenario", "qid", "type", "rank_of_gold", "top5_chunk_ids"])
        for p in perq:
            w.writerow([p["model"], p["scenario"], p["qid"], p["type"], p["rank"], " ".join(corpus[j]["id"] for j in p["top"])])

    n_docs = len({d["doc_id"] for d in corpus})
    md = [f"# Результати СР10 ({datetime.now():%Y-%m-%d %H:%M})\n",
          f"Корпус: {len(corpus)} фрагментів із {n_docs} статей англійської Вікіпедії (з ЛР 10); запитів: {len(queries)} із золотою розміткою "
          f"(речення-доказ → фрагмент); k={k}; точний пошук (brute-force cosine), CPU.\n"]
    main_rows = [r for r in rows if r["scenario"] == MAIN]
    md.append(f"\n## 1. Основна таблиця: якість і вартість (запити EN, сценарій `{MAIN}`)\n")
    md.append(md_table(["Модель", "dim", "парам., M", f"recall@{k}", "MRR", "кодув. запиту, мс", "пошук, мс", "разом p95, мс", "побудова індексу, с", "індекс, МБ", "ГБ / 1 млн фрагм."],
                       [[r["model"], r["dim"], r["params_M"], r[f"recall@{k}"], r["MRR"], r["enc_ms"], r["search_ms"], r["lat_p95_ms"],
                         r["index_build_s"], r["index_MB"], r["GB_per_1M_chunks"]] for r in main_rows]))
    md.append(f"\n## 2. Вплив мови та перефразування (recall@{k} / MRR)\n")
    names = list(SCENARIOS)
    md.append(md_table(["Модель"] + names, [[e.key] + [f"{x[f'recall@{k}']} / {x['MRR']}" for n in names for x in rows if x["model"] == e.key and x["scenario"] == n] for e in embs]))
    md.append("\n`en_para->en` — перефразовані запити (стійкість); `uk->en` — українські запити до англійського корпусу (крос-мовний пошук).\n")
    md.append(f"\n## 3. За типами запитів (recall@{k} / MRR)\n")
    types = sorted({q["type"] for q in queries})
    for sc in (MAIN, "uk->en"):
        md.append(f"\nСценарій `{sc}`:\n\n")
        trows = []
        for e in embs:
            cells = []
            for t in types:
                pq = [p for p in perq if p["model"] == e.key and p["scenario"] == sc and p["type"] == t]
                rec = np.mean([np.mean([r <= k for r in p["ranks_each"]]) for p in pq])
                cells.append(f"{rec:.2f} / {np.mean([1 / p['rank'] for p in pq]):.2f}")
            trows.append([e.key] + cells)
        md.append(md_table(["Модель"] + [f"{t} ({sum(q['type'] == t for q in queries)})" for t in types], trows))
    md.append(f"\n## 4. Обрізання фрагментів та нормалізація\n")
    md.append(md_table(["Модель", "max_seq_length", "частка фрагментів довших за ліміт", f"recall@{k} cosine", f"recall@{k} dot (без норм.)", "MRR cosine", "MRR dot", "сер. норма сирих векторів"],
                       [[r["model"], r["max_seq"], r["truncated_share"], r[f"recall@{k}"], r[f"recall@{k}_no_norm"], r["MRR"], r["MRR_no_norm"], r["raw_norm_mean"]] for r in main_rows]))
    (RES / "results.md").write_text("\n".join(md), encoding="utf-8")

    keys = [e.key for e in embs]
    for sc in (MAIN, "uk->en"):
        (RES / f"disagreements_{sc.replace('->', '-')}.md").write_text(disagreements(perq, keys, corpus, queries, sc, a.n_disagreements), encoding="utf-8")

    meta = {"date": datetime.now().isoformat(timespec="seconds"), "python": platform.python_version(), "platform": platform.platform(),
            "cpu": platform.processor() or platform.machine(), "cpu_count": os.cpu_count()}
    try:
        import torch, sentence_transformers
        meta.update(torch=torch.__version__, sentence_transformers=sentence_transformers.__version__, torch_threads=torch.get_num_threads())
    except Exception:
        pass
    (RES / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "\n".join(md))
    print(f"\nФайли у {RES}/: results.md, disagreements_*.md, summary.csv, per_query.csv, run_meta.json")


if __name__ == "__main__":
    main()
