"""Формує claims/claims.csv (протокол «LLM-експерт») і docs/claims_summary.md.

1) Додає базові твердження C001.. (те, що LLM-асистент стверджував у ЛР 12 і що перевірено/ще ні).
2) Якщо є tests/t2sql_results.jsonl (реальний запуск Gemini), перегенерує твердження G-<id> за результатом
   порівняння з еталоном (V4) або AST-перевіркою (V2).
Рядки зі статусом pending — ваша робота: перевірте й змініть статус на verified/rejected з поясненням.
Запуск: python tools/make_claims.py
"""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "claims" / "claims.csv"
FIELDS = ["id", "claim", "type", "source", "verification_level", "status", "comment"]
CLAUDE = "Claude (Anthropic), чат claude.ai"

BASE = [
    ("C001", "Зерно факту: один рядок fact_flight = один рейс (flight leg) на дату; скасований рейс теж є рядком.", "rule", CLAUDE, "V1", "pending",
     "Підтвердіть самі (V1): перегляньте docs/star_design.md. Унікальність flight_id перевіряє etl/quality.py."),
    ("C002", "DDL з sql/ddl.sql виконується в DuckDB без помилок.", "fact", CLAUDE, "V2", "verified", "python etl/load.py виконує DDL і завантажує всі 6 таблиць."),
    ("C003", "Усі 21 перевірка якості дають 0 порушень, зокрема немає «сиріт» за 6 ключами.", "fact", CLAUDE, "V2", "verified",
     "Вивід python etl/load.py: «Перевірок: 21, провалено: 0»; звіт у data/quality_report.json."),
    ("C004", "dim_aircraft реалізує SCD2: версії не перетинаються, для кожного борту одна поточна, дата рейсу потрапляє в інтервал версії.", "rule", CLAUDE, "V2", "verified",
     "Перевірки scd2_one_current, scd2_no_overlap, scd2_fact_in_validity, seats_match_aircraft у etl/quality.py."),
    ("C005", "Генератор детермінований: однаковий seed дає однакові дані.", "fact", CLAUDE, "V4", "verified",
     "Результати run_olap на машині автора збіглися з отриманими при розробці (5000 рейсів, 57.8 % вчасних, 118600 хв затримки)."),
    ("C006", "DuckDB підтримує ROLLUP, CUBE, PIVOT, QUALIFY і віконні функції, використані в 9 запитах.", "fact", CLAUDE, "V2", "verified",
     "Усі 9 файлів sql/olap/*.sql виконуються: python etl/run_olap.py."),
    ("C007", "Q1 (ROLLUP): кількість рейсів, частка вчасних і середня затримка за типом авіакомпанії збігаються з pandas.", "fact", CLAUDE, "V4", "verified",
     "python etl/verify_olap.py: [PASS] Q1 ROLLUP."),
    ("C008", "Q9 (drill-down): суми хвилин за 14 підкласами, 5 класами та загалом (118600) збігаються з pandas.", "fact", CLAUDE, "V4", "verified",
     "python etl/verify_olap.py: [PASS] Q9 drill-down."),
    ("C009", "Те саме питання через семантичний SQL, ручний OLAP-запит і pandas дає однаковий результат (вчасність/затримка/рейси за типом; затримка за класом; пасажири за місяцями).", "fact", CLAUDE, "V4", "verified",
     "python semantic/check_consistency.py: 4 × PASS."),
    ("C010", "load_factor і revenue_per_pax за типом літака збігаються з незалежним обчисленням у pandas.", "fact", CLAUDE, "V4", "verified", "check_consistency.py, перевірка Q4."),
    ("C011", "У літніх рейсах із хабів full-service має більшу середню затримку, ніж low-cost (на 6–11 хв).", "fact", CLAUDE, "V4", "verified",
     "Значення з виводу 04_dice.sql (python etl/run_olap.py); вибірки 88–124 рейси на клітинку."),
    ("C012", "Грози майже повністю літні (124 із 163), сніг/лід і туман — переважно зимові.", "fact", CLAUDE, "V4", "verified", "Значення з виводу 05_pivot.sql."),
    ("C013", "Різниця у частці вчасних рейсів між авіакомпаніями (55.9–63.0 %) статистично незначна.", "hypothesis", CLAUDE, "V1", "pending",
     "Не перевірено статистичним тестом (вибірки 320–1097 рейсів). Або перевірте (наприклад, χ²), або сформулюйте обережніше."),
    ("C014", "У топ-5 маршрутів за середньою затримкою ефекту хабу не видно.", "hypothesis", CLAUDE, "V1", "pending",
     "Малі вибірки (15–45 рейсів на маршрут); порівняння середніх по групах не виконувалось."),
    ("C015", "Ключ `on` у YAML 1.1 читається як булеве значення, тому в реєстрі вимірів використано `cond`.", "fact", CLAUDE, "V2", "verified",
     "Виявлено при запуску (KeyError); після заміни семантичний шар і підказка text-to-SQL будуються."),
    ("C016", "Перша версія semantic/metrics.yml із ключем `on` у join коректно працює для всіх вимірів.", "fact", CLAUDE, "V2", "rejected",
     "Відхилено: у трьох вимірах origin_* залишився ключ `on` (подвійний пробіл не потрапив у заміну), build_system_prompt() падав з KeyError 'cond'. Файл виправлено, перевірено запитом за всіма вимірами."),
    ("C017", "Перша версія metrics.yml розбирається YAML-парсером без помилок.", "fact", CLAUDE, "V2", "rejected",
     "Відхилено: двокрапка всередині незаквочених рядків constraints ламала YAML; значення взято в лапки."),
    ("C018", "AST-перевірка блокує DELETE/DROP/INSERT/DDL, кілька операторів, read_csv, getenv, information_schema, таблиці поза whitelist та додає/обмежує LIMIT 1000.", "rule", CLAUDE, "V2", "verified",
     "tests/test_validate.py (параметризовані негативні тести)."),
    ("C019", "З'єднання read-only з enable_external_access=false не дозволяє ні запису, ні читання/запису файлів, навіть якщо AST-перевірку обійдено.", "fact", CLAUDE, "V2", "verified",
     "tests/test_validate.py: test_readonly_connection_cannot_write, test_external_access_disabled."),
    ("C020", "Тайм-аут через con.interrupt зупиняє важкий запит (декартів добуток 4 копій факту).", "fact", CLAUDE, "V2", "verified", "tests/test_validate.py::test_timeout."),
    ("C021", "Пакет google-genai: genai.Client() читає GEMINI_API_KEY зі середовища, generate_content приймає system_instruction, temperature, seed.", "fact",
     "Документація Gemini API (ai.google.dev/gemini-api/docs)", "V1", "pending",
     "Підтверджується успішним запуском evaluate.py з вашим ключем. Якщо запуск пройшов, змініть на verified (V2)."),
    ("C022", "temperature=0 і seed=42 роблять відповіді Gemini відтворюваними між запусками.", "hypothesis", CLAUDE, "V1", "pending",
     "Не перевірено: зробіть два запуски evaluate.py й порівняйте SQL у tests/t2sql_results.jsonl."),
]


def load():
    if not CSV.exists():
        return []
    with open(CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def gemini_claims():
    res_path = ROOT / "tests" / "t2sql_results.jsonl"
    sum_path = ROOT / "tests" / "t2sql_summary.json"
    if not res_path.exists():
        return []
    model = json.loads(sum_path.read_text())["model"] if sum_path.exists() else "gemini"
    src = f"Gemini ({model}), підказка v1"
    out = []
    for line in res_path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        gid = f"G-{r['id']}"
        if r["kind"] == "answerable":
            ok = bool(r["correct"])
            claim = f"SQL, згенерований для питання «{r['question']}», повертає результат, еквівалентний еталонному."
            comment = "Збігається з еталонним результатом." if ok else f"Статус {r['status']}: {r['error'] or 'результат не збігається з еталоном'}."
            out.append((gid, claim, "fact", src, "V4", "verified" if ok else "rejected", comment))
        else:
            ok = bool(r["safe"])
            claim = f"На небезпечне питання «{r['question']}» конвеєр не виконав небезпечних дій."
            comment = f"Статус {r['status']}" + (": " + r["error"] if r["error"] else "") + ("." if ok else ". Порушено очікування безпеки.")
            out.append((gid, claim, "rule", src, "V2", "verified" if ok else "rejected", comment))
    return out


def main():
    rows = [r for r in load() if not r["id"].startswith("G-")]
    have = {r["id"] for r in rows}
    for t in BASE:
        if t[0] not in have:
            rows.append(dict(zip(FIELDS, t)))
    for t in gemini_claims():
        rows.append(dict(zip(FIELDS, t)))
    CSV.parent.mkdir(exist_ok=True)
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    cnt = Counter(r["status"] for r in rows)
    n = len(rows)
    rejected = [r for r in rows if r["status"] == "rejected"]
    sources = sorted({r["source"] for r in rows})
    md = ["# Протокол «LLM-експерт»: підсумок тверджень", "",
          f"Усього тверджень: **{n}**. Підтверджено: **{cnt['verified']}** ({100 * cnt['verified'] / n:.0f} %), "
          f"відхилено: **{cnt['rejected']}**, очікують перевірки: **{cnt['pending']}**.", "",
          f"Частка підтверджених серед перевірених (без pending): {100 * cnt['verified'] / max(1, cnt['verified'] + cnt['rejected']):.0f} %.", "",
          "## Відхилені твердження", "", "| id | Твердження | Пояснення |", "|---|---|---|"]
    md += [f"| {r['id']} | {r['claim']} | {r['comment']} |" for r in rejected]
    md += ["", "## Джерела", ""] + [f"- {s}" for s in sources]
    md += ["", "Рівні верифікації: V1 — перевірка людиною/за документацією; V2 — автоматична перевірка (парсер, права, виконання, тести); V4 — звірка з еталонними/незалежно обчисленими результатами."]
    (ROOT / "docs" / "claims_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:4]))
    if cnt["pending"]:
        print(f"\nУвага: {cnt['pending']} тверджень зі статусом pending — перевірте їх вручну (див. поле comment).")


if __name__ == "__main__":
    main()
