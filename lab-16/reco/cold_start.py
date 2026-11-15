"""Холодний старт (Результат 3). Запуск: python -m reco.cold_start -> reports/cold_start_results.json, cold_start_table.md, fig_cold_start.png

Сценарій A «новий користувач» (історії немає):
  A1 симуляція: кожен «теплий» користувач з test вдає нового — його події train ВИДАЛЕНО з навчання (n≈47);
  A2 реальні нові користувачі: 8 осіб, що приєдналися після cutoff (мало подій, дуже широкі інтервали).
  Сигнали, доступні без історії: роль (граф), авіакомпанія (шляхи через рейси і ризики), популярність.
Сценарій B «новий документ» (взаємодій немає): 4 документи, опубліковані після cutoff. Сигнали: теми (граф), вектор тексту (embeddings).
  Додатково: «слот для нового» — зарезервована позиція в top-k для найкращого нового документа."""
from __future__ import annotations
import dataclasses, json
import numpy as np
from . import config as C
from .data import load
from .eval import make_rec, _next_day
from .filters import apply_filters
from .metrics import precision_at_k, recall_at_k, ndcg_at_k, bootstrap_ci, paired_diff_ci
from .recommender import Recommender


def tuned_params():
    p = C.ROOT / "reports" / "eval_results.json"
    if not p.exists():
        return C.GraphParams(), C.HybridParams()
    t = json.loads(p.read_text(encoding="utf-8"))["tuned"]
    return C.GraphParams(**t["graph"]), C.HybridParams(**t["hybrid"])


def positives_in(ds, users, start, end):
    pos = {}
    for e in ds.events:
        if start <= e["ts"] < end and e["event"] in C.POSITIVE_EVENTS and e["user_id"] in users:
            pos.setdefault(e["user_id"], set()).add(e["doc_id"])
    return pos


def eligible(rec, u, docs, as_of):
    cands, _ = apply_filters(rec.ds.users[u], sorted(rec.ds.items), rec.ds, as_of, rec.fp, rec.seen.get(u, set()))
    return docs & set(cands)


def user_metrics(recs, rel):
    return {"p5": precision_at_k(recs, rel, 5), "r5": recall_at_k(recs, rel, 5), "ndcg10": ndcg_at_k(recs, rel, 10)}


def summarize(per_cfg):
    out = {}
    for name, per in per_cfg.items():
        us = sorted(per)
        out[name] = {m: dict(zip(("mean", "lo", "hi"), bootstrap_ci([per[u][m] for u in us]))) for m in ("p5", "r5", "ndcg10")}
    return out


def scenario_new_user(ds, graph, hybrid):
    cut, end = ds.cutoff, _next_day(ds.end)
    cfgs = {"pop": ("pop", C.GraphParams(), None),
            "role_only": ("graph", dataclasses.replace(graph, beta=0.0, gamma=0.0), None),
            "airline_only": ("graph", dataclasses.replace(graph, alpha=0.0, gamma=0.0), None),
            "role+airline": ("graph", dataclasses.replace(graph, gamma=0.0), None),
            "hybrid": ("hybrid", dataclasses.replace(graph, gamma=0.0), hybrid)}
    warm = set(ds.split["warm_eval_users"]); pos = positives_in(ds, warm, cut, end)
    sim = {n: {} for n in cfgs}
    for u in sorted(warm):
        ds_u = dataclasses.replace(ds, events=[e for e in ds.events if not (e["user_id"] == u and e["ts"] < cut)])
        for n, (method, g, h) in cfgs.items():
            rec = Recommender(ds_u, g, C.FilterParams(), h)
            rel = eligible(rec, u, pos.get(u, set()), cut[:10])
            if not rel: continue
            recs = [i["doc_id"] for i in rec.recommend(u, 10, method, as_of=cut[:10], explain=False)["items"]]
            sim[n][u] = user_metrics(recs, rel)
    users = sorted(set.intersection(*[set(v) for v in sim.values()])); sim = {n: {u: v[u] for u in users} for n, v in sim.items()}
    # A2: реальні нові користувачі
    cold = ds.split["cold_users"]; real = {n: {} for n in cfgs}
    for n, (method, g, h) in cfgs.items():
        rec = Recommender(ds, g, C.FilterParams(), h)
        for u in cold:
            j = ds.users[u]["joined_at"]
            rel = eligible(rec, u, positives_in(ds, {u}, j, end).get(u, set()), j)
            if rel:
                recs = [i["doc_id"] for i in rec.recommend(u, 10, method, as_of=j, explain=False)["items"]]
                real[n][u] = user_metrics(recs, rel)
    ru = sorted(set.intersection(*[set(v) for v in real.values()])); real = {n: {u: v[u] for u in ru} for n, v in real.items()}
    paired = {}
    for n in cfgs:
        if n != "pop":
            for m in ("p5", "ndcg10"):
                paired[f"{n} - pop [{m}]"] = dict(zip(("mean", "lo", "hi"), paired_diff_ci([sim[n][u][m] for u in users], [sim["pop"][u][m] for u in users])))
    return {"simulation": {"n_users": len(users), "results": summarize(sim), "paired": paired},
            "real_cold_users": {"n_users": len(ru), "results": summarize(real) if ru else {}}}


def top_k_with_new_slot(rec, u, k, method, as_of, new_ids, slots):
    full = [i["doc_id"] for i in rec.recommend(u, 36, method, as_of=as_of, explain=False)["items"]]
    base = full[:k - slots]
    extra = [d for d in full if d in new_ids and d not in base][:slots]
    fill = [d for d in full if d not in base and d not in extra]
    return (base + extra + fill)[:k]


def scenario_new_doc(ds, graph, hybrid):
    cut, end, as_of = ds.cutoff, _next_day(ds.end), ds.end[:10]
    new = set(ds.split["new_items"]); users = sorted(ds.split["warm_eval_users"])
    cfgs = {"pop": ("pop", None, None, 0), "embed": ("embed", None, None, 0), "graph": ("graph", graph, None, 0),
            "hybrid": ("hybrid", graph, hybrid, 0), "hybrid+слот": ("hybrid", graph, hybrid, 1)}
    pos = positives_in(ds, set(users), cut, end); res = {}
    rec_cache = {n: Recommender(dataclasses.replace(ds), g, C.FilterParams(), h) for n, (_, g, h, _) in cfgs.items()}
    for n, (method, g, h, slots) in cfgs.items():
        rec, hits, tot, exposed, p5 = rec_cache[n], 0, 0, 0, []
        for u in users:
            top = top_k_with_new_slot(rec, u, 5, method, as_of, new, slots) if slots else \
                [i["doc_id"] for i in rec.recommend(u, 5, method, as_of=as_of, explain=False)["items"]]
            rel_new = eligible(rec, u, {d for d in pos.get(u, set()) if d in new}, as_of)
            hits += len(set(top) & rel_new); tot += len(rel_new); exposed += bool(set(top) & new)
            rel_all = eligible(rec, u, pos.get(u, set()), as_of)
            if rel_all: p5.append(precision_at_k(top, rel_all, 5))
        res[n] = {"new_doc_recall5": hits / tot if tot else 0.0, "new_doc_relevant_pairs": tot,
                  "exposure5": exposed / len(users), "p5_all_docs": float(np.mean(p5)), "p5_users": len(p5)}
    return res


def main():
    ds = load(); graph, hybrid = tuned_params()
    out = {"params": {"graph": dataclasses.asdict(graph), "hybrid": dataclasses.asdict(hybrid)},
           "new_user": scenario_new_user(ds, graph, hybrid), "new_doc": scenario_new_doc(ds, graph, hybrid)}
    (C.ROOT / "reports" / "cold_start_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    f = lambda r: f"{r['mean']:.3f} [{r['lo']:.3f}; {r['hi']:.3f}]"
    md = ["### Новий користувач (A1: симуляція, n=%d)" % out["new_user"]["simulation"]["n_users"],
          "| Підхід | precision@5 | recall@5 | nDCG@10 |", "|---|---|---|---|"]
    for n, r in out["new_user"]["simulation"]["results"].items(): md.append(f"| {n} | {f(r['p5'])} | {f(r['r5'])} | {f(r['ndcg10'])} |")
    md += ["", "### Новий користувач (A2: реальні нові, n=%d)" % out["new_user"]["real_cold_users"]["n_users"], "| Підхід | precision@5 | recall@5 | nDCG@10 |", "|---|---|---|---|"]
    for n, r in out["new_user"]["real_cold_users"]["results"].items(): md.append(f"| {n} | {f(r['p5'])} | {f(r['r5'])} | {f(r['ndcg10'])} |")
    md += ["", "### Новий документ (B)", "| Підхід | recall нових@5 | exposure@5 | precision@5 (усі) |", "|---|---|---|---|"]
    for n, r in out["new_doc"].items(): md.append(f"| {n} | {r['new_doc_recall5']:.3f} (пар: {r['new_doc_relevant_pairs']}) | {r['exposure5']:.3f} | {r['p5_all_docs']:.3f} |")
    (C.ROOT / "reports" / "cold_start_table.md").write_text("\n".join(md) + "\n", encoding="utf-8"); print("\n".join(md))
    print("paired vs pop:", {k: (round(v['mean'], 3), round(v['lo'], 3), round(v['hi'], 3)) for k, v in out["new_user"]["simulation"]["paired"].items()})
    from .plots import make_cold_plot
    make_cold_plot(out)


if __name__ == "__main__":
    main()
