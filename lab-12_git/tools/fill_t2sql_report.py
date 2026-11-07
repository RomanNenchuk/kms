"""Заповнює docs/t2sql_report.md за tests/t2sql_summary.json і tests/t2sql_results.jsonl.
Метрики вставляються точно. У таблиці помилок колонки «що згенерувала модель» й «еталон» точні,
а «причина» і «як виправити» — ЧЕРНЕТКА за евристикою: перевірте й відредагуйте.
Запуск: python tools/fill_t2sql_report.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "t2sql_report.md"
summary = json.loads((ROOT / "tests" / "t2sql_summary.json").read_text())
results = [json.loads(l) for l in (ROOT / "tests" / "t2sql_results.jsonl").read_text(encoding="utf-8").splitlines()]
s = summary


def pct(x):
    return f"{100 * x:.0f} %"


def cell(t, n=320):
    t = (t or "—").replace("\n", " ").replace("|", "\\|")
    return f"`{t[:n]}{'…' if len(t) > n else ''}`" if t != "—" else "—"


def classify(r):
    st, err = r["status"], (r["error"] or "")
    if st == "invalid" and re.search(r"Binder|Catalog|column|table", err, re.I):
        return "вигадана колонка/таблиця", "Додати в підказку точний перелік колонок і приклад JOIN; повторити запит."
    if st == "invalid":
        return "синтаксична/виконавча помилка SQL", "Додати в підказку приклад коректного синтаксису DuckDB; ввести повтор із повідомленням про помилку."
    if st == "blocked":
        return "порушення політики (AST)", "Уточнити правила в підказці; конвеєр правильно заблокував запит."
    if st == "timeout":
        return "завеликий/неефективний запит", "Додати правило про обов'язкові умови JOIN; зменшити складність питання."
    if st == "refused":
        return "хибна відмова моделі", "Уточнити правило REFUSE: аналітичні питання відмовляти не можна."
    return ("пропущений/зайвий фільтр, не та формула метрики або інша форма виводу",
            "Порівняти SQL з еталоном: перевірити фільтри (сезон, хаб, cancelled), формулу метрики та набір колонок; додати приклад у підказку.")


text = REPORT.read_text(encoding="utf-8")

model_line = f"Модель: {s['model']}, temperature 0, seed 42."
text = re.sub(r"<!-- MODEL:START -->.*?<!-- MODEL:END -->", f"<!-- MODEL:START -->{model_line}<!-- MODEL:END -->", text, flags=re.S)

metrics = f"""<!-- METRICS:START -->
| Метрика | Значення |
|---|---|
| Частка правильних (з {s['answerable']} аналітичних) | {pct(s['accuracy'])} |
| Частка виконаних без помилки | {pct(s['executed_ok'])} |
| Частка безпечних (з {s['questions']}) | {pct(s['safe_rate'])} |
| Сирих відповідей заблоковано AST | {s['guard_blocked_raw_outputs']} |
| Відмов моделі (`REFUSE`) | {s['refused_by_model']} |
| Середні токени (вхід / вихід) | {s['avg_prompt_tokens']} / {s['avg_completion_tokens']} |
| Середня затримка, с | {s['avg_latency_s']} |
| Середня вартість запиту, USD | {s['avg_cost_usd']} |
<!-- METRICS:END -->"""
text = re.sub(r"<!-- METRICS:START -->.*?<!-- METRICS:END -->", lambda m: metrics, text, flags=re.S)

wrong = [r for r in results if r["kind"] == "answerable" and not r["correct"]]
rows = []
for i, r in enumerate(wrong[:3], 1):
    cause, fix = classify(r)
    rows.append(f"| {i} | {r['id']}: {r['question']} | {cell(r['sql'] or r['raw_output'])} | {cell(r['reference_sql'])} | {cause} *(чернетка)* | {fix} *(чернетка)* |")
for i in range(len(wrong) + 1, 4):
    rows.append(f"| {i} | — | — | — | — | Помилок менше трьох: додайте складніші питання в tests/t2sql.jsonl і повторіть запуск |")
errors = ("<!-- ERRORS:START -->\n| № | Питання | Що згенерувала модель | Еталон | Причина (категорія) | Як виправити |\n|---|---|---|---|---|---|\n"
          + "\n".join(rows) + "\n<!-- ERRORS:END -->")
text = re.sub(r"<!-- ERRORS:START -->.*?<!-- ERRORS:END -->", lambda m: errors, text, flags=re.S)
REPORT.write_text(text, encoding="utf-8")
print(f"Оновлено {REPORT.name}: метрики; помилок знайдено {len(wrong)} (у таблицю потрапило {min(3, len(wrong))}).")
if len(wrong) < 3:
    print("Помилок менше трьох — додайте складніші питання (синоніми, умови з кількох вимірів) і запустіть evaluate.py знову.")
print("Перевірте колонки «Причина» і «Як виправити»: це евристична чернетка, не висновок.")
