"""Результат 4: оцінка методів А і Б на золотому наборі.

  python src/evaluate.py --split dev                 # репетиція на dev
  python src/evaluate.py --split test --final        # фінальна оцінка (після run обох методів на test --final)

Читає results/{rules,llm}_{split}.jsonl і data/gold.jsonl. Пише:
  results/eval_{split}.json            - всі метрики
  results/errors_{method}_{split}.csv  - FP/FN з автокатегорією (колонка comment - для ручного аналізу)
  results/audit_{split}.csv            - випадкові 20 передбачень кожного методу для ручної перевірки цитат
  docs/extraction_eval_draft_{split}.md - чернетка звіту з таблицями (висновки дописуються вручну)
"""
import argparse
import csv
import json
import os
import random
from collections import defaultdict

import common as cm
import gold_tools as gt

METHODS = {"A": ("rules", "Метод А: правила + spaCy"), "B": ("llm", "Метод Б: Gemini")}


def key(r):
    return (r["doc_id"], gt.ent_key(r["subject"]), r["relation"], gt.ent_key(r["object"]))


def prf(g, p):
    tp = len(g & p)
    pr = tp / len(p) if p else 0.0
    rc = tp / len(g) if g else 0.0
    return {"gold": len(g), "pred": len(p), "tp": tp, "P": round(pr, 3), "R": round(rc, 3),
            "F1": round(2 * pr * rc / (pr + rc), 3) if pr + rc else 0.0}


def by(keyfn, G, P):
    out = {}
    for name in sorted({keyfn(k) for k in G} | {keyfn(k) for k in P}):
        out[name] = prf({k for k in G if keyfn(k) == name}, {k for k in P if keyfn(k) == name})
    return out


def categorize(kind, k, other, rows_by_key):
    """Автокатегорія помилки (грубо; остаточна класифікація - вручну в колонці comment)."""
    doc, s, rel, o = k
    same_doc = [x for x in other if x[0] == doc]
    if kind == "FP":                                   # зайве передбачення; other = gold
        if any(x[1] == s and x[3] == o and x[2] != rel for x in same_doc):
            return "wrong_relation"
        if any(x[1] == o and x[3] == s and x[2] == rel for x in same_doc):
            return "direction_swapped"
        if any(x[2] == rel and (x[1] == s) != (x[3] == o) and (x[1] == s or x[3] == o) for x in same_doc):
            return "wrong_entity_or_canonical"
        return "extra_not_in_gold"
    if any(x[2] == rel and (x[1] == s or x[3] == o) for x in same_doc):          # FN; other = pred
        return "missed_or_wrong_canonical"
    return "missed"


def evidence_of(r):
    return r["evidence"]["text"] if isinstance(r.get("evidence"), dict) else str(r.get("evidence", ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--audit-n", type=int, default=20)
    a = ap.parse_args()
    docs = set(cm.split_docs(a.split, a.final))
    gold_rows = [r for r in gt.read_jsonl(gt.ROOT / "data" / "gold.jsonl") if r["doc_id"] in docs]
    G = {key(r) for r in gold_rows}
    res, report = {}, []
    random.seed(gt.SEED)
    audit = []
    for m, (prefix, title) in METHODS.items():
        path = cm.RESULTS / f"{prefix}_{a.split}.jsonl"
        rows = [r for r in gt.read_jsonl(path) if r["doc_id"] in docs]
        P = {key(r) for r in rows}
        rbk = {key(r): r for r in rows}
        info = {"overall": prf(G, P), "by_relation": by(lambda k: k[2], G, P),
                "by_subject_type": {}, "claims": len(rows)}
        # за типом суб'єкта (береться з золотого або передбачення)
        stype = {key(r): r["subject"]["type"] for r in gold_rows + rows}
        info["by_subject_type"] = by(lambda k: stype.get(k, "?"), G, P)
        # вартість і цитати (метод Б)
        if m == "B":
            sp = cm.RESULTS / f"{prefix}_{a.split}_summary.json"
            if sp.exists():
                sm = json.loads(sp.read_text(encoding="utf-8"))
                info["cost"] = {k: sm.get(k) for k in ("tokens_in", "tokens_out", "cost_usd", "cost_per_doc_usd")}
                pi, po = float(os.getenv("GEMINI_PRICE_IN", 0)), float(os.getenv("GEMINI_PRICE_OUT", 0))
                if pi or po:                                   # умовна вартість за публічним прайсом ($ за 1M токенів)
                    c = (sm["tokens_in"] * pi + sm["tokens_out"] * po) / 1e6
                    info["cost"].update(cost_usd=round(c, 5), cost_per_doc_usd=round(c / sm["docs"], 5),
                                        price_in=pi, price_out=po, note="умовна вартість за публічним прайсом")
                pin, pout = float(os.getenv("GEMINI_PRICE_IN", 0)), float(os.getenv("GEMINI_PRICE_OUT", 0))
                if (pin or pout) and sm.get("tokens_in") is not None:      # перерахунок вартості з токенів за цінами .env
                    c = (sm["tokens_in"] * pin + sm["tokens_out"] * pout) / 1e6
                    info["cost"].update(cost_usd=round(c, 5), cost_per_doc_usd=round(c / sm["docs"], 5))
                    info["cost"]["price_per_1M_usd"] = {"in": pin, "out": pout}
                info["unverified_evidence_share"] = sm.get("unverified_share")
                info["rejected_by_validation"] = sm.get("rejected")
        else:
            info["cost"] = {"cost_usd": 0.0, "cost_per_doc_usd": 0.0}
        # правдоподібно непідтверджені: FP, чия цитата не перетинається з жодним золотим твердженням документа
        gold_ev = defaultdict(list)
        for r in gold_rows:
            e = r["evidence"]
            if "start" not in e:                                   # запасний варіант: шукаємо цитату в тексті
                i = cm.read_doc(r["doc_id"]).find(e["text"])
                e = {"start": i, "end": i + len(e["text"])} if i >= 0 else {"start": -1, "end": -1}
            gold_ev[r["doc_id"]].append((e["start"], e["end"]))
        fp = [rbk[k] for k in P - G]
        def overlaps(r):
            e = r["evidence"]
            return any(s < e["end"] and e["start"] < t for s, t in gold_ev[r["doc_id"]])
        unsup = [r for r in fp if not overlaps(r)]
        info["fp_total"] = len(fp)
        info["fp_without_gold_evidence_overlap"] = len(unsup)
        info["fp_unsupported_share_of_pred"] = round(len(unsup) / len(P), 3) if P else 0.0
        # помилки
        err_path = cm.RESULTS / f"errors_{m}_{a.split}.csv"
        with open(err_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["kind", "category", "doc", "subject", "relation", "object", "evidence", "comment"])
            gk = {key(r): r for r in gold_rows}
            for k in sorted(P - G):
                w.writerow(["FP", categorize("FP", k, G, rbk), k[0], k[1], k[2], k[3], evidence_of(rbk[k])[:300], ""])
            for k in sorted(G - P):
                w.writerow(["FN", categorize("FN", k, P, gk), k[0], k[1], k[2], k[3], evidence_of(gk[k])[:300], ""])
        cats = defaultdict(int)
        for r in csv.DictReader(open(err_path, encoding="utf-8")):
            cats[(r["kind"], r["category"])] += 1
        info["error_categories"] = {f"{k[0]}:{k[1]}": v for k, v in sorted(cats.items())}
        # вибірка для ручної перевірки цитат
        for r in random.sample(rows, min(a.audit_n, len(rows))):
            audit.append([m, r["doc_id"], r["subject"]["canonical"], r["relation"], r["object"]["canonical"],
                          evidence_of(r)[:300], "in_gold" if key(r) in G else "not_in_gold", "", ""])
        res[m] = info
    with open(cm.RESULTS / f"audit_{a.split}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["method", "doc", "subject", "relation", "object", "evidence", "auto", "supported(yes/no)", "comment"])
        w.writerows(audit)
    (cm.RESULTS / f"eval_{a.split}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    # чернетка звіту
    L = [f"# Оцінка видобування ({a.split})", "", f"Документів: {len(docs)}, золотих тверджень: {len(G)}. "
         "Збіг: (документ, subject.canonical, relation, object.canonical).", "",
         "## Загальні метрики", "", "| Метод | Передбачень | TP | P | R | F1 | Вартість/док, $ |", "|---|---|---|---|---|---|---|"]
    for m, (_, title) in METHODS.items():
        o = res[m]["overall"]
        L.append(f"| {title} | {o['pred']} | {o['tp']} | {o['P']} | {o['R']} | {o['F1']} | {res[m]['cost'].get('cost_per_doc_usd')} |")
    for label, field in (("за відношенням", "by_relation"), ("за типом суб'єкта", "by_subject_type")):
        L += ["", f"## P/R/F1 {label}", "", "| Категорія | gold | А: P / R / F1 | Б: P / R / F1 |", "|---|---|---|---|"]
        for name in sorted(set(res["A"][field]) | set(res["B"][field])):
            ra = res["A"][field].get(name, {}); rb = res["B"][field].get(name, {})
            f = lambda x: f"{x.get('P', 0)} / {x.get('R', 0)} / {x.get('F1', 0)}"
            L.append(f"| {name} | {ra.get('gold', rb.get('gold', 0))} | {f(ra)} | {f(rb)} |")
    L += ["", "## Цитати та вартість", "",
          f"- Метод Б: частка відповідей моделі, відхилених через цитату, якої немає в тексті: {res['B'].get('unverified_evidence_share')}.",
          f"- Метод Б: відхилено валідацією (сигнатура/мітки): {res['B'].get('rejected_by_validation')}.",
          f"- Хибні передбачення без перетину цитати з жодним золотим твердженням (А / Б): "
          f"{res['A']['fp_without_gold_evidence_overlap']} / {res['B']['fp_without_gold_evidence_overlap']} "
          f"(частка від усіх передбачень {res['A']['fp_unsupported_share_of_pred']} / {res['B']['fp_unsupported_share_of_pred']}).",
          f"- Ручна перевірка вибірки: `results/audit_{a.split}.csv` (колонка supported yes/no) -> тут вказати частку.",
          f"- Токени метод Б: {res['B'].get('cost')}", "",
          "## Категорії помилок (авто)", ""]
    for m in METHODS:
        L.append(f"- {METHODS[m][1]}: {res[m]['error_categories']}")
    L += ["", "## Аналіз ≥10 помилок", "", "(Заповнити з `results/errors_*_*.csv`: приклад, причина, що змінити.)", "",
          "## Рекомендація", "", "(Який метод і за яких умов використовувати; чому.)"]
    out = gt.ROOT / "docs" / f"extraction_eval_draft_{a.split}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    for m in METHODS:
        o = res[m]["overall"]
        print(f"{METHODS[m][1]}: pred={o['pred']} TP={o['tp']} P={o['P']} R={o['R']} F1={o['F1']}")
    print(f"Записано: results/eval_{a.split}.json, errors_*, audit_{a.split}.csv, {out.relative_to(gt.ROOT)}")


if __name__ == "__main__":
    main()