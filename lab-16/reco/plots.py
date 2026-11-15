"""Графіки Результату 2 (палітра: перші 6 слотів reference palette, перевірені validate_palette.js; фіксований порядок)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from . import config as C

COL = {"pop": "#2a78d6", "graph": "#eb6834", "embed": "#1baf7a", "hybrid_default": "#eda100", "graph_tuned": "#e87ba4", "hybrid_tuned": "#008300"}
LABEL = {"pop": "Популярність", "graph": "Граф", "embed": "Embeddings", "hybrid_default": "Гібрид (за замовч.)",
         "graph_tuned": "Граф (підібр.)", "hybrid_tuned": "Гібрид (підібр.)"}
OFFSET = {"pop": (8, 6), "embed": (8, 6), "graph": (-10, -4), "graph_tuned": (-10, 8), "hybrid_default": (-10, 6), "hybrid_tuned": (10, -14)}
INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"


def _style(ax):
    ax.set_facecolor(SURF); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID); ax.tick_params(colors=MUTED, length=0)


def make_plots(out):
    res = out["results"]; names = list(res)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), facecolor=SURF)
    for ax, (m, title) in zip(axes, [("p5", "precision@5"), ("ndcg10", "nDCG@10"), ("r5", "recall@5")]):
        _style(ax)
        for i, n in enumerate(names):
            r = res[n][m]
            ax.bar(i, r["mean"], width=0.62, color=COL[n], edgecolor=SURF, linewidth=2)
            ax.errorbar(i, r["mean"], yerr=[[r["mean"] - r["lo"]], [r["hi"] - r["mean"]]], color=INK, capsize=3, lw=1.2)
            ax.text(i, r["hi"] + 0.01, f"{r['mean']:.2f}", ha="center", va="bottom", fontsize=8, color=INK)
        ax.set_xticks(range(len(names))); ax.set_xticklabels([LABEL[n].replace(" (", "\n(") for n in names], fontsize=7.5, color=MUTED)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
    fig.suptitle(f"Офлайн-оцінка на test (n={out['protocol']['n_eval_users']} користувачів; штрихи — 95 % bootstrap-інтервал)", x=0.01, ha="left", fontsize=10, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.94)); fig.savefig(C.ROOT / "reports" / "fig_accuracy.png", dpi=160, facecolor=SURF); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.4), facecolor=SURF); _style(ax); ax.grid(axis="x", color=GRID, lw=0.8)
    for n in names:
        c, nv = res[n]["coverage5"], res[n]["novelty5"]
        ax.errorbar(c["mean"], nv["mean"], yerr=[[nv["mean"] - nv["lo"]], [nv["hi"] - nv["mean"]]],
                    fmt="o", ms=9, color=COL[n], mec=SURF, mew=2, ecolor=COL[n], elinewidth=1, alpha=0.95)
        ax.annotate(LABEL[n], (c["mean"], nv["mean"]), textcoords="offset points", xytext=OFFSET[n], fontsize=8, color=INK,
                    ha="right" if OFFSET[n][0] < 0 else "left")
    ax.set_xlim(0.38, 0.75)
    ax.set_xlabel("coverage@5 (частка каталогу)", color=MUTED, fontsize=9); ax.set_ylabel("novelty@5 (біт)", color=MUTED, fontsize=9)
    ax.set_title("Різноманітність і новизна", loc="left", fontsize=11, color=INK)
    fig.tight_layout(); fig.savefig(C.ROOT / "reports" / "fig_diversity.png", dpi=160, facecolor=SURF); plt.close(fig)


def make_cold_plot(out):
    """Холодний старт: ліворуч — новий користувач (nDCG@10), праворуч — новий документ (recall нових@5 і exposure@5)."""
    sim = out["new_user"]["simulation"]["results"]; nd = out["new_doc"]
    cols = {"pop": "#2a78d6", "role_only": "#eb6834", "airline_only": "#1baf7a", "role+airline": "#eda100", "hybrid": "#008300",
            "embed": "#1baf7a", "graph": "#eb6834", "hybrid+слот": "#e87ba4"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.2), facecolor=SURF)
    _style(a1)
    for i, (n, r) in enumerate(sim.items()):
        m = r["ndcg10"]; a1.bar(i, m["mean"], 0.62, color=cols[n], edgecolor=SURF, linewidth=2)
        a1.errorbar(i, m["mean"], yerr=[[m["mean"] - m["lo"]], [m["hi"] - m["mean"]]], color=INK, capsize=3, lw=1.2)
        a1.text(i, m["hi"] + 0.01, f"{m['mean']:.2f}", ha="center", fontsize=8, color=INK)
    a1.set_xticks(range(len(sim))); a1.set_xticklabels(list(sim), fontsize=8, color=MUTED)
    a1.set_title(f"Новий користувач: nDCG@10 (n={out['new_user']['simulation']['n_users']})", loc="left", fontsize=11, color=INK)
    _style(a2); w = 0.38
    for i, (n, r) in enumerate(nd.items()):
        a2.bar(i - w / 2, r["new_doc_recall5"], w, color=cols[n], edgecolor=SURF, linewidth=2)
        a2.bar(i + w / 2, r["exposure5"], w, color=cols[n], edgecolor=SURF, linewidth=2, alpha=0.45, hatch="//")
        a2.text(i - w / 2, r["new_doc_recall5"] + 0.01, f"{r['new_doc_recall5']:.2f}", ha="center", fontsize=8, color=INK)
        a2.text(i + w / 2, r["exposure5"] + 0.01, f"{r['exposure5']:.2f}", ha="center", fontsize=8, color=INK)
    a2.set_xticks(range(len(nd))); a2.set_xticklabels(list(nd), fontsize=8, color=MUTED)
    a2.set_title("Новий документ: recall нових@5 (суцільний), exposure@5 (штрих)", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(C.ROOT / "reports" / "fig_cold_start.png", dpi=160, facecolor=SURF); plt.close(fig)
