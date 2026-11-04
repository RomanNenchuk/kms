"""Результат 5: оптимізація «до/після» — змінюємо ОДИН фактор: MAX_PER_DOC (ліміт контекстів з одного документа).

  python -m src.rag_opt --run [--cap 2] [--sleep 3] [--resume]   37 тестів з обмеженням -> eval/rag_eval_results_after.jsonl
  python -m src.rag_opt --judge                                    (необов'язково) faithfulness для «після»; діє квота судді
  python -m src.rag_opt --report                                   таблиця до/після і висновок -> docs/rag_optimization.md
«До» = базовий прогін Результату 4 (eval/rag_eval_results.jsonl, без обмеження).
"""
import os, sys
from . import rag_eval as E
from .config import ROOT, EVAL

BEFORE, AFTER = EVAL / "rag_eval_results.jsonl", EVAL / "rag_eval_results_after.jsonl"
OUT = ROOT / "docs" / "rag_optimization.md"
f2 = lambda v: "н/д" if v is None else f"{v:.2f}"
ok = lambda p: f"{p[0]}/{p[1]}"


def metrics(path):
    E.RESULTS = path
    return E.compute()


def delta(x, y, pct=False):
    if x is None or y is None:
        return "—"
    return f"{(y / x - 1) * 100:+.0f}%" if pct and x else f"{y - x:+.2f}"


def build_report(cap, b=BEFORE, a=AFTER):
    m0, m1 = metrics(b), metrics(a)
    s0, s1 = m0["scores"], m1["scores"]
    imp = [t["id"] for t, _ in m1["rows"] if t["id"] in s0 and not s0[t["id"]]["passed"] and s1[t["id"]]["passed"]]
    reg = [t["id"] for t, _ in m1["rows"] if t["id"] in s0 and s0[t["id"]]["passed"] and not s1[t["id"]]["passed"]]
    tokd = (m1["tok_prompt"] / m0["tok_prompt"] - 1) if m0["tok_prompt"] else 0.0
    gain = m1["doc_recall"] - m0["doc_recall"]
    if imp and not reg:
        verdict = f"Зміна покращила якість без регресій: тести {', '.join(imp)} почали проходити."
    elif imp and reg:
        verdict = f"Змішаний результат: покращились {', '.join(imp)}, але погіршились {', '.join(reg)}."
    elif reg:
        verdict = f"Зміна погіршила результат: перестали проходити {', '.join(reg)}."
    elif gain > 0:
        verdict = "Document recall виріс, але кількість пройдених тестів не змінилась."
    else:
        verdict = "Ефекту на якість не виявлено."
    pays = (not reg) and (bool(imp) or gain > 0) and tokd <= 0.10
    cost = lambda m: "н/д (безкоштовний тариф; ціни не задано)" if m["cost"] is None else f"${m['cost']:.5f}"
    fa = lambda m: "н/д (суддя не запускався)" if not m["faithful_all"][1] else f2(m["faithfulness_mean"])
    rows = [("Document recall (18 answerable)", f2(m0["doc_recall"]), f2(m1["doc_recall"]), delta(m0["doc_recall"], m1["doc_recall"])),
            ("Evidence recall", f2(m0["evidence_recall"]), f2(m1["evidence_recall"]), delta(m0["evidence_recall"], m1["evidence_recall"])),
            ("Citation precision", f2(m0["cite_precision"]), f2(m1["cite_precision"]), delta(m0["cite_precision"], m1["cite_precision"]))]
    rows += [(f"Пройдено: {c}", ok(m0["cats"][c]), ok(m1["cats"][c]), "") for c in m0["cats"]]
    rows += [("Правильна відмова", ok(m0["abstain_correct"]), ok(m1["abstain_correct"]), ""),
             ("Хибна відмова", ok(m0["abstain_false"]), ok(m1["abstain_false"]), ""),
             ("Faithfulness (середня)", fa(m0), fa(m1), ""),
             ("Затримка p50, мс", f"{m0['p50']:.0f}", f"{m1['p50']:.0f}", delta(m0["p50"], m1["p50"], True)),
             ("Затримка p95, мс", f"{m0['p95']:.0f}", f"{m1['p95']:.0f}", delta(m0["p95"], m1["p95"], True)),
             ("Prompt-токени (середні)", f"{m0['tok_prompt']:.0f}", f"{m1['tok_prompt']:.0f}", delta(m0["tok_prompt"], m1["tok_prompt"], True)),
             ("Усього токенів (середні)", f"{m0['tok_total']:.0f}", f"{m1['tok_total']:.0f}", delta(m0["tok_total"], m1["tok_total"], True)),
             ("Вартість/запит", cost(m0), cost(m1), "")]
    tbl = "\n".join(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |" for r in rows)
    ch = []
    for t, r in m1["rows"]:
        i = t["id"]
        if i in s0 and (s0[i]["passed"] != s1[i]["passed"] or s0[i].get("doc_recall") != s1[i].get("doc_recall")):
            ch.append(f"| {i} | {t['category']} | {'так' if s0[i]['passed'] else 'ні'} → {'так' if s1[i]['passed'] else 'ні'} | "
                      f"{f2(s0[i].get('doc_recall'))} → {f2(s1[i].get('doc_recall'))} |")
    chg = "\n".join(ch) or "| — | жодних змін | | |"
    return f"""# Оптимізація «до/після» (ЛР 11, Результат 5)

_Згенеровано `python -m src.rag_opt --report`; дані: `eval/rag_eval_results.jsonl` (до), `eval/rag_eval_results_after.jsonl` (після)._

## 1. Гіпотеза і змінений фактор
**Спостереження (Результат 4):** єдиний жорсткий провал (t16) і неповне покриття в t15 — це провали пошуку: усі 5 контекстів у промпті походили з одного документа, а другий потрібний документ не потрапляв.
**Гіпотеза:** якщо обмежити кількість контекстів з одного документа (`MAX_PER_DOC = {cap}`) ще до reranking, у промпт потраплятиме більше різних документів, document recall зросте, а токени й затримка суттєво не зміняться.
**Змінений фактор (один):** `MAX_PER_DOC`: без обмеження → {cap}.
**Незмінне:** генератор `gemini-3.5-flash-lite`, temperature 0, seed 42, промпт `rag_v1`, k = 5, 15 кандидатів на reranking, reranker, рівень доступу, 37 тестів.

## 2. Метрики до/після
| Метрика | До | Після | Зміна |
|---|---|---|---|
{tbl}

Тести, що змінили статус або document recall:
| id | категорія | пройдено | doc recall |
|---|---|---|---|
{chg}

## 3. Висновок
- {verdict}
- Document recall: {f2(m0['doc_recall'])} → {f2(m1['doc_recall'])} ({gain:+.2f}); prompt-токени {tokd * 100:+.0f}%, p50 {delta(m0['p50'], m1['p50'], True)}, p95 {delta(m0['p95'], m1['p95'], True)}.
- Чи окупається зміна: **{'так' if pays else 'ні або не доведено'}** (критерій: немає регресій, є приріст якості, токени не зросли більш ніж на 10%).

## 4. Обмеження
- «До» — це прогін Результату 4, а не повторний: за temperature 0 генерація майже детермінована, але p50/p95 залежать від навантаження мережі в момент запуску.
- 37 тестів — мала вибірка, на 18 питаннях один тест — це 5,6 п. п.
- Faithfulness для «після» оцінюється лише якщо запущено `--judge` (квота судді); «до» — за Результатом 4.
"""


def main():
    a = sys.argv[1:]
    cap = int(a[a.index("--cap") + 1]) if "--cap" in a else 2
    sleep = float(a[a.index("--sleep") + 1]) if "--sleep" in a else 3.0
    if "--run" in a:
        os.environ["MAX_PER_DOC"] = str(cap)
        E.RESULTS = AFTER
        E.run_generation(sleep=sleep, resume="--resume" in a)
    elif "--judge" in a:
        E.RESULTS = AFTER
        E.run_judge()
    elif "--report" in a:
        OUT.write_text(build_report(cap), encoding="utf-8")
        print(f"Збережено {OUT}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
