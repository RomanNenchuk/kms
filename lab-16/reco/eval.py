"""Офлайн-оцінка (Результат 2). Запуск: python -m reco.eval  ->  reports/eval_results.json, reports/eval_table.md, reports/*.png

Протокол (див. docs/reco_eval.md):
  * часове розбиття: train = ts < cutoff; test = ts >= cutoff; моделі бачать лише train;
  * рекомендації формуються «на момент cutoff» (as_of = cutoff): документи, опубліковані пізніше, недоступні;
  * релевантні = позитивні події (open/save/helpful) користувача у test на документах, які система МОГЛА показати
    (пройшли фільтри й не були бачені в train) — однакові кандидати для всіх конфігурацій;
  * гіперпараметри підбираються на валідаційному вікні [val_cutoff, cutoff) ВСЕРЕДИНІ train, test не використовується;
  * невизначеність: bootstrap по користувачах (2000 повторів, seed=42) + парний bootstrap різниць."""
from __future__ import annotations
import argparse, dataclasses, datetime as dt, itertools, json, math
from collections import Counter
import numpy as np
from . import config as C
from .data import load
from .filters import apply_filters
from .metrics import precision_at_k, recall_at_k, ndcg_at_k, novelty_at_k, coverage, bootstrap_ci, paired_diff_ci
from .recommender import Recommender

VAL_CUTOFF = "2026-10-12"           # валідація: fit на ts < 10-12, оцінка на [10-12, 10-26)
REPORTS = C.ROOT / "reports"


def _next_day(d: str) -> str:
    return (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()


def make_rec(ds, cutoff, graph=None, hybrid=None):
    return Recommender(dataclasses.replace(ds, cutoff=cutoff), graph, C.FilterParams(), hybrid)


def item_probs(rec):
    cnt = rec.models["pop"].cnt
    tot = sum(cnt.values()) + len(rec.ds.items)
    return {d: (cnt.get(d, 0.0) + 1.0) / tot for d in rec.ds.items}


def ground_truth(rec, start, end):
    """user -> (релевантні кандидати, статистика втрат) для вікна [start, end)."""
    ds, as_of = rec.ds, start[:10]
    pos = {}
    for e in ds.events:
        if start <= e["ts"] < end and e["event"] in C.POSITIVE_EVENTS:
            pos.setdefault(e["user_id"], set()).add(e["doc_id"])
    out, lost = {}, Counter()
    for u, docs in pos.items():
        if u not in rec.seen:                 # немає історії в train -> холодний старт, оцінюється окремо (Р3)
            lost["cold_user_pairs"] += len(docs)
            continue
        cands, dropped = apply_filters(ds.users[u], sorted(ds.items), ds, as_of, rec.fp, rec.seen[u])
        rel = {d for d in docs if d in set(cands)}
        for d in docs - rel:
            lost[dropped[d]] += 1
        lost["eligible_pairs"] += len(rel)
        if rel:
            out[u] = rel
    return out, dict(lost)


def evaluate(rec, config, start, end, k=5):
    """config: {"method": ..}. Повертає per-user метрики та списки рекомендацій."""
    gt, lost = ground_truth(rec, start, end)
    p_item, per_user, lists = item_probs(rec), {}, {}
    for u in sorted(gt):
        recs = [i["doc_id"] for i in rec.recommend(u, 10, config["method"], as_of=start[:10], explain=False)["items"]]
        rel = gt[u]
        per_user[u] = {"p5": precision_at_k(recs, rel, 5), "r5": recall_at_k(recs, rel, 5),
                       "ndcg10": ndcg_at_k(recs, rel, 10), "novelty5": novelty_at_k(recs, p_item, 5)}
        lists[u] = recs
    return per_user, lists, lost, gt


def tune(ds, seed_print=True):
    """Підбір на валідації (train-only): спочатку α,β,γ графа, потім злиття гібрида. Метрика — nDCG@10."""
    main_cut = ds.cutoff
    def score(graph, hybrid, method):
        rec = make_rec(ds, VAL_CUTOFF, graph, hybrid)
        pu, *_ = evaluate(rec, {"method": method}, VAL_CUTOFF, main_cut)
        return float(np.mean([v["ndcg10"] for v in pu.values()])), len(pu)
    grid_g = [C.GraphParams(a, b, g) for a, b, g in itertools.product([0.5, 1.0, 2.0], repeat=3)]
    gres = sorted(((score(g, None, "graph")[0], g) for g in grid_g), key=lambda x: (-x[0], dataclasses.astuple(x[1])))
    best_g = gres[0][1]
    grid_h = [C.HybridParams(m, {"graph": 1.0, "embed": we, "pop": wp}) for m in ("rrf", "weighted")
              for we in (0.0, 0.25, 0.5, 1.0) for wp in (0.0, 0.25, 0.5, 1.0)]
    hres = sorted(((score(best_g, h, "hybrid")[0], h) for h in grid_h), key=lambda x: (-x[0], x[1].method, str(x[1].weights)))
    best_h = hres[0][1]
    default = score(None, None, "hybrid")[0]
    n_val = score(best_g, best_h, "hybrid")[1]
    return {"graph": best_g, "hybrid": best_h, "val_ndcg_graph": gres[0][0], "val_ndcg_hybrid": hres[0][0],
            "val_ndcg_hybrid_default": default, "n_val_users": n_val,
            "graph_grid_top5": [(round(s, 4), dataclasses.asdict(g)) for s, g in gres[:5]],
            "hybrid_grid_top5": [(round(s, 4), dataclasses.asdict(h)) for s, h in hres[:5]]}


def leakage_checks(ds, rec, tuned_window_end):
    tr, te = ds.train, ds.test
    checks = {
        "train_max_ts < cutoff": max(e["ts"] for e in tr) < ds.cutoff,
        "test_min_ts >= cutoff": min(e["ts"] for e in te) >= ds.cutoff,
        "tuning window ends at/before cutoff": tuned_window_end <= ds.cutoff,
        "рекомендації не містять бачених у train": all(
            not rec.seen[u] & {i["doc_id"] for i in rec.recommend(u, 36, "hybrid", as_of=ds.cutoff[:10], explain=False)["items"]}
            for u in list(rec.seen)[:20]),
        "жоден документ у видачі не опублікований після as_of": all(
            ds.items[i["doc_id"]]["published_at"] <= ds.cutoff[:10]
            for u in list(rec.seen)[:20] for i in rec.recommend(u, 36, "hybrid", as_of=ds.cutoff[:10], explain=False)["items"]),
        "популярність/профілі враховують лише train": all(e["ts"] < ds.cutoff for e in tr),
    }
    return checks


CONFIGS = ["pop", "graph", "embed", "hybrid_default", "graph_tuned", "hybrid_tuned"]
LABEL = {"pop": "Популярність", "graph": "Граф", "embed": "Embeddings", "hybrid_default": "Гібрид (за замовч.)",
         "graph_tuned": "Граф (підібр.)", "hybrid_tuned": "Гібрид (підібр.)"}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--no-plots", action="store_true"); a = ap.parse_args()
    ds = load(); cut, end = ds.cutoff, _next_day(ds.end)
    tuned = tune(ds)
    spec = {"pop": ("pop", None, None), "graph": ("graph", None, None), "embed": ("embed", None, None),
            "hybrid_default": ("hybrid", None, None), "graph_tuned": ("graph", tuned["graph"], None),
            "hybrid_tuned": ("hybrid", tuned["graph"], tuned["hybrid"])}
    res, lists, per = {}, {}, {}
    for name in CONFIGS:
        method, g, h = spec[name]
        rec = make_rec(ds, cut, g, h)
        pu, ls, lost, gt = evaluate(rec, {"method": method}, cut, end)
        per[name], lists[name] = pu, ls
        users = sorted(pu)
        row = {}
        for m in ("p5", "r5", "ndcg10", "novelty5"):
            mean, lo, hi = bootstrap_ci([pu[u][m] for u in users])
            row[m] = {"mean": mean, "lo": lo, "hi": hi}
        # coverage — точкова оцінка: bootstrap по користувачах для неї односторонній (ресемпл не охоплює більше, ніж вибірка)
        row["coverage5"] = {"mean": coverage([ls[u] for u in users], ds.items)}
        res[name] = row
    users = sorted(per["pop"]); assert all(sorted(per[n]) == users for n in CONFIGS)
    paired = {}
    for n in CONFIGS:
        for ref in ("pop", "hybrid_tuned"):
            if n == ref: continue
            for m in ("p5", "ndcg10"):
                mean, lo, hi = paired_diff_ci([per[n][u][m] for u in users], [per[ref][u][m] for u in users])
                paired[f"{n} - {ref} [{m}]"] = {"mean": mean, "lo": lo, "hi": hi, "significant": lo > 0 or hi < 0}
    rec_main = make_rec(ds, cut)
    _, lost_stats = ground_truth(rec_main, cut, end)
    out = {"protocol": {"cutoff": cut, "test_end": ds.end, "val_cutoff": VAL_CUTOFF, "n_eval_users": len(users),
                        "catalog": len(ds.items), "bootstrap": {"B": 2000, "seed": 42}},
           "test_pairs": lost_stats, "tuned": {k: (dataclasses.asdict(v) if dataclasses.is_dataclass(v) else v) for k, v in tuned.items()},
           "results": res, "paired": paired, "leakage_checks": leakage_checks(ds, rec_main, cut)}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "eval_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    hdr = "| Конфігурація | precision@5 | recall@5 | nDCG@10 | coverage@5 | novelty@5 |\n|---|---|---|---|---|---|\n"
    fmt = lambda r: f"{r['mean']:.3f} [{r['lo']:.3f}; {r['hi']:.3f}]" if "lo" in r else f"{r['mean']:.3f}"
    rows = "".join(f"| {LABEL[n]} | " + " | ".join(fmt(res[n][m]) for m in ("p5", "r5", "ndcg10", "coverage5", "novelty5")) + " |\n" for n in CONFIGS)
    (REPORTS / "eval_table.md").write_text(hdr + rows, encoding="utf-8")
    print(hdr + rows); print("\nusers:", len(users), "| втрати/статистика пар:", lost_stats)
    print("tuned graph:", tuned["graph"], "| hybrid:", tuned["hybrid"], "| val nDCG:", round(tuned["val_ndcg_hybrid_default"], 3), "->", round(tuned["val_ndcg_hybrid"], 3))
    print("leakage:", out["leakage_checks"])
    if not a.no_plots:
        from .plots import make_plots
        make_plots(out)


if __name__ == "__main__":
    main()
