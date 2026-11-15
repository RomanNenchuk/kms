"""Сценарні тести агента (Результат 3): прогін tests/agent_scenarios.jsonl, перевірка очікувань, метрики.

  python -m agent.evaluate --label baseline --sleep 4                 # прогін -> tests/agent_results_baseline.jsonl
  python -m agent.evaluate --label fixed --ids s01,u02                # лише вибрані сценарії
  python -m agent.evaluate --compare baseline fixed                   # таблиця «до / після» (для C4)
  python -m agent.evaluate --label baseline --md                      # додатково вивести таблицю для docs/agent_eval.md

Формат сценарію (один JSON на рядок), усі поля, окрім id / kind / question, необов'язкові:
  kind: success | unknown | conflict      expected_tools: [..] (мають бути викликані)    forbidden_tools: [..]
  numbers: [..] (кожне число є у відповіді, допуск 0.06 або 0.1%)   contains_all / contains_any / not_contains: [..]
  must_cite_prefix: ["sql:", ...] (є хоч одне цитування з таким префіксом)   expect_abstain: true|false
  allowed_flight_ids: [..] (усі згадані id рейсів мають належати цьому набору)
  flag_conflict: true (у відповіді є слова про розбіжність)   requires_neo4j: true   level: public|internal|restricted
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from .agent import Agent, PROMPT_PATH, ROOT
from .llm import GeminiLLM
from .tools_client import McpTools

SCEN = ROOT / "tests" / "agent_scenarios.jsonl"
BARE_RE = re.compile(r"\b(?:graph|kb|sql|cypher):[^\s,;)\]`\"'*]+")
FLIGHT_RE = re.compile(r"\b[A-Z]{2}\d{3}-\d{8}\b")
CONFLICT_WORDS = ["розбіж", "відрізня", "не збіга", "не співпад", "різн", "не однаков", "суперечн"]


def load_scenarios(path=SCEN):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def numbers_in(text: str) -> list[float]:
    t = text.replace(" ", " ")
    t = re.sub(r"(?<=\d)[ ](?=\d{3}\b)", "", t)                 # «5 000» -> «5000»
    return [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", t)]


def has_number(text: str, target: float) -> bool:
    tol = max(0.06, abs(target) * 0.001)
    return any(abs(x - target) <= tol for x in numbers_in(text))


def bare_ids(text: str) -> list[str]:
    """id джерел поза квадратними дужками (наприклад, у зворотних лапках): перевірка цитат їх не бачить."""
    return BARE_RE.findall(re.sub(r"\[[^\[\]]*\]", " ", text))


def check_scenario(sc: dict, res: dict) -> dict:
    """Повертає {check: bool}; сценарій пройдено, якщо всі перевірки True."""
    ans, low = res["answer"], res["answer"].lower()
    ch = {"stop_ok": res["stop_reason"] == "done"}
    ch["abstain"] = res["abstained"] == bool(sc.get("expect_abstain", False))
    if sc.get("expected_tools"):
        ch["tools"] = set(sc["expected_tools"]) <= set(res["tools_used"])
    if sc.get("forbidden_tools"):
        ch["no_forbidden_tools"] = not (set(sc["forbidden_tools"]) & set(res["tools_used"]))
    if sc.get("numbers"):
        ch["numbers"] = all(has_number(ans, n) for n in sc["numbers"])
    if sc.get("contains_all"):
        ch["contains_all"] = all(s.lower() in low for s in sc["contains_all"])
    if sc.get("contains_any"):
        ch["contains_any"] = any(s.lower() in low for s in sc["contains_any"])
    if sc.get("not_contains"):
        ch["not_contains"] = not any(s.lower() in low for s in sc["not_contains"])
    if sc.get("must_cite_prefix"):
        cited = res["citations"]["cited"]
        ch["cite_prefix"] = all(any(c.startswith(p) for c in cited) for p in sc["must_cite_prefix"])
    if sc.get("flag_conflict"):
        ch["flags_conflict"] = any(w in low for w in CONFLICT_WORDS)
    if sc.get("allowed_flight_ids"):          # не називати рейси, яких немає в очікуваному наборі
        ch["only_expected_flights"] = set(FLIGHT_RE.findall(ans)) <= set(sc["allowed_flight_ids"])
    ch["cite_format"] = not bare_ids(ans)
    ch["citations_ok"] = res["citations"]["ok"]
    return ch


def summarize(rows: list[dict]) -> dict:
    run = [r for r in rows if not r.get("skipped")]
    n = len(run)
    if not n:
        return {"scenarios": 0}
    by_kind = {}
    for r in run:
        k = by_kind.setdefault(r["kind"], [0, 0])
        k[0] += r["passed"]; k[1] += 1
    avg = lambda key: round(sum(r[key] for r in run) / n, 2)
    return {"scenarios": n, "skipped": len(rows) - n, "passed": sum(r["passed"] for r in run),
            "success_rate": round(sum(r["passed"] for r in run) / n, 3),
            "by_kind": {k: f"{a}/{b}" for k, (a, b) in by_kind.items()},
            "avg_llm_steps": avg("llm_steps"), "avg_tool_calls": avg("tool_calls"),
            "avg_tokens": avg("tokens"), "avg_latency_s": avg("latency_s"),
            "total_cost_usd": round(sum(r["cost_usd"] for r in run), 6)}


def md_table(rows: list[dict]) -> str:
    out = ["| id | вид | пройдено | кроків LLM | викликів | токенів | невдалі перевірки |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("skipped"):
            out.append(f"| {r['id']} | {r['kind']} | пропущено ({r['skipped']}) | | | | |")
            continue
        bad = ", ".join(k for k, v in r["checks"].items() if not v) or "—"
        out.append(f"| {r['id']} | {r['kind']} | {'так' if r['passed'] else 'НІ'} | {r['llm_steps']} | {r['tool_calls']} | {r['tokens']} | {bad} |")
    return "\n".join(out)


async def run_all(scenarios, llm_factory, level_default="public", defenses="on", sleep=0.0, trace=None):
    rows, by_level = [], {}
    for sc in scenarios:
        by_level.setdefault(sc.get("level", level_default), []).append(sc)
    neo = bool(os.getenv("NEO4J_PASSWORD"))
    for level, group in by_level.items():
        async with McpTools(access_level=level, defenses=defenses) as tools:
            agent = Agent(llm_factory(), tools, trace_path=trace) if trace else Agent(llm_factory(), tools)
            for sc in group:
                base = {"id": sc["id"], "kind": sc["kind"], "question": sc["question"], "level": level}
                if sc.get("requires_neo4j") and not neo:
                    rows.append({**base, "skipped": "потрібен Neo4j"}); continue
                try:
                    res = await agent.run(sc["question"], tag=sc["id"])
                except Exception as e:          # збій LLM/API не має обривати весь прогін
                    print(f"[ERR] {sc['id']:4} {sc['kind']:8} ВИНЯТОК: {type(e).__name__}: {str(e)[:200]}", flush=True)
                    rows.append({**base, "passed": False, "checks": {"no_exception": False}, "answer": "", "tools_used": [],
                                 "stop_reason": "exception", "error": f"{type(e).__name__}: {str(e)[:300]}", "llm_steps": 0,
                                 "tool_calls": 0, "tokens": 0, "latency_s": 0.0, "cost_usd": 0.0, "run_id": None})
                    continue
                ch = check_scenario(sc, res)
                rows.append({**base, "passed": all(ch.values()), "checks": ch, "answer": res["answer"],
                             "tools_used": res["tools_used"], "stop_reason": res["stop_reason"],
                             "llm_steps": res["llm_steps"], "tool_calls": res["tool_calls"], "tokens": res["usage"]["total"],
                             "latency_s": res["latency_s"], "cost_usd": res["cost_usd"], "run_id": res["run_id"]})
                mark = "OK " if rows[-1]["passed"] else "ERR"
                print(f"[{mark}] {sc['id']:4} {sc['kind']:8} кроків={res['llm_steps']} викликів={res['tool_calls']} "
                      f"{'' if rows[-1]['passed'] else [k for k, v in ch.items() if not v]}", flush=True)
                if sleep:
                    await asyncio.sleep(sleep)
    order = {sc["id"]: i for i, sc in enumerate(scenarios)}
    return sorted(rows, key=lambda r: order[r["id"]])


def compare(a: str, b: str):
    ra = {r["id"]: r for r in map(json.loads, (ROOT / "tests" / f"agent_results_{a}.jsonl").read_text(encoding="utf-8").splitlines())}
    rb = {r["id"]: r for r in map(json.loads, (ROOT / "tests" / f"agent_results_{b}.jsonl").read_text(encoding="utf-8").splitlines())}
    sa, sb = summarize(list(ra.values())), summarize(list(rb.values()))
    print(f"| метрика | {a} | {b} |\n|---|---|---|")
    for k in ("scenarios", "passed", "success_rate", "avg_llm_steps", "avg_tool_calls", "avg_tokens", "avg_latency_s", "total_cost_usd"):
        print(f"| {k} | {sa.get(k)} | {sb.get(k)} |")
    changed = [i for i in ra if i in rb and ra[i].get("passed") != rb[i].get("passed")]
    print("\nЗмінилися сценарії:", ", ".join(f"{i}: {'так' if ra[i].get('passed') else 'НІ'} → {'так' if rb[i].get('passed') else 'НІ'}" for i in changed) or "—")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--file", default=str(SCEN))
    ap.add_argument("--ids", help="через кому")
    ap.add_argument("--defenses", default="on", choices=["on", "off"])
    ap.add_argument("--sleep", type=float, default=4.0)
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    a = ap.parse_args()
    if a.compare:
        return compare(*a.compare)
    sc = load_scenarios(a.file)
    if a.ids:
        want = set(a.ids.split(","))
        sc = [s for s in sc if s["id"] in want]
    system = PROMPT_PATH.read_text(encoding="utf-8")
    t0 = time.time()
    rows = asyncio.run(run_all(sc, lambda: GeminiLLM(system), defenses=a.defenses, sleep=a.sleep,
                               trace=ROOT / "logs" / f"trace_eval_{a.label}.jsonl"))
    out = ROOT / "tests" / f"agent_results_{a.label}.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    s = summarize(rows)
    (ROOT / "tests" / f"agent_summary_{a.label}.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + json.dumps(s, ensure_ascii=False, indent=2), f"\n({round(time.time() - t0)} с) -> {out}")
    if a.md:
        print("\n" + md_table(rows))
    fails = [r for r in rows if not r.get("skipped") and not r["passed"]]
    if fails:
        print("\n=== Невдалі сценарії (матеріал для аналізу) ===")
        for r in fails:
            print(f"\n[{r['id']}] {r['question']}\nневдалі перевірки: {[k for k, v in r['checks'].items() if not v]}  інструменти: {r['tools_used']}  stop: {r['stop_reason']}\nвідповідь: {r['answer'][:400]}")


if __name__ == "__main__":
    main()
