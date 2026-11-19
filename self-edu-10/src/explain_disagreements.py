#!/usr/bin/env python3
"""Інтерактивний розбір розбіжностей моделей (критерій C3).

Для кожного запиту, де моделі розійшлися, скрипт показує запит, золотий доказ, що знайшла кожна модель,
автоматичні підказки (мова, обрізання фрагмента, спільні слова), просить обрати причини з меню й дописати
коротку примітку, а потім збирає чернетку пояснення в results/explanations.md.

    python src/explain_disagreements.py                       # 4 запити en->en + 3 запити uk->en
    python src/explain_disagreements.py --plan en->en:3,uk->en:3
    python src/explain_disagreements.py --redo                # відповісти заново
Відповіді зберігаються в results/explanations.json; можна перервати (Ctrl+C) і продовжити пізніше.
Потрібно, щоб уже був запуск run_experiment.py (results/per_query.csv).
"""
from __future__ import annotations

import argparse, csv, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES, DATA = ROOT / "results", ROOT / "data"
FIELD = {"en->en": "en", "en_para->en": "en_para", "uk->en": "uk"}

CAUSES = {
    "1": ("мова запиту: англомовна модель не розуміє українських слів", "запит українською, а модель навчена лише на англійській"),
    "2": ("абревіатури й власні назви (ICAO, IATA, CRS, Thai Airways…)", "у запиті є абревіатури або власні назви, які модель по-різному обробляє"),
    "3": ("синоніми / перефразування (запит і доказ різними словами)", "запит і речення-доказ описують те саме різними словами, тож потрібне семантичне, а не лексичне зіставлення"),
    "4": ("обрізання довгого фрагмента (доказ за межею max_seq_length)", "речення-доказ лежить у «хвості» фрагмента, який модель через ліміт max_seq_length не бачить"),
    "5": ("схожий фрагмент з іншої статті чи розділу «перебив» золотий", "модель знайшла тематично близький фрагмент з іншої статті чи розділу"),
    "6": ("префікси query:/passage: (e5)", "різниця пов'язана з префіксами query:/passage:, яких вимагає e5"),
    "7": ("точні числа, дати, назви (21 minutes, 2002…)", "відповідь — точний факт (число, дата), який слабо відображається в загальному змісті фрагмента"),
    "8": ("інше (опиши в примітці)", "інша причина"),
}


def jl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def squash(s):
    return re.sub(r"\s+", " ", s).strip()


def pick(per_q, scenario, models, n):
    by = {}
    for r in per_q:
        if r["scenario"] == scenario and r["model"] in models:
            by.setdefault(r["qid"], {})[r["model"]] = r
    sc = []
    for qid, m in by.items():
        if len(m) < len(models):
            continue
        ranks = [int(m[x]["rank_of_gold"]) for x in models]
        sc.append((min(ranks) <= 5 < max(ranks), max(ranks) - min(ranks), qid))
    sc.sort(reverse=True)
    return [(qid, by[qid]) for _, spread, qid in sc if spread > 0][:n]


def hints(q, scenario, models, by_model, chunk, max_seq):
    out = []
    field = FIELD[scenario]
    ranks = {m: int(by_model[m]["rank_of_gold"]) for m in models}
    best = min(ranks, key=ranks.get)
    worst = max(ranks, key=ranks.get)
    out.append(f"Найкраще впоралась `{best}` (ранг {ranks[best]}), найгірше — `{worst}` (ранг {ranks[worst]}).")
    if scenario == "uk->en":
        en_only = [m for m in models if m.endswith("-en")]
        if en_only:
            out.append(f"Запит українською; `{', '.join(en_only)}` — англомовна модель (підказка до причини 1).")
    ct, ev = squash(chunk["text"]), squash(q["evidence"][0])
    p = ct.find(ev)
    if p < 0:
        p = ct.find(ev[:40])
    if p >= 0:
        end = p + len(ev)
        cut = [m for m in models if max_seq.get(m) and end > max_seq[m] * 4]
        out.append(f"Фрагмент має {len(ct)} символів, доказ закінчується на позиції {end}.")
        if cut:
            out.append("Орієнтовно (1 токен ≈ 4 символи) доказ за межею ліміту для: " + ", ".join(f"`{m}` (ліміт {max_seq[m]} ток. ≈ {max_seq[m] * 4} симв.)" for m in cut) + " — підказка до причини 4.")
        else:
            out.append("Доказ вкладається в ліміт усіх моделей, тож причина 4 малоймовірна.")
    words = lambda s: set(re.findall(r"[A-Za-z0-9]{3,}", s.lower()))
    shared = sorted(words(q[field]) & words(ev))
    caps = sorted(set(re.findall(r"\b[A-Z]{2,}[A-Za-z0-9]*\b", q[field])))
    out.append("Спільні латинські слова запиту й доказу: " + (", ".join(shared) if shared else "немає (підказка до причини 3: різні слова)"))
    if caps:
        out.append("Абревіатури в запиті: " + ", ".join(caps) + " (підказка до причини 2).")
    if re.search(r"\d", ev):
        out.append("У доказі є числа/дати (підказка до причини 7).")
    return out


def show(i, total, scenario, q, by_model, models, corpus, id2c, max_seq):
    field = FIELD[scenario]
    gold_id = q["relevant_chunks"][0][0]
    gold = id2c[gold_id]
    print("\n" + "=" * 78)
    print(f"[{i}/{total}] {q['id']} ({q['type']}), сценарій {scenario}")
    print(f"ЗАПИТ:  {q[field]}")
    print(f"ДОКАЗ:  {q['evidence'][0]}")
    print(f"ЗОЛОТИЙ ФРАГМЕНТ: {gold['title']} › {gold['section']}")
    print("-" * 78)
    for m in models:
        r = by_model[m]
        top1 = id2c[r["top5_chunk_ids"].split()[0]]
        same = "той самий документ" if top1["doc_id"] == gold["doc_id"] else "ІНША стаття"
        mark = "✓" if int(r["rank_of_gold"]) <= 5 else "✗"
        print(f"{mark} {m:16s} ранг {r['rank_of_gold']:>4}  | №1 знайдено: {top1['title']} › {top1['section']} ({same})")
        if int(r["rank_of_gold"]) > 1:
            print(f"     текст №1: {squash(top1['text'])[:170]}…")
    print("-" * 78)
    print("ПІДКАЗКИ СКРИПТА:")
    for h in hints(q, scenario, models, by_model, gold, max_seq):
        print("  •", h)
    return gold


def ask():
    print("\nЯкі причини розбіжності? Обери номери через кому (напр. 3,5):")
    for k, (t, _) in CAUSES.items():
        print(f"  {k}. {t}")
    while True:
        s = input("Номери: ").strip()
        ks = [x.strip() for x in s.split(",") if x.strip()]
        if ks and all(k in CAUSES for k in ks):
            break
        print("  введи номери з меню, наприклад 3 або 3,5")
    note = input("Своїми словами 1–2 речення (що ти бачиш у списку вище; Enter — пропустити): ").strip()
    return ks, note


def draft(scenario, q, by_model, models, ks, note):
    field = FIELD[scenario]
    ranks = ", ".join(f"{m} — ранг {by_model[m]['rank_of_gold']}" for m in models)
    reasons = "; ".join(CAUSES[k][1] for k in ks)
    s = f"Моделі дали різні результати ({ranks}). Імовірні причини: {reasons}."
    return s + (f" {note}" if note else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="en->en:4,uk->en:3", help="сценарій:кількість через кому")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--include-baseline", action="store_true")
    a = ap.parse_args()

    per_q = list(csv.DictReader(open(RES / "per_query.csv", encoding="utf-8")))
    summary = list(csv.DictReader(open(RES / "summary.csv", encoding="utf-8")))
    models = [m for m in dict.fromkeys(r["model"] for r in summary) if a.include_baseline or m != "hashing-baseline"]
    max_seq = {r["model"]: (int(r["max_seq"]) if r["max_seq"] not in ("", "None") else None) for r in summary}
    corpus, queries = jl(DATA / "corpus.jsonl"), {q["id"]: q for q in jl(DATA / "queries.jsonl")}
    id2c = {c["id"]: c for c in corpus}

    store_p = RES / "explanations.json"
    store = json.loads(store_p.read_text(encoding="utf-8")) if store_p.exists() and not a.redo else {}

    plan = [(x.split(":")[0], int(x.split(":")[1])) for x in a.plan.split(",")]
    items = [(sc, qid, by) for sc, n in plan for qid, by in pick(per_q, sc, models, n)]
    print(f"Моделі в аналізі: {', '.join(models)}. Запитів до розбору: {len(items)}.")
    try:
        for i, (sc, qid, by) in enumerate(items, 1):
            key = f"{sc}|{qid}"
            if key in store:
                print(f"[{i}/{len(items)}] {key} — уже є відповідь, пропускаю (--redo щоб переробити)")
                continue
            q = queries[qid]
            show(i, len(items), sc, q, by, models, corpus, id2c, max_seq)
            ks, note = ask()
            store[key] = {"causes": ks, "note": note, "draft": draft(sc, q, by, models, ks, note)}
            store_p.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    except (KeyboardInterrupt, EOFError):
        print("\nПерервано; збережене лишається, запусти скрипт ще раз для продовження.")

    out = ["# Аналіз розбіжностей моделей\n"]
    n_done = 0
    for sc, qid, by in items:
        e = store.get(f"{sc}|{qid}")
        if not e:
            continue
        n_done += 1
        q = queries[qid]
        gold = id2c[q["relevant_chunks"][0][0]]
        out.append(f"\n## {n_done}. {qid} ({q['type']}), сценарій `{sc}`\n")
        out.append(f"**Запит:** {q[FIELD[sc]]}\n\n**Золотий доказ:** _{q['evidence'][0]}_ ({gold['title']} › {gold['section']})\n")
        out.append("\n| модель | ранг золотого | найкращий знайдений фрагмент |\n|---|---|---|")
        for m in models:
            t1 = id2c[by[m]["top5_chunk_ids"].split()[0]]
            out.append(f"| {m} | {by[m]['rank_of_gold']} | {t1['title']} › {t1['section']} |")
        out.append(f"\n**Причини:** {'; '.join(CAUSES[k][0] for k in e['causes'])}\n\n**Пояснення:** {e['draft']}\n")
    (RES / "explanations.md").write_text("\n".join(out), encoding="utf-8")
    print(f"\nГотово: розібрано {n_done} з {len(items)} запитів → results/explanations.md" + ("" if n_done >= 5 else "  (для C3 потрібно ≥ 5!)"))


if __name__ == "__main__":
    main()
