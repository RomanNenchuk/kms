"""Графіки для звіту (matplotlib, без стилів із мережі)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from . import config as C

COL = {"pop": "#7a7a7a", "content": "#2a7ab0", "graph": "#d9822b", "embed": "#6aa84f", "graph_expo": "#e8b98a", "random": "#cccccc"}


def _bars(ax, res, names, labels, metric, title):
    xs = range(len(names))
    means = [res[n][metric]["mean"] for n in names]
    err = [[res[n][metric]["mean"] - res[n][metric]["lo"] for n in names], [res[n][metric]["hi"] - res[n][metric]["mean"] for n in names]]
    ax.bar(xs, means, yerr=err, color=[COL[n] for n in names], capsize=3)
    ax.set_xticks(list(xs)); ax.set_xticklabels([labels[n] for n in names], rotation=30, ha="right", fontsize=8)
    ax.set_title(title, fontsize=10); ax.grid(axis="y", alpha=.3)


def fig_metrics(out, configs):
    res, names = out["results"], list(configs)
    labels = {n: configs[n][2] for n in names}
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.6))
    _bars(ax[0], res, names, labels, "p5", "precision@5")
    _bars(ax[1], res, names, labels, "ndcg10", "nDCG@10")
    xs = range(len(names)); ax[2].bar(xs, [res[n]["coverage5"]["mean"] for n in names], color=[COL[n] for n in names])
    ax[2].set_xticks(list(xs)); ax[2].set_xticklabels([labels[n] for n in names], rotation=30, ha="right", fontsize=8)
    ax[2].set_title("coverage@5", fontsize=10); ax[2].grid(axis="y", alpha=.3)
    fig.suptitle(f"Порівняння підходів (n={out['protocol']['n_eval_users']} користувачів; 95 % bootstrap CI)", fontsize=10)
    fig.tight_layout(); fig.savefig(C.RESULTS / "fig_metrics.png", dpi=150); plt.close(fig)


def fig_tradeoff(out, configs):
    res = out["results"]; fig, ax = plt.subplots(figsize=(5, 4))
    for n in configs:
        ax.scatter(res[n]["novelty5"]["mean"], res[n]["ndcg10"]["mean"], s=40 + 400 * res[n]["coverage5"]["mean"], color=COL[n], alpha=.8)
        ax.annotate(configs[n][2], (res[n]["novelty5"]["mean"], res[n]["ndcg10"]["mean"]), fontsize=7, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("novelty@5 (більше = менш популярні)"); ax.set_ylabel("nDCG@10"); ax.grid(alpha=.3)
    ax.set_title("Точність vs новизна (розмір точки = coverage@5)", fontsize=9)
    fig.tight_layout(); fig.savefig(C.RESULTS / "fig_tradeoff.png", dpi=150); plt.close(fig)


def fig_cold(out):
    a1, b = out["A1_new_user_simulation"], out["B_new_documents"]
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    names = list(a1["results"]); r = a1["results"]
    x = range(len(names)); w = .38
    ax[0].bar([i - w / 2 for i in x], [r[n]["warm_ndcg10"] for n in names], w, label="з історією", color="#9bbfd9")
    ax[0].bar([i + w / 2 for i in x], [r[n]["ndcg10"]["mean"] for n in names], w, label="історію приховано", color="#d9822b")
    ax[0].set_xticks(list(x)); ax[0].set_xticklabels(names, rotation=30, ha="right", fontsize=7); ax[0].legend(fontsize=8)
    ax[0].set_title(f"A1. Новий користувач: nDCG@10 (n={a1['n_users']})", fontsize=10); ax[0].grid(axis="y", alpha=.3)
    bn = list(b["results"]); ax[1].bar(range(len(bn)), [b["results"][n]["recall_new5"] for n in bn], color="#2a7ab0")
    ax[1].set_xticks(range(len(bn))); ax[1].set_xticklabels(bn, rotation=30, ha="right", fontsize=8)
    ax[1].set_title("B. Новий документ: recall нових@5", fontsize=10); ax[1].grid(axis="y", alpha=.3)
    fig.tight_layout(); fig.savefig(C.RESULTS / "fig_cold_start.png", dpi=150); plt.close(fig)
