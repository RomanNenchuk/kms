"""Дашборд і тренд. Запуск: python -m src.dashboard
-> results/dashboard.html (відкрити у браузері, без мережі), fig_trend.png, fig_scenarios.png, tables.md
Дані: results/measurements/*.json (останній замір стану) і results/history.jsonl (усі різні заміри для тренду)."""
from __future__ import annotations
import html, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from . import measure as M

RES, SC_ORDER = M.RES, ("chat", "audit")
LABEL = {"baseline": "baseline-v2 (до очищення)", "clean": "clean (після очищення)", "lab11": "lab11 (еталон)"}


def load():
    cfg = M.load_cfg()
    cur = {v: json.load(open(RES / "measurements" / f"{v}.json", encoding="utf-8")) for v in ("baseline", "clean", "lab11")}
    hist = [h for h in M.read_history() if h["variant"] in ("baseline", "clean")]
    hist.sort(key=lambda h: (h["measured"], 0 if h["variant"] == "baseline" else 1))
    return cfg, cur, hist


def series(hist, mid):
    return [(f"{LABEL[h['variant']].split(' ')[0]}\n{h['measured'][5:19].replace('T', ' ')}", h["values"][mid]) for h in hist]


def fig_trend(cfg, cur, hist):
    fig, axes = plt.subplots(2, 4, figsize=(13, 5.6)); ref = cur["lab11"]
    for ax, m in zip(axes.flat, cfg["metrics"]):
        s = series(hist, m["id"]); xs = list(range(len(s)))
        ax.plot(xs, [v for _, v in s], "o-", color="#2a7ab0", lw=2, label="замір")
        refv = next(x["value"] for x in ref["metrics"] if x["id"] == m["id"])
        ax.axhline(refv, color="#6aa84f", ls=":", lw=1.5, label="еталон lab11")
        ax.axhline(m["thresholds"]["chat"], color="#d9822b", ls="--", lw=1, label="поріг чат")
        ax.axhline(m["thresholds"]["audit"], color="#c0392b", ls="--", lw=1, label="поріг аудит")
        ax.set_xticks(xs); ax.set_xticklabels([x for x, _ in s], fontsize=7); ax.set_xlim(-0.4, len(s) - 0.6)
        vals = [v for _, v in s] + [refv, m["thresholds"]["chat"], m["thresholds"]["audit"]]
        lo, hi = min(vals), max(vals); pad = max((hi - lo) * 0.12, 0.001); ax.set_ylim(lo - pad, hi + pad)
        ax.set_title(f"{m['id']} · {m['dimension']}", fontsize=9); ax.grid(alpha=.3); ax.tick_params(axis="y", labelsize=7)
    h, l = axes.flat[0].get_legend_handles_labels(); fig.legend(h, l, loc="lower center", ncol=4, fontsize=8)
    fig.suptitle("Тренд метрик якості: заміри за часом (порівняно з порогами й еталоном)", fontsize=11)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96)); fig.savefig(RES / "fig_trend.png", dpi=150); plt.close(fig)


def fig_scenarios(cfg, cur):
    cols = [(v, s) for s in SC_ORDER for v in ("baseline", "clean")]
    fig, ax = plt.subplots(figsize=(8.5, 4.2)); mids = [m["id"] for m in cfg["metrics"]]
    for j, (v, s) in enumerate(cols):
        for i, mid in enumerate(mids):
            m = next(x for x in cur[v]["metrics"] if x["id"] == mid); ok = m["status"][s] == "ok"
            ax.add_patch(plt.Rectangle((j, i), 1, 1, color="#cfe8cf" if ok else "#f2c6c2", ec="white"))
            ax.text(j + .5, i + .5, f"{m['value']:.4f}", ha="center", va="center", fontsize=8)
    ax.set_xlim(0, len(cols)); ax.set_ylim(len(mids), 0)
    ax.set_xticks([j + .5 for j in range(len(cols))]); ax.set_xticklabels([f"{LABEL[v].split(' ')[0]}\n{cfg['scenarios'][s]['name'].split(' (')[0]}" for v, s in cols], fontsize=8)
    ax.set_yticks([i + .5 for i in range(len(mids))]); ax.set_yticklabels([f"{m['id']} {m['dimension']}" for m in cfg["metrics"]], fontsize=8)
    ax.set_title("Пройдено (зелений) / не пройдено (червоний) за порогами сценаріїв", fontsize=10)
    for sp in ax.spines.values(): sp.set_visible(False)
    fig.tight_layout(); fig.savefig(RES / "fig_scenarios.png", dpi=150); plt.close(fig)


def svg_trend(cfg, cur, hist, m):
    s = series(hist, m["id"]); W, H, L, R, T, B = 250, 120, 36, 10, 10, 26
    refv = next(x["value"] for x in cur["lab11"]["metrics"] if x["id"] == m["id"])
    vals = [v for _, v in s] + [refv, m["thresholds"]["chat"], m["thresholds"]["audit"]]
    lo, hi = min(vals), max(vals); pad = max((hi - lo) * 0.12, 0.001); lo, hi = lo - pad, hi + pad
    y = lambda v: T + (H - T - B) * (1 - (v - lo) / (hi - lo)); x = lambda i: L + (W - L - R) * ((i + .5) / len(s))
    o = [f'<svg viewBox="0 0 {W} {H}" class="sp">']
    for v, c, d in ((refv, "#6aa84f", "2 2"), (m["thresholds"]["chat"], "#d9822b", "5 3"), (m["thresholds"]["audit"], "#c0392b", "5 3")):
        o.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{c}" stroke-dasharray="{d}"/>')
    o.append('<polyline fill="none" stroke="#2a7ab0" stroke-width="2" points="' + " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(s)) + '"/>')
    for i, (lab, v) in enumerate(s):
        o.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.5" fill="#2a7ab0"/><text x="{x(i):.1f}" y="{H - 12}" text-anchor="middle" font-size="8">{html.escape(lab.split(chr(10))[0])}</text>'
                 f'<text x="{x(i):.1f}" y="{y(v) - 6:.1f}" text-anchor="middle" font-size="8">{v:.3f}</text>')
    o.append("</svg>"); return "".join(o)


def build_html(cfg, cur, hist):
    sc = cfg["scenarios"]; rows = []
    for m in cfg["metrics"]:
        b = next(x for x in cur["baseline"]["metrics"] if x["id"] == m["id"]); c = next(x for x in cur["clean"]["metrics"] if x["id"] == m["id"])
        r = next(x for x in cur["lab11"]["metrics"] if x["id"] == m["id"])
        cells = "".join(f'<td class="num">{x["value"]:.4f}' + "".join(f'<span class="chip {s} {x["status"][s]}">{"✓" if x["status"][s] == "ok" else "✗"}</span>' for s in SC_ORDER) + "</td>" for x in (b, c, r))
        th = "".join(f'<span class="sc {s}">≥ {m["thresholds"][s]}</span>' for s in SC_ORDER)
        rows.append(f'<tr><td><b>{m["id"]}</b></td><td>{m["dimension"]}</td><td>{html.escape(m["name"])}</td><td class="num">{th}</td>{cells}<td class="num">{c["value"] - b["value"]:+.4f}</td></tr>')
    cards = "".join(
        f'<div class="card"><div class="t">{LABEL[v]}</div>' + "".join(f'<div class="k sc {s}">{html.escape(sc[s]["name"].split(" (")[0])}: <b>{cur[v]["summary"][s]["ok"]}/8</b></div>' for s in SC_ORDER)
        + f'<div class="d">{cur[v]["measured"][:16].replace("T", " ")}</div></div>' for v in ("baseline", "clean", "lab11"))
    spark = "".join(f'<div class="cell"><div class="h">{m["id"]} · {m["dimension"]}</div>{svg_trend(cfg, cur, hist, m)}</div>' for m in cfg["metrics"])
    pts = len(hist)
    legend = "".join(f'<li><b>{html.escape(sc[s]["name"])}</b>: {html.escape(sc[s]["use"])}</li>' for s in SC_ORDER)
    return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8"><title>Метрики якості знань — дашборд</title><style>
body{{font:14px/1.45 "Times New Roman",serif;margin:24px;color:#000;max-width:1180px}} h1{{font-size:20px}} h2{{font-size:16px;margin-top:22px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap}} .card{{border:1px solid #888;padding:8px 12px;min-width:210px}} .card .t{{font-weight:bold}} .card .d{{color:#555;font-size:12px}}
table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #888;padding:4px 7px;vertical-align:top}} th{{background:#f2f2f2}} .num{{text-align:center;white-space:nowrap}}
.chip{{margin-left:6px;padding:0 5px;border-radius:3px;font-size:12px}} .chip.ok{{background:#cfe8cf}} .chip.fail{{background:#f2c6c2}}
.sp{{width:100%;height:auto}} .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}} .cell{{border:1px solid #ccc;padding:4px}} .h{{font-size:12px;font-weight:bold}}
body.chat .audit,body.audit .chat{{display:none}} .tabs button{{font:inherit;padding:4px 12px;margin-right:6px;border:1px solid #888;background:#fff;cursor:pointer}} body.chat #tchat,body.audit #taudit{{background:#2a7ab0;color:#fff}}
.sc{{display:block}} .small{{font-size:12px;color:#444}}
</style></head><body class="chat"><h1>Метрики якості знань для KMS: авіаційні перевезення</h1>
<div class="small">Дата зрізу для актуальності: {cfg["reference_date"]}. Заміри для тренду: {pts}. Значення метрики — частка «добрих» елементів; метрика пройдена, якщо значення ≥ порогу.</div>
<div class="tabs" style="margin:12px 0"><button id="tchat" onclick="document.body.className='chat'">Чат підтримки</button><button id="taudit" onclick="document.body.className='audit'">Аудит</button></div>
<ul class="small">{legend}</ul>
<div class="cards">{cards}</div>
<h2>Таблиця метрик (вибраний сценарій: пороги й позначки ✓/✗ змінюються)</h2>
<table><tr><th>ID</th><th>Вимір</th><th>Метрика</th><th>Поріг</th><th>baseline-v2</th><th>clean</th><th>lab11 (еталон)</th><th>Δ clean − baseline</th></tr>{"".join(rows)}</table>
<h2>Тренд: заміри за часом</h2><div class="small">Синя лінія — виміряні стани за часом; зелений пунктир — еталон lab11; помаранчевий і червоний пунктири — пороги сценаріїв «чат» і «аудит».</div>
<div class="grid">{spark}</div></body></html>"""


def tables_md(cfg, cur):
    f = ["| ID | Вимір | Формула | Поріг: чат | Поріг: аудит |", "|---|---|---|---|---|"]
    for m in cfg["metrics"]:
        f.append(f"| {m['id']} | {m['dimension']} | {m['formula'].split('= ', 1)[-1]} | {m['thresholds']['chat']} | {m['thresholds']['audit']} |")
    v = ["", "| ID | Вимір | baseline-v2 | clean | lab11 | чат: до → після | аудит: до → після |", "|---|---|---|---|---|---|---|"]
    ic = {"ok": "✓", "fail": "✗"}
    for m in cfg["metrics"]:
        g = lambda var: next(x for x in cur[var]["metrics"] if x["id"] == m["id"])
        b, c, r = g("baseline"), g("clean"), g("lab11")
        v.append(f"| {m['id']} | {m['dimension']} | {b['value']:.4f} | {c['value']:.4f} | {r['value']:.4f} | {ic[b['status']['chat']]} → {ic[c['status']['chat']]} | {ic[b['status']['audit']]} → {ic[c['status']['audit']]} |")
    v.append(f"| | **пройдено з 8** | | | | {cur['baseline']['summary']['chat']['ok']} → {cur['clean']['summary']['chat']['ok']} | {cur['baseline']['summary']['audit']['ok']} → {cur['clean']['summary']['audit']['ok']} |")
    return "\n".join(f) + "\n" + "\n".join(v) + "\n"


def main():
    cfg, cur, hist = load()
    (RES / "dashboard.html").write_text(build_html(cfg, cur, hist), encoding="utf-8")
    (RES / "tables.md").write_text(tables_md(cfg, cur), encoding="utf-8")
    fig_trend(cfg, cur, hist); fig_scenarios(cfg, cur)
    print("results/dashboard.html, tables.md, fig_trend.png, fig_scenarios.png; замірів у тренді:", len(hist)); print((RES / "tables.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
