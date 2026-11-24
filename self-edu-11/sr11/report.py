"""Генерація таблиць і чернетки висновків/плану для звіту (критерії C2, C3, C4) -> results/report_tables.md."""
import collections
import json
import math
import os
from . import config as C
from .queries import load_queries
from .runner import load_run
from . import table

PLAN = {
    "пошук": ("Покращити пошук: збільшити n_ctx/top_k, розбивати багатокрокові питання на підзапити (query decomposition), "
              "перекладати українські запити англійською перед пошуком, додати multi-query",
              "doc_recall (gold-документ у top-5), simple+multistep", "≥ 0.95"),
    "контекст": ("Віддавати LLM більше контексту навколо знайденого фрагмента: збільшити MAX_CTX_CHARS, додавати сусідні child-чанки одного parent",
                 "evidence_recall (доказове речення в контексті LLM)", "≥ 0.95"),
    "генерація": ("Посилити промпт rag_v1: «спершу виписати факти, потім обчислити», обов'язкові цитати на кожне твердження, "
                  "шаблон для конфліктів (показати обидва значення з джерелами); post-check faithfulness (self-check) перед видачею",
                  "середня faithfulness (суддя) і частка правильних відповідей simple+multistep+conflict", "faithfulness ≥ 0.95; 0 галюцинацій на unanswerable"),
    "політика": ("Додати guardrails: класифікатор шкідливих запитів ДО RAG, санітизація/ігнорування інструкцій у джерелах, "
                 "вихідний фільтр (URL, персональні дані, числа не з контексту), єдиний токен відмови NO_ANSWER",
                 "частка пройдених harmful-тестів; кількість виконаних ін'єкцій і витоків", "harmful 5/5; 0 виконаних ін'єкцій"),
}


def pct(xs, p):
    xs = sorted(xs)
    return xs[max(0, math.ceil(p * len(xs)) - 1)] if xs else None


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def f2(v):
    return "н/д" if v is None else f"{v:.2f}"


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def short(s, n):
    s = (s or "").replace("|", "/").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def build(queries=None, rows=None, run=None, kappa=None):
    queries = queries or load_queries()
    rows = rows if rows is not None else table.load()
    run = run if run is not None else load_run()
    if not rows:
        raise SystemExit("Немає classification.csv — спершу `python -m sr11 classify`.")
    q = {x["id"]: x for x in queries}
    fin = {r["id"]: table.final(r) for r in rows}
    n = len(rows)
    ver = collections.Counter(v for v, _ in fin.values())
    fails = [r for r in rows if fin[r["id"]][0] != "правильно"]
    cause = collections.Counter(fin[r["id"]][1] for r in fails)
    by_cat = {c: [r for r in rows if r["category"] == c] for c in C.CATEGORIES}

    # --- метрики
    ans_rows = [r for r in rows if r["category"] in ("simple", "multistep")]
    doc_rec = avg([_num(r["doc_recall"]) for r in ans_rows])
    ev_rec = avg([_num(r["evidence_recall"]) for r in ans_rows])
    faith = avg([_num(r["faithfulness"]) for r in rows])
    given = [run[r["id"]] for r in rows if not run[r["id"]]["abstained"]]
    cite_ok = sum(not x["citations"]["invalid"] for x in given)
    una = by_cat["unanswerable"]
    una_ok = sum(fin[r["id"]][0] == "правильно" for r in una)
    false_abs = sum(run[r["id"]]["abstained"] for r in ans_rows)
    lat = [run[r["id"]]["latency_ms"] for r in rows]
    tok = [run[r["id"]]["tokens"]["total"] for r in rows]
    harm = by_cat["harmful"]
    harm_ok = sum(fin[r["id"]][0] == "правильно" for r in harm)

    L = []
    L.append("# Таблиці для звіту СР11 (згенеровано `python -m sr11 report`)\n")
    L.append(f"Генератор: `{os.environ.get('GEMINI_MODEL', '?')}`; суддя: `{os.environ.get('JUDGE_MODEL', '?')}`; запитів: {n}.\n")

    L.append("## 1. Набір запитів (C1)\n")
    L.append("| Категорія | К-сть | Українською | Із синтетичною фікстурою |\n|---|---|---|---|")
    for c in C.CATEGORIES:
        qs = [x for x in queries if x["category"] == c]
        L.append(f"| {C.CATEGORY_UK[c]} ({c}) | {len(qs)} | {sum(x['lang'] == 'uk' for x in qs)} | {sum(bool(x['fixtures']) for x in qs)} |")
    L.append(f"\nБез відповіді + шкідливі: **{len(una) + len(harm)}** (потрібно ≥ 4). Категорій: **{sum(bool(v) for v in by_cat.values())}** (потрібно ≥ 4).\n")

    L.append("## 2. Результати за категоріями (C2)\n")
    L.append("| Категорія | правильно | частково | ні |\n|---|---|---|---|")
    for c in C.CATEGORIES:
        cc = collections.Counter(fin[r["id"]][0] for r in by_cat[c])
        L.append(f"| {C.CATEGORY_UK[c]} | {cc['правильно']} | {cc['частково']} | {cc['ні']} |")
    L.append(f"| **Разом** | **{ver['правильно']}** | **{ver['частково']}** | **{ver['ні']}** |\n")

    L.append("## 3. Усі запити з класифікацією (C2)\n")
    L.append("| id | категорія | запит | результат | клас причини | пояснення |\n|---|---|---|---|---|---|")
    for r in rows:
        v, c = fin[r["id"]]
        mark = " ✎" if (r.get("human_verdict") or r.get("human_cause")) else ""
        L.append(f"| {r['id']} | {r['category']} | {short(r['question'], 70)} | {v}{mark} | {c} | {short(r['auto_detail'], 90)} |")
    L.append("\n✎ — вердикт/причину виправлено вручну.\n")

    L.append("## 4. Розподіл причин відмов (C3)\n")
    L.append(f"Відмовами вважаю результати «частково» та «ні»: {len(fails)} із {n}.\n")
    L.append("| Клас причини | К-сть | Частка відмов |\n|---|---|---|")
    for c in C.CAUSES:
        L.append(f"| {c} | {cause[c]} | {cause[c] / len(fails):.0%} |" if fails else f"| {c} | 0 | — |")
    L.append("\nПошук чи генерація? Для simple+multistep: поєднання «gold-документ у top-5» × результат.\n")
    hit = [r for r in ans_rows if _num(r["doc_recall"]) == 1.0]
    miss = [r for r in ans_rows if _num(r["doc_recall"]) != 1.0]
    L.append("| Пошук | запитів | з них правильно | частково | ні |\n|---|---|---|---|---|")
    for name, grp in (("gold знайдено (doc_recall = 1)", hit), ("gold не знайдено повністю", miss)):
        cc = collections.Counter(fin[r["id"]][0] for r in grp)
        L.append(f"| {name} | {len(grp)} | {cc['правильно']} | {cc['частково']} | {cc['ні']} |")

    L.append("\n## 5. Метрики\n")
    L.append("| Метрика | Значення |\n|---|---|")
    L.append(f"| doc_recall (simple+multistep) | {f2(doc_rec)} |\n| evidence_recall (simple+multistep) | {f2(ev_rec)} |")
    L.append(f"| faithfulness, середня (суддя, лише не-відмови) | {f2(faith)} |")
    L.append(f"| цитати валідні (не-відмови) | {cite_ok}/{len(given)} |")
    L.append(f"| правильні відмови на unanswerable | {una_ok}/{len(una)} |\n| хибні відмови на simple+multistep | {false_abs}/{len(ans_rows)} |")
    L.append(f"| harmful пройдено | {harm_ok}/{len(harm)} |")
    L.append(f"| затримка p50 / p95, мс | {pct(lat, .5):.0f} / {pct(lat, .95):.0f} |\n| токенів на запит, середнє | {avg(tok):.0f} |")
    if kappa:
        ks = "н/д" if kappa["kappa"] is None else f"{kappa['kappa']:.2f}"
        L.append(f"| суддя vs людина (n={kappa['n']}) | згода {kappa['agreement']:.0%}, κ = {ks} |")
    else:
        L.append("| суддя vs людина | ще не пораховано: `sheet` → заповнити → `kappa` |")

    # --- чернетка висновків (дані, не вердикт)
    L.append("\n## 6. Чернетка висновків (C3) — перевір цифри й перепиши власними словами\n")
    worst = min(C.CATEGORIES, key=lambda c: (sum(fin[r['id']][0] == 'правильно' for r in by_cat[c]) / max(1, len(by_cat[c]))))
    w_ok = sum(fin[r["id"]][0] == "правильно" for r in by_cat[worst])
    obs = [f"Загалом правильно {ver['правильно']}/{n} ({ver['правильно'] / n:.0%}); найслабша категорія — «{C.CATEGORY_UK[worst]}» ({w_ok}/{len(by_cat[worst])} правильно)."]
    if fails:
        top = cause.most_common(1)[0]
        obs.append(f"Найчастіший клас причин — «{top[0]}»: {top[1]} із {len(fails)} відмов ({top[1] / len(fails):.0%}).")
    if ans_rows:
        a = collections.Counter(fin[r["id"]][0] for r in hit)
        b = collections.Counter(fin[r["id"]][0] for r in miss)
        obs.append(f"Якщо gold-документ знайдено, правильних {a['правильно']}/{len(hit)}; якщо ні — {b['правильно']}/{len(miss)}: "
                   + ("основна проблема в пошуку." if len(miss) and b['правильно'] / len(miss) < a['правильно'] / max(1, len(hit)) - 0.2 else "пошук не єдина причина, помилки є й при знайденому контексті."))
    uk = [r for r in ans_rows if r["lang"] == "uk"]
    en = [r for r in ans_rows if r["lang"] == "en"]
    if uk and en:
        obs.append(f"Українські запити (simple+multistep): правильно {sum(fin[r['id']][0] == 'правильно' for r in uk)}/{len(uk)}; англійські: {sum(fin[r['id']][0] == 'правильно' for r in en)}/{len(en)}.")
    if una:
        nm = [r for r in una if r["subtype"].startswith("near_miss")]
        nm_bad = [r["id"] for r in nm if fin[r["id"]][0] != "правильно"]
        obs.append(f"Питання без відповіді: правильна відмова {una_ok}/{len(una)}; серед «майже-відповідей» (near-miss, тема є в корпусі) "
                   f"не пройдено {len(nm_bad)}/{len(nm)}" + (f" ({', '.join(nm_bad)})." if nm_bad else "."))
    if harm:
        bad = [r["id"] for r in harm if fin[r["id"]][0] != "правильно"]
        obs.append(f"Шкідливі/атаки: пройдено {harm_ok}/{len(harm)}" + (f"; провали: {', '.join(bad)}." if bad else "."))
    for i, o in enumerate(obs, 1):
        L.append(f"{i}. {o}")

    # --- чернетка плану
    L.append("\n## 7. Чернетка плану виправлень (C4) — відредагуй під свої результати\n")
    base = {"пошук": f2(doc_rec), "контекст": f2(ev_rec), "генерація": f"faithfulness {f2(faith)}", "політика": f"harmful {harm_ok}/{len(harm)}"}
    L.append("| Пріоритет | Причина | К-сть | Виправлення | Метрика успіху | Зараз | Ціль |\n|---|---|---|---|---|---|---|")
    prio = {c: ("P1" if (c == "політика" or cause[c] >= 3) else ("P2" if cause[c] == 2 else "P3")) for c in C.CAUSES if cause[c]}
    order = sorted(prio, key=lambda c: (prio[c], -cause[c]))
    for c in order:
        fix, metric, target = PLAN[c]
        L.append(f"| {prio[c]} | {c} | {cause[c]} | {fix} | {metric} | {base[c]} | {target} |")
    L.append("\nМетрики, що зміняться після плану: " + ", ".join(f"{PLAN[c][1].split(' (')[0]}" for c in order) + ".")
    return "\n".join(L) + "\n"


def write():
    kap = C.p("kappa.json")
    md = build(kappa=json.loads(kap.read_text(encoding="utf-8")) if kap.exists() else None)
    C.p("report_tables.md").write_text(md, encoding="utf-8")
    print(f"Записано {C.p('report_tables.md')}")
    return md
