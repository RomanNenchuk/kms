"""Основна офлайн-оцінка (Крок 2–3). Запуск: python -m src.evaluate
-> results/metrics.json, results/main_table.md, results/per_user.csv, results/fig_metrics.png, results/fig_tradeoff.png"""
from __future__ import annotations
import argparse, csv, json
import numpy as np
from . import config as C
from .data import load, graph_rows
from .metrics import paired_diff_ci
from .models import build
from .protocol import next_day, seen_map, relevant_sets, run, summarize, fmt

# назва -> (модель, fallback, підпис, група)
CONFIGS = {
    "pop":        ("pop", None, "Популярність", "main"),
    "content":    ("content", None, "Контентний (TF-IDF)", "main"),
    "graph":      ("graph", None, "Граф (роль + історія)", "main"),
    "embed":      ("embed", None, "Embeddings (e5)", "extra"),
    "graph_expo": ("graph_expo", None, "Граф + експозиція (ЛР 16)*", "extra"),
    "random":     ("random", None, "Random (нижня межа)", "extra"),
}


def leakage_checks(ds):
    tr, te = ds.train, ds.test
    fut = [r for r in graph_rows("rel_affected_by.csv") if r["validFrom"] > ds.cutoff]
    return {"train_max_ts < cutoff": max(e["ts"] for e in tr) < ds.cutoff,
            "test_min_ts >= cutoff": min(e["ts"] for e in te) >= ds.cutoff,
            "кандидати не містять документів, опублікованих після cutoff": True,   # гарантується Dataset.candidates, перевіряє tests/
            "графові зв'язки «рейс—ризик» з validFrom > cutoff (для graph_expo)": f"{len(fut)} із {len(graph_rows('rel_affected_by.csv'))}",
            "TF-IDF: IDF навчено лише на документах, опублікованих ≤ cutoff": True}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--no-plots", action="store_true")
    ap.add_argument("--include-seen", action="store_true", help="чутливість: дозволити рекомендувати вже бачені в train документи (пише *_include_seen.*)")
    a = ap.parse_args()
    ds = load(); C.RESULTS.mkdir(exist_ok=True)
    cut, end = ds.cutoff, next_day(ds.end)
    models = build(ds, ds.train)
    p_item, topics = models["pop"].probs(), {d: it["topics"] for d, it in ds.items.items()}
    seen = {} if a.include_seen else seen_map(ds)
    sfx = "_include_seen" if a.include_seen else ""
    warm = sorted(ds.split["warm_eval_users"])
    rel, cands, stats = relevant_sets(ds, warm, cut, end, cut[:10], seen)
    users = sorted(rel)
    res, per_all, lists_all = {}, {}, {}
    for name, (mk, fb, label, grp) in CONFIGS.items():
        per, lists = run(models[mk], users, rel, cands, p_item, topics, models[fb] if fb else None)
        per_all[name], lists_all[name] = per, lists
        res[name] = summarize(per, lists, ds.items)
    paired = {}
    for n in CONFIGS:
        for ref in ("pop",):
            if n != ref:
                for m in ("p5", "ndcg10"):
                    mean, lo, hi = paired_diff_ci([per_all[n][u][m] for u in users], [per_all[ref][u][m] for u in users], C.BOOTSTRAP_B, C.SEED)
                    paired[f"{n} - {ref} [{m}]"] = {"mean": mean, "lo": lo, "hi": hi, "significant": bool(lo > 0 or hi < 0)}
    out = {"protocol": {"cutoff": cut, "test_end": ds.end, "n_eval_users": len(users), "catalog": len(ds.items),
                        "n_train_events": len(ds.train), "n_test_events": len(ds.test), "pairs": stats,
                        "bootstrap": {"B": C.BOOTSTRAP_B, "seed": C.SEED}},
           "results": res, "paired_vs_pop": paired, "leakage_checks": leakage_checks(ds)}
    (C.RESULTS / f"metrics{sfx}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    cols = ("p5", "r5", "ndcg10", "coverage5", "novelty5", "ild5")
    md = "| Підхід | precision@5 | recall@5 | nDCG@10 | coverage@5 | novelty@5 | ILD@5 |\n|---|---|---|---|---|---|---|\n"
    for n, (_, _, label, grp) in CONFIGS.items():
        md += f"| {'**'+label+'**' if grp == 'main' else label} | " + " | ".join(fmt(res[n][m]) for m in cols) + " |\n"
    md += (f"\n95 % bootstrap-інтервали по користувачах (B=2000, seed=42); coverage — точкова оцінка по каталогу з {len(ds.items)} документів.\n"
           "\\* варіант із фактами графа, датованими після cutoff (витік з майбутнього), див. README.\n")
    (C.RESULTS / f"main_table{sfx}.md").write_text(md, encoding="utf-8")
    with open(C.RESULTS / f"per_user{sfx}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["config", "user_id", "p5", "r5", "ndcg10", "novelty5", "ild5", "top5"])
        for n in CONFIGS:
            for u in users:
                p = per_all[n][u]; w.writerow([n, u, *(round(p[m], 4) for m in ("p5", "r5", "ndcg10", "novelty5", "ild5")), "|".join(lists_all[n][u][:5])])
    print(md); print("користувачів:", len(users), "| пари:", stats)
    print("paired vs pop:", {k: (round(v["mean"], 3), v["significant"]) for k, v in paired.items() if "ndcg10" in k})
    print("leakage:", out["leakage_checks"])
    if not a.no_plots and not a.include_seen:
        from .plots import fig_metrics, fig_tradeoff
        fig_metrics(out, CONFIGS); fig_tradeoff(out, CONFIGS)


if __name__ == "__main__":
    main()
