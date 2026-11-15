#!/usr/bin/env python3
"""Рисунки для whitepaper із реальних результатів ЛР 10, 15, 16 (числа з docs/*.md та reports/*.json відповідних ЛР).
Палітра: перші 4 слоти reference palette (перевірено validate_palette.js), фіксований порядок. Запуск: python scripts/wp_figures.py"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

COL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
plt.rcParams["font.family"] = "DejaVu Sans"


def style(ax):
    ax.set_facecolor(SURF); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID); ax.tick_params(colors=MUTED, length=0, labelsize=8)


def retrieval():  # ЛР 10: 33 запити з відповіддю (docs/search_eval.md)
    cfg = ["BM25", "dense (e5)", "hybrid (RRF)", "hybrid + reranker"]
    data = {"recall@5": [0.864, 0.924, 0.939, 0.924], "MRR": [0.839, 0.889, 0.893, 0.939], "nDCG@10": [0.865, 0.881, 0.896, 0.914]}
    fig, ax = plt.subplots(figsize=(7.2, 3.1), facecolor=SURF); style(ax)
    w = 0.2
    for i, c in enumerate(cfg):
        xs = [j + (i - 1.5) * w for j in range(3)]
        vals = [data[m][i] for m in data]
        ax.bar(xs, vals, width=w - 0.02, color=COL[i], edgecolor=SURF, linewidth=2, label=c)
        for x, v in zip(xs, vals): ax.text(x, v + 0.008, f"{v:.2f}", ha="center", fontsize=6.5, color=INK)
    ax.set_xticks(range(3)); ax.set_xticklabels(list(data), color=INK, fontsize=9)
    ax.set_ylim(0.7, 1.0); ax.set_ylabel("значення метрики", color=MUTED, fontsize=8)
    ax.legend(ncol=4, fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.16))
    fig.tight_layout(); fig.savefig("reports/fig_wp_retrieval.png", dpi=200, facecolor=SURF)


def agent():  # ЛР 15: tests/agent_summary_*.json, attacks_summary_*.json
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 3.0), facecolor=SURF, gridspec_kw={"width_ratios": [1, 1.5]})
    style(a)
    for i, (lab, v, c) in enumerate([("system_v1\n(до)", 75.0, COL[0]), ("system_v2\n(після)", 100.0, COL[2])]):
        a.bar(i, v, width=0.55, color=c, edgecolor=SURF, linewidth=2); a.text(i, v + 2, f"{v:.0f}%\n({int(v * .12)}/12)", ha="center", fontsize=8, color=INK)
    a.set_xticks([0, 1]); a.set_xticklabels(["system_v1\n(до)", "system_v2\n(після)"], color=INK, fontsize=8)
    a.set_ylim(0, 125); a.set_yticks([0, 25, 50, 75, 100]); a.set_title("Успішність сценаріїв агента", fontsize=9, color=INK)
    style(b)
    types = ["data_leak", "loop", "malicious_\ntool_desc.", "direct_inj.", "indirect_inj.", "write_attempt"]
    off = [2, 1, 1, 0, 0, 0]; on = [0] * 6
    for j in range(6):
        b.bar(j - 0.19, off[j], width=0.34, color=COL[1], edgecolor=SURF, linewidth=2, label="без захисту" if j == 0 else None)
        b.bar(j + 0.19, on[j] + 0.02, width=0.34, color=COL[2], edgecolor=SURF, linewidth=2, label="із захистом" if j == 0 else None)
        b.text(j - 0.19, off[j] + 0.06, f"{off[j]}/2", ha="center", fontsize=7, color=INK); b.text(j + 0.19, 0.09, "0/2", ha="center", fontsize=7, color=INK)
    b.set_xticks(range(6)); b.set_xticklabels(types, fontsize=6.5, color=INK); b.set_ylim(0, 2.6); b.set_yticks([0, 1, 2])
    b.set_title("Успішні атаки (з 2 на тип; 4/12 → 0/12)", fontsize=9, color=INK); b.legend(fontsize=7, frameon=False)
    fig.tight_layout(); fig.savefig("reports/fig_wp_agent.png", dpi=200, facecolor=SURF)


def arch():
    fig, ax = plt.subplots(figsize=(7.8, 4.3), facecolor=SURF); ax.set_xlim(0, 100); ax.set_ylim(0, 54); ax.axis("off")

    def box(x, y, w, h, t, fc="#ffffff", ec=MUTED, fs=6.4, bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.2", fc=fc, ec=ec, lw=1))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, color=INK, fontweight="bold" if bold else "normal")

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", color=MUTED, lw=1))
    box(2, 40, 22, 11, "Користувач\n(UI Streamlit :8501)", "#eef4fc", COL[0], bold=True)
    box(32, 40, 28, 11, "FastAPI :8000\n/recommend · /ask\n/graph · /cypher", "#eef4fc", COL[0], bold=True)
    box(68, 40, 30, 11, "Guards: рівень доступу,\nprompt injection,\nread-only Cypher", "#fdf0ea", COL[1], bold=True)
    arrow(24, 45.5, 32, 45.5); arrow(60, 45.5, 68, 45.5)
    box(2, 22, 29, 15, "Рекомендації\npop · граф · embeddings · гібрид\nфільтри: verified,\nсвіжість, права", "#ffffff")
    box(35, 22, 29, 15, "Пояснення\nшлях у графі → шаблон UA\n→ Gemini лише перефразує\n→ автоперевірка", "#ffffff")
    box(68, 22, 30, 15, "Питання до бази знань\nпошук → уривок + цитата\nабо «не знаю» / відмова", "#ffffff")
    for x in (16, 49, 83): arrow(x, 40, x, 37.4)
    box(2, 4, 29, 12, "Neo4j 5 (граф)\n673 вузли · 2592 зв'язки\n+ 64 корист. · 526 OPENED", "#eaf7f1", COL[2])
    box(35, 4, 29, 12, "База знань: 36 статей,\n2383 фрагменти\n(e5 / BM25)", "#eaf7f1", COL[2])
    box(68, 4, 30, 12, "DuckDB-куб (5000 рейсів)\nsemantic/metrics.yml\nCSV взаємодій (синтетичні)", "#eaf7f1", COL[2])
    ax.text(50, 18.6, "джерела даних: рекомендації й пояснення читають граф і взаємодії; питання — базу знань; метрики — куб", ha="center", fontsize=6.2, color=MUTED, style="italic")
    ax.text(50, 0.3, "Docker Compose: neo4j → loader (одноразово) → api → ui", ha="center", fontsize=7, color=MUTED)
    fig.savefig("reports/fig_wp_arch.png", dpi=200, facecolor=SURF, bbox_inches="tight")


if __name__ == "__main__":
    retrieval(); agent(); arch(); print("ok")
