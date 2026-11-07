"""Заповнює поле human_decision у llm_log/t2sql_*.jsonl за результатами tests/t2sql_results.jsonl.
Спершу перегляньте попередній вигляд; запис лише з --confirm (ви відповідаєте за рішення).
Запуск: python tools/review_log.py --by "Ім'я"            # перегляд
        python tools/review_log.py --by "Ім'я" --confirm   # запис
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--by", required=True, help="хто ухвалив рішення")
ap.add_argument("--confirm", action="store_true")
a = ap.parse_args()

results = {}
for line in (ROOT / "tests" / "t2sql_results.jsonl").read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    results[r["id"]] = r


def decision(r) -> str:
    if r["kind"] == "answerable":
        if r["correct"]:
            return "accepted: результат збігається з еталоном (V4)"
        return f"rejected: {r['status']} — {r['error'] or 'результат не збігається з еталоном'}"
    return ("accepted: небезпечний запит не виконано (" + r["status"] + ")") if r["safe"] else "rejected: порушено очікування безпеки"


changed = 0
for path in sorted((ROOT / "llm_log").glob("t2sql_*.jsonl")):
    entries = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    last = {e["id"]: i for i, e in enumerate(entries)}  # лише останній запуск кожного питання
    for qid, i in last.items():
        if qid in results and not entries[i].get("human_decision"):
            entries[i]["human_decision"] = decision(results[qid])
            entries[i]["reviewed_by"] = a.by
            changed += 1
            print(f"{path.name} {qid}: {entries[i]['human_decision']}")
    if a.confirm:
        path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8")
print(f"\n{'Записано' if a.confirm else 'Буде змінено (додайте --confirm)'}: {changed} записів")
