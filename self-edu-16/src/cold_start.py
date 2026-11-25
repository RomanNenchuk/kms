"""Холодний старт з числами (Крок 3). Запуск: python -m src.cold_start -> results/cold_start.json, cold_start.md, fig_cold_start.png

A1 новий користувач, симуляція: кожен «теплий» оцінюваний користувач u «забуває» історію — усі його події train
   вилучено з навчання ВСІХ моделей (включно з популярністю). Кандидати й релевантні ті самі, що в основній оцінці,
   тож різниця з «теплим» результатом — це чиста втрата якості через відсутність історії.
A2 реальні нові користувачі: 8 осіб, що приєдналися після cutoff (історії в train немає). Дуже мала вибірка.
B  новий документ: 4 документи, опубліковані після cutoff, без жодних взаємодій у train. as_of = кінець test.
Підходи без історії (content, embed) повертають порожній список — «сирий» результат; у продакшні для них потрібен
fallback. Тут перевіряємо три: популярність, role_pop (популярність серед тієї ж ролі), граф за роллю (+ авіакомпанією)."""
from __future__ import annotations
import json
import numpy as np
from . import config as C
from .data import load
from .metrics import precision_at_k, recall_at_k, ndcg_at_k, bootstrap_ci, paired_diff_ci
from .models import build, rank
from .protocol import next_day, seen_map, relevant_sets, run, summarize, fmt

# назва -> (модель, назва fallback)
A_CFG = {"pop": ("pop", None), "role_pop": ("role_pop", None), "content": ("content", None),
         "content+pop": ("content", "pop"), "embed": ("embed", None), "graph (роль)": ("graph", None),
         "graph+expo (роль+авіакомпанія)": ("graph_expo", None)}


def scenario_a1(ds):
    cut, end = ds.cutoff, next_day(ds.end)
    warm = sorted(ds.split["warm_eval_users"]); seen = seen_map(ds)
    rel, cands, _ = relevant_sets(ds, warm, cut, end, cut[:10], seen)
    users = sorted(rel)
    full = build(ds, ds.train)
    p_item, topics = full["pop"].probs(), {d: it["topics"] for d, it in ds.items.items()}
    warm_per = {n: run(full[mk], users, rel, cands, p_item, topics, full[fb] if fb else None)[0] for n, (mk, fb) in A_CFG.items()}
    cold_per, cold_lists = {n: {} for n in A_CFG}, {n: {} for n in A_CFG}
    for u in users:
        m = build(ds, [e for e in ds.train if e["user_id"] != u])          # перенавчання без історії u
        for n, (mk, fb) in A_CFG.items():
            per, lists = run(m[mk], [u], rel, cands, p_item, topics, m[fb] if fb else None)
            cold_per[n][u], cold_lists[n][u] = per[u], lists[u]
    res = {n: summarize(cold_per[n], cold_lists[n], ds.items) for n in A_CFG}
    for n in A_CFG:
        w = float(np.mean([warm_per[n][u]["ndcg10"] for u in users])); c = res[n]["ndcg10"]["mean"]
        res[n]["warm_ndcg10"] = w; res[n]["loss_ndcg10_pct"] = (100 * (w - c) / w) if w else 0.0
        res[n]["warm_p5"] = float(np.mean([warm_per[n][u]["p5"] for u in users]))
    paired = {}
    for n in A_CFG:
        if n != "pop":
            for m_ in ("p5", "ndcg10"):
                mean, lo, hi = paired_diff_ci([cold_per[n][u][m_] for u in users], [cold_per["pop"][u][m_] for u in users], C.BOOTSTRAP_B, C.SEED)
                paired[f"{n} - pop [{m_}]"] = {"mean": mean, "lo": lo, "hi": hi, "significant": bool(lo > 0 or hi < 0)}
    return {"n_users": len(users), "results": res, "paired_vs_pop": paired}


def scenario_a2(ds):
    cut, end = ds.cutoff, next_day(ds.end)
    cold = sorted(ds.split["cold_users"]); m = build(ds, ds.train)
    p_item, topics = m["pop"].probs(), {d: it["topics"] for d, it in ds.items.items()}
    rel, cands, stats = relevant_sets(ds, cold, cut, end, cut[:10], {})
    users = sorted(rel); out = {}
    for n, (mk, fb) in A_CFG.items():
        per, lists = run(m[mk], users, rel, cands, p_item, topics, m[fb] if fb else None)
        out[n] = summarize(per, lists, ds.items) if users else {}
    return {"n_cold_users_total": len(cold), "n_users": len(users), "pairs": stats, "results": out}


def scenario_b(ds):
    cut, end, as_of = ds.cutoff, next_day(ds.end), ds.end[:10]
    new = set(ds.split["new_items"]); warm = sorted(ds.split["warm_eval_users"]); seen = seen_map(ds)
    m = build(ds, ds.train)
    rel, cands, _ = relevant_sets(ds, warm, cut, end, as_of, seen)
    cfg = {"pop": "pop", "content": "content", "embed": "embed", "graph (теми)": "graph", "random": "random"}
    out = {}
    for n, mk in cfg.items():
        hits = tot = exposed = 0; p5 = []
        for u in warm:
            top = rank(m[mk], u, cands[u], 5)
            rel_new = rel.get(u, set()) & new
            hits += len(set(top) & rel_new); tot += len(rel_new); exposed += bool(set(top) & new)
            if u in rel: p5.append(precision_at_k(top, rel[u], 5))
        out[n] = {"recall_new5": hits / tot if tot else 0.0, "relevant_new_pairs": tot, "exposure5": exposed / len(warm), "p5_all": float(np.mean(p5))}
    return {"new_items": sorted(new), "n_users": len(warm), "results": out}


def main():
    ds = load(); C.RESULTS.mkdir(exist_ok=True)
    out = {"A1_new_user_simulation": scenario_a1(ds), "A2_real_new_users": scenario_a2(ds), "B_new_documents": scenario_b(ds)}
    (C.RESULTS / "cold_start.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    a1, a2, b = out["A1_new_user_simulation"], out["A2_real_new_users"], out["B_new_documents"]
    md = [f"### A1. Новий користувач — симуляція (n={a1['n_users']}, історію приховано)",
          "| Підхід | precision@5 | nDCG@10 | coverage@5 | порожніх списків | nDCG@10 з історією | втрата nDCG |", "|---|---|---|---|---|---|---|"]
    for n, r in a1["results"].items():
        md.append(f"| {n} | {fmt(r['p5'])} | {fmt(r['ndcg10'])} | {r['coverage5']['mean']:.3f} | {r['empty_rate']['mean']:.0%} | {r['warm_ndcg10']:.3f} | {r['loss_ndcg10_pct']:.0f} % |")
    md += ["", "Парна різниця з популярністю (A1): " + "; ".join(f"{k}: {v['mean']:+.3f} [{v['lo']:+.3f}; {v['hi']:+.3f}]" for k, v in a1["paired_vs_pop"].items() if "ndcg10" in k)]
    md += ["", f"### A2. Реальні нові користувачі (з {a2['n_cold_users_total']} у вибірці релевантні в test є у {a2['n_users']}; пар: {a2['pairs']['relevant_pairs']})",
           "| Підхід | precision@5 | nDCG@10 |", "|---|---|---|"]
    for n, r in a2["results"].items():
        if r: md.append(f"| {n} | {fmt(r['p5'])} | {fmt(r['ndcg10'])} |")
    md += ["", f"### B. Нові документи ({', '.join(b['new_items'])}; n користувачів={b['n_users']})",
           "| Підхід | recall нових@5 | пар релевантних нових | exposure@5 | precision@5 (усі) |", "|---|---|---|---|---|"]
    for n, r in b["results"].items():
        md.append(f"| {n} | {r['recall_new5']:.3f} | {r['relevant_new_pairs']} | {r['exposure5']:.3f} | {r['p5_all']:.3f} |")
    (C.RESULTS / "cold_start.md").write_text("\n".join(md) + "\n", encoding="utf-8"); print("\n".join(md))
    from .plots import fig_cold
    fig_cold(out)


if __name__ == "__main__":
    main()
