"""Етичні ризики з числами (Крок 4). Запуск: python -m src.ethics -> results/ethics.json, ethics.md
R1 упередженість до популярного (popularity bias / довгий хвіст), R2 «бульбашка» тем + захід MMR,
R3 приватність і доступ (витік за рівнем доступу, k-анонімність атрибутів), R4 нерівність якості між ролями."""
from __future__ import annotations
import json
from collections import Counter, defaultdict
import numpy as np
from . import config as C
from .data import load
from .metrics import gini, jaccard, ild, ndcg_at_k, precision_at_k, coverage, bootstrap_ci, paired_diff_ci
from .models import build, rank
from .protocol import next_day, seen_map, relevant_sets, run, summarize

APPROACHES = {"pop": "Популярність", "content": "Контентний (TF-IDF)", "graph": "Граф (роль + історія)", "embed": "Embeddings (e5)"}


def mmr(model, user, cands, topics, lam, k=10):
    s = model.score(user)
    pool = [d for d in cands if d in s]
    if not pool: return []
    lo, hi = min(s[d] for d in pool), max(s[d] for d in pool)
    norm = {d: (s[d] - lo) / (hi - lo) if hi > lo else 0.0 for d in pool}
    chosen = []
    while pool and len(chosen) < k:
        best = max(pool, key=lambda d: (lam * norm[d] - (1 - lam) * max((jaccard(topics[d], topics[c]) for c in chosen), default=0.0)))
        chosen.append(best); pool.remove(best)
    return chosen


def user_topics(ds, train):
    t = defaultdict(set)
    for u, docs in ds.positives(train).items():
        for d in docs: t[u] |= set(ds.items[d]["topics"])
    return t


def main():
    ds = load(); cut, end = ds.cutoff, next_day(ds.end)
    m = build(ds, ds.train); seen = seen_map(ds)
    p_item, topics = m["pop"].probs(), {d: it["topics"] for d, it in ds.items.items()}
    rel, cands, _ = relevant_sets(ds, sorted(ds.split["warm_eval_users"]), cut, end, cut[:10], seen)
    users = sorted(rel); out = {}
    runs = {n: run(m[n], users, rel, cands, p_item, topics) for n in APPROACHES}

    # R1: упередженість до популярного
    top_pop = {d for d, _ in sorted(m["pop"].cnt.items(), key=lambda x: (-x[1], x[0]))[:round(0.2 * len(ds.items))]}
    gt_share = float(np.mean([d in top_pop for u in users for d in rel[u]]))
    r1 = {"top20pct_docs": sorted(top_pop), "share_of_relevant_pairs_on_top20pct": gt_share}
    for n in APPROACHES:
        lists = runs[n][1]; exp = Counter(d for u in users for d in lists[u][:5])
        flat = [d for u in users for d in lists[u][:5]]
        r1[n] = {"gini_exposure": gini([exp.get(d, 0) for d in ds.items]), "share_top20pct": float(np.mean([d in top_pop for d in flat])),
                 "docs_never_recommended": sum(1 for d in ds.items if exp.get(d, 0) == 0)}
    out["R1_popularity_bias"] = r1

    # R2: бульбашка тем + MMR
    ut = user_topics(ds, ds.train); r2 = {}
    def bubble(lists):
        nov = [np.mean([bool(set(topics[d]) - ut[u]) for d in lists[u][:5]]) for u in users if lists[u]]
        return float(np.mean(nov)) if nov else 0.0
    for n in APPROACHES:
        r2[n] = {"ild5": float(np.mean([runs[n][0][u]["ild5"] for u in users])), "topic_novelty_rate": bubble(runs[n][1])}
    base_per, base_lists = runs["graph"]
    mm = {}
    for lam in (1.0, C.MMR_LAMBDA, 0.5):
        lists = {u: mmr(m["graph"], u, cands[u], topics, lam) for u in users}
        per = {u: {"p5": precision_at_k(lists[u], rel[u], 5), "ndcg10": ndcg_at_k(lists[u], rel[u], 10), "ild5": ild(lists[u], topics, 5)} for u in users}
        d_nd = paired_diff_ci([per[u]["ndcg10"] for u in users], [base_per[u]["ndcg10"] for u in users], C.BOOTSTRAP_B, C.SEED)
        d_il = paired_diff_ci([per[u]["ild5"] for u in users], [base_per[u]["ild5"] for u in users], C.BOOTSTRAP_B, C.SEED)
        mm[str(lam)] = {"p5": float(np.mean([per[u]["p5"] for u in users])), "ndcg10": float(np.mean([per[u]["ndcg10"] for u in users])),
                        "ild5": float(np.mean([per[u]["ild5"] for u in users])), "coverage5": coverage(list(lists.values()), ds.items, 5),
                        "topic_novelty_rate": bubble(lists), "delta_ndcg10": dict(zip(("mean", "lo", "hi"), d_nd)), "delta_ild5": dict(zip(("mean", "lo", "hi"), d_il))}
    r2["mmr_on_graph"] = mm; out["R2_filter_bubble"] = r2

    # R3: приватність і доступ
    r3 = {}
    rel_na, cands_na, _ = relevant_sets(ds, users, cut, end, cut[:10], seen, respect_access=False)
    for n in APPROACHES:
        viol = []
        for u in users:
            top = rank(m[n], u, cands_na[u], 5)
            viol.append(any(C.ACCESS_RANK[ds.items[d]["sensitivity"]] > C.ACCESS_RANK[ds.users[u]["access_level"]] for d in top))
        r3[n] = {"users_with_access_violation_no_filter": float(np.mean(viol)), "with_filter": 0.0}
    for key in (("role", "airline"), ("role", "airline", "home_airport")):
        c = Counter(tuple(u[k] for k in key) for u in ds.users.values())
        r3["k_anonymity_" + "+".join(key)] = {"groups": len(c), "min_group": min(c.values()),
                                              "users_unique": sum(1 for u in ds.users.values() if c[tuple(u[k] for k in key)] == 1) / len(ds.users)}
    out["R3_privacy_access"] = r3

    # R4: якість за ролями
    r4 = {}
    for n in ("pop", "graph"):
        by = defaultdict(lambda: defaultdict(list))
        for u in users:
            for k in ("p5", "ndcg10"): by[ds.users[u]["role"]][k].append(runs[n][0][u][k])
        r4[n] = {role: {"n": len(v["p5"]), "p5": float(np.mean(v["p5"])), "ndcg10": float(np.mean(v["ndcg10"]))} for role, v in sorted(by.items())}
        nd = [v["ndcg10"] for v in r4[n].values()]; r4[n]["gap_ndcg10_max_min"] = max(nd) - min(nd)
    out["R4_role_fairness"] = r4

    (C.RESULTS / "ethics.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["### R1. Упередженість до популярного",
          f"Частка релевантних пар на 20 % найпопулярніших документів: {gt_share:.2f}",
          "| Підхід | Gini експозиції | частка рекомендацій з top-20 % | документів ніколи не рекомендовано |", "|---|---|---|---|"]
    md += [f"| {l} | {r1[n]['gini_exposure']:.3f} | {r1[n]['share_top20pct']:.2f} | {r1[n]['docs_never_recommended']} з {len(ds.items)} |" for n, l in APPROACHES.items()]
    md += ["", "### R2. «Бульбашка» тем", "| Підхід | ILD@5 | частка рекомендацій із новою для користувача темою |", "|---|---|---|"]
    md += [f"| {l} | {r2[n]['ild5']:.3f} | {r2[n]['topic_novelty_rate']:.2f} |" for n, l in APPROACHES.items()]
    md += ["", f"Захід: MMR-переранжування графа (λ — вага релевантності; 1.0 = без заходу)",
           "| λ | precision@5 | nDCG@10 (Δ, 95 % CI) | ILD@5 (Δ, 95 % CI) | coverage@5 | нова тема |", "|---|---|---|---|---|---|"]
    md += [f"| {lam} | {v['p5']:.3f} | {v['ndcg10']:.3f} ({v['delta_ndcg10']['mean']:+.3f} [{v['delta_ndcg10']['lo']:+.3f}; {v['delta_ndcg10']['hi']:+.3f}]) | "
           f"{v['ild5']:.3f} ({v['delta_ild5']['mean']:+.3f} [{v['delta_ild5']['lo']:+.3f}; {v['delta_ild5']['hi']:+.3f}]) | {v['coverage5']:.3f} | {v['topic_novelty_rate']:.2f} |" for lam, v in mm.items()]
    md += ["", "### R3. Приватність і доступ", "| Підхід | користувачів із документом вище їхнього рівня доступу (без фільтра) | з фільтром |", "|---|---|---|"]
    md += [f"| {l} | {r3[n]['users_with_access_violation_no_filter']:.2f} | 0.00 |" for n, l in APPROACHES.items()]
    for k, v in r3.items():
        if k.startswith("k_anon"): md.append(f"\n{k}: груп {v['groups']}, мінімальна група {v['min_group']}, унікальних користувачів {v['users_unique']:.0%}")
    md += ["", "### R4. Якість за ролями (nDCG@10; n — кількість оцінюваних користувачів ролі)", "| Роль | n | Популярність | Граф |", "|---|---|---|---|"]
    for role in r4["pop"]:
        if role != "gap_ndcg10_max_min": md.append(f"| {role} | {r4['pop'][role]['n']} | {r4['pop'][role]['ndcg10']:.3f} | {r4['graph'][role]['ndcg10']:.3f} |")
    md.append(f"| розрив max−min | | {r4['pop']['gap_ndcg10_max_min']:.3f} | {r4['graph']['gap_ndcg10_max_min']:.3f} |")
    (C.RESULTS / "ethics.md").write_text("\n".join(md) + "\n", encoding="utf-8"); print("\n".join(md))


if __name__ == "__main__":
    main()
