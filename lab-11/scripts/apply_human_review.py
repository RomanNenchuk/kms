#!/usr/bin/env python3
"""Переносить РЕАЛЬНІ оцінки з eval/human_sheet.csv у поле human_decision журналу llm_log/rag_calls.jsonl.

1) Записи, де human_decision стоїть без звірки з текстом (verified_against_text != true), скидаються в null.
2) Для відповідей з аркуша (human_faithful = 0/1) human_decision заповнюється з verified_against_text = true.
Резервна копія журналу: rag_calls.jsonl.bak. Запуск: python scripts/apply_human_review.py [--dry-run]
"""
import csv, json, sys, shutil, datetime as dt, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "llm_log" / "rag_calls.jsonl"
RES = ROOT / "eval" / "rag_eval_results.jsonl"
SHEET = ROOT / "eval" / "human_sheet.csv"


def main(dry):
    rid2req = {}
    for line in open(RES, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            rid2req[r["id"]] = r["request_id"]
    review = {}
    with open(SHEET, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            col = next((k for k in row if k and k.startswith("human_faithful")), None)
            v = (row.get(col) or "").strip() if col else ""
            if v in ("0", "1") and row["id"] in rid2req:
                review[rid2req[row["id"]]] = (row["id"], int(v), (row.get("human_note") or "").strip())
    if not review:
        sys.exit("В eval/human_sheet.csv немає заповнених оцінок human_faithful (0/1).")

    out, reset, applied = [], 0, 0
    today = dt.date.today().isoformat()
    for line in open(LOG, encoding="utf-8"):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            out.append(line.rstrip("\n"))                  # пошкоджений рядок лишаємо як є
            continue
        hd = rec.get("human_decision")
        if hd and not (isinstance(hd, dict) and hd.get("verified_against_text") is True):
            rec["human_decision"] = None
            reset += 1
        if rec.get("request_id") in review:
            tid, v, note = review[rec["request_id"]]
            rec["human_decision"] = {"decision": "accepted" if v == 1 else "rejected", "comment": note,
                                     "verified_against_text": True, "reviewer": "author", "date": today, "test_id": tid}
            applied += 1
        out.append(json.dumps(rec, ensure_ascii=False) if isinstance(rec, dict) else line)
    print(f"скинуто неперевірених рішень: {reset} | застосовано оцінок з аркуша: {applied} з {len(review)}")
    if dry:
        print("--dry-run: файл не змінено")
        return
    shutil.copy(LOG, str(LOG) + ".bak")
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"записано {LOG} (копія: {LOG.name}.bak)")


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
