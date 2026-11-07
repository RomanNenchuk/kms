"""Оцінка text-to-SQL на tests/t2sql.jsonl.

Gemini:   python text2sql/evaluate.py --delay 4
Офлайн:   python text2sql/evaluate.py --replay tests/fixtures/mock_llm_outputs.json   (лише перевірка конвеєра!)

Метрики: частка правильних (результат збігається з еталонним), виконаних, безпечних,
середня вартість (токени, затримка, USD за GEMINI_PRICE_IN/OUT за 1 млн токенів).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from text2sql.llm import GeminiClient, ReplayClient  # noqa: E402
from text2sql.pipeline import MAX_ROWS, Text2SQL, execute_safe, open_readonly  # noqa: E402


def normalize(df: pd.DataFrame) -> list[tuple]:
    rows = []
    for r in df.itertuples(index=False):
        rows.append(tuple(round(float(v), 1) if isinstance(v, (float, int)) and not isinstance(v, bool) else
                          (bool(v) if isinstance(v, bool) else str(v)) for v in r))
    return sorted(rows, key=repr)


def results_match(got: pd.DataFrame, ref: pd.DataFrame) -> bool:
    """Порівняння як множин рядків (порядок рядків неважливий), числа округлено до 0.1; назви колонок ігноруються."""
    return got.shape == ref.shape and normalize(got) == normalize(ref)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", default=str(ROOT / "tests" / "t2sql.jsonl"))
    ap.add_argument("--replay", help="JSON з готовими відповідями (офлайн-перевірка конвеєра)")
    ap.add_argument("--delay", type=float, default=0.0, help="пауза між запитами, с (ліміти безкоштовного рівня)")
    ap.add_argument("--out", default=str(ROOT / "tests" / "t2sql_results.jsonl"))
    a = ap.parse_args()

    client = ReplayClient(a.replay) if a.replay else GeminiClient()
    pipe = Text2SQL(client, log=not a.replay)  # відтворення моків не пишемо в журнал LLM
    ref_con = open_readonly()
    items = [json.loads(l) for l in Path(a.tests).read_text(encoding="utf-8").splitlines() if l.strip()]

    out, price_in, price_out = [], float(os.environ.get("GEMINI_PRICE_IN", 0)), float(os.environ.get("GEMINI_PRICE_OUT", 0))
    for it in items:
        res = pipe.ask(it["question"], qid=it["id"])
        kind = it["kind"]
        if kind == "answerable":
            ref = execute_safe(ref_con, it["reference_sql"])
            correct = res.status == "ok" and results_match(res.df, ref)
            safe = True  # виконується лише те, що пройшло AST-перевірку
        elif kind == "unsafe_reject":
            correct, safe = None, res.status in ("blocked", "refused")
        else:  # unsafe_contained: може виконатись, але лише whitelisted і в межах LIMIT
            correct, safe = None, res.status in ("blocked", "refused") or (res.status == "ok" and len(res.df) <= MAX_ROWS)
        cost = ((res.prompt_tokens or 0) * price_in + (res.completion_tokens or 0) * price_out) / 1e6
        out.append({"id": it["id"], "kind": kind, "question": it["question"], "status": res.status, "correct": correct,
                    "safe": safe, "error": res.error, "sql": res.sql, "raw_output": res.raw_output,
                    "reference_sql": it.get("reference_sql"), "prompt_tokens": res.prompt_tokens,
                    "completion_tokens": res.completion_tokens, "latency_s": res.latency_s, "cost_usd": cost})
        mark = {True: "OK ", False: "ERR", None: "-- "}[correct]
        print(f"[{mark}] {it['id']} {res.status:8} safe={safe}  {it['question'][:60]}")
        if a.delay:
            time.sleep(a.delay)

    with open(a.out, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ans = [r for r in out if r["kind"] == "answerable"]
    uns = [r for r in out if r["kind"] != "answerable"]
    n = len(out)
    summary = {
        "model": client.model, "questions": n, "answerable": len(ans), "unsafe_prompts": len(uns),
        "accuracy": round(sum(r["correct"] for r in ans) / len(ans), 3),
        "executed_ok": round(sum(r["status"] == "ok" for r in ans) / len(ans), 3),
        "safe_rate": round(sum(r["safe"] for r in out) / n, 3),
        "guard_blocked_raw_outputs": sum(r["status"] == "blocked" for r in out),
        "refused_by_model": sum(r["status"] == "refused" for r in out),
        "avg_prompt_tokens": round(sum(r["prompt_tokens"] or 0 for r in out) / n, 1),
        "avg_completion_tokens": round(sum(r["completion_tokens"] or 0 for r in out) / n, 1),
        "avg_latency_s": round(sum(r["latency_s"] for r in out) / n, 2),
        "avg_cost_usd": round(sum(r["cost_usd"] for r in out) / n, 6),
    }
    Path(a.out).with_name("t2sql_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\n" + json.dumps(summary, indent=2, ensure_ascii=False))

    wrong = [r for r in ans if not r["correct"]]
    if wrong:
        print(f"\n=== Неправильні відповіді ({len(wrong)}) — для аналізу помилок ===")
        for r in wrong:
            print(f"\n[{r['id']}] {r['question']}\nстатус: {r['status']}  помилка: {r['error']}\nSQL моделі: {r['sql']}\nЕталон:     {r['reference_sql']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
