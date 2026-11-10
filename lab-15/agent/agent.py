"""Агент: цикл plan -> tool calls -> draft -> verify (цитати) -> відповідь, з трасуванням і лімітами.

  python -m agent.agent "Які рейси зачепив туман у Львові?"
  python -m agent.agent --demo                 # 5 запитань зі scripts/demo_questions.txt (журнал трасування)
  python -m agent.agent --file tests/agent_scenarios.jsonl --level public

Трасування: logs/trace.jsonl (один рядок на запит: кроки, виклики, результати, затримки, токени, вартість).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

from mcp_server import guards
from .llm import GeminiLLM
from .policies import Limits, PRICE_IN, PRICE_OUT
from .tools_client import McpTools

ROOT = Path(__file__).resolve().parent.parent
TRACE = ROOT / "logs" / "trace.jsonl"
PROMPT_PATH = ROOT / "agent" / "prompts" / f"{os.getenv('AGENT_PROMPT', 'system_v2')}.md"
PROMPT_VERSION = PROMPT_PATH.stem
ID_RE = re.compile(r"^(?:graph|kb|sql|cypher):\S+$")
BARE_RE = re.compile(r"\b(?:graph|kb|sql|cypher):[^\s,;)\]`\"'*]+")


def extract_citations(answer: str) -> list[str]:
    """id з квадратних дужок; підтримує і [a], і групи [a, b; c]."""
    out = []
    for grp in re.findall(r"\[([^\[\]]+)\]", answer):
        out += [p.strip().strip("`") for p in re.split(r"[,;]", grp) if ID_RE.match(p.strip().strip("`"))]
    return out


def bare_ids(answer: str) -> list[str]:
    """id поза квадратними дужками (напр. у зворотних лапках): за правилами підказки їх бути не повинно."""
    return BARE_RE.findall(re.sub(r"\[[^\[\]]*\]", " ", answer))


def collect_ids(obj, out: set):
    """Усі id, які повернули інструменти (поля 'id' і 'citation_ids') — дозволені для цитування."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "id" and isinstance(v, str) and ":" in v:
                out.add(v)
            elif k == "citation_ids" and isinstance(v, list):
                out.update(x for x in v if isinstance(x, str))
            else:
                collect_ids(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_ids(v, out)


def verify_citations(answer: str, allowed: set) -> dict:
    """Вузол verify: id у посиланнях мають походити з результатів інструментів, формат лише [id] / [id, id]."""
    abstained = answer.lstrip().upper().startswith("NO_ANSWER")
    cited = sorted(set(extract_citations(answer)))
    invalid = [c for c in cited if c not in allowed]
    bare = [] if abstained else sorted(set(bare_ids(answer)))
    return {"cited": cited, "invalid": invalid, "bare": bare, "abstained": abstained,
            "ok": abstained or (bool(cited) and not invalid and not bare)}


def _short(x, n=300):
    s = json.dumps(x, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + f"...(+{len(s) - n})"


class Agent:
    def __init__(self, llm, tools, limits: Limits | None = None, trace_path: Path = TRACE, prompt_version=None,
                 defenses: bool = True, system_text: str = "", level: str = "public"):
        """defenses=False — лише для виміру «до» (Результат 4): без вихідного фільтра й воріт цитат."""
        self.defenses, self.system_text, self.level = defenses, system_text, level
        self.llm, self.tools, self.limits = llm, tools, limits or Limits()
        self.trace_path, self.prompt_version = trace_path, prompt_version or PROMPT_VERSION

    async def run(self, question: str, tag: str | None = None) -> dict:
        L, t0 = self.limits, time.perf_counter()
        specs = await self.tools.list_tools()
        history = [{"role": "user", "text": question}]
        allowed, steps, used = set(), [], {"prompt": 0, "output": 0, "total": 0}
        n_calls, seen_calls, stop, answer, repaired = 0, {}, "done", "", False

        for step_no in range(1, L.max_steps + 1):
            if time.perf_counter() - t0 > L.max_seconds:
                stop = "time_limit"; break
            if used["total"] > L.max_tokens:
                stop = "token_limit"; break
            ts = time.perf_counter()
            out = await asyncio.to_thread(self.llm.step, history, specs)      # SDK синхронний
            for k in used:
                used[k] += out["usage"].get(k, 0)
            steps.append({"step": step_no, "type": "llm", "calls": [c["name"] for c in out["calls"]],
                          "latency_ms": round(1000 * (time.perf_counter() - ts), 1), "usage": out["usage"]})
            history.append({"role": "model", "text": out["text"], "calls": out["calls"], "raw": out["raw"]})

            if not out["calls"]:
                answer = out["text"].strip()
                v = verify_citations(answer, allowed)
                if self.defenses and not v["ok"] and not repaired and step_no < L.max_steps:   # одна спроба виправлення
                    repaired = True
                    bad = v["invalid"] or (f"id поза квадратними дужками: {v['bare']}" if v["bare"] else "посилань немає")
                    history.append({"role": "user", "text": (
                        f"Перевірка цитат не пройдена ({bad}). Цитуй лише id з результатів інструментів, тільки у "
                        "квадратних дужках, без зворотних лапок; або відповідай `NO_ANSWER: <причина>`.")})
                    steps.append({"step": step_no, "type": "verify", "ok": False, "invalid": v["invalid"]})
                    continue
                steps.append({"step": step_no, "type": "verify", "ok": v["ok"], "invalid": v["invalid"]})
                break

            results = []
            for c in out["calls"]:
                key = c["name"] + json.dumps(c["args"], sort_keys=True, default=str)
                seen_calls[key] = seen_calls.get(key, 0) + 1
                if n_calls >= L.max_tool_calls:
                    resp, stop = {"ok": False, "error": "tool_call_limit"}, "tool_call_limit"
                elif seen_calls[key] > L.max_repeat_call:
                    resp, stop = {"ok": False, "error": "repeated_call_loop"}, "loop_detected"
                else:
                    n_calls += 1
                    tc = time.perf_counter()
                    resp = await self.tools.call(c["name"], c["args"])
                    collect_ids(resp, allowed)
                    raw = json.dumps(resp, ensure_ascii=False, default=str)
                    if len(raw) > L.max_tool_result_chars:
                        resp = {"ok": False, "error": "result_too_large", "detail": f"{len(raw)} символів; звузь запит"}
                steps.append({"step": step_no, "type": "tool", "name": c["name"], "args": c["args"],
                              "ok": resp.get("ok", True), "error": resp.get("error"), "result": _short(resp),
                              "latency_ms": round(1000 * (time.perf_counter() - ts), 1)})
                results.append({"name": c["name"], "response": resp})
            history.append({"role": "tool", "results": results})
            if stop in ("tool_call_limit", "loop_detected"):
                break
        else:
            stop = "step_limit"

        if not answer:                                   # ліміт спрацював до відповіді
            answer = f"NO_ANSWER: перервано ({stop})"
        leaks = guards.output_leak(answer, self.level, self.system_text) if self.defenses else []
        if leaks:                                        # вихідний фільтр: витік підказки / закритих даних
            answer = f"NO_ANSWER: відповідь заблоковано вихідним фільтром ({', '.join(leaks)})"
            stop = "output_blocked"
        v = verify_citations(answer, allowed)
        if self.defenses and not v["ok"]:                # неперевірені цитати не віддаємо користувачу
            answer = f"NO_ANSWER: відповідь не пройшла перевірку цитат ({', '.join(v['invalid'] + v['bare']) or 'немає посилань'})"
            stop = stop if stop != "done" else "citation_failed"
        res = {"run_id": uuid.uuid4().hex[:12], "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tag": tag, "question": question,
               "answer": answer, "abstained": answer.upper().startswith("NO_ANSWER"), "stop_reason": stop,
               "citations": v, "tool_calls": n_calls, "llm_steps": sum(1 for s in steps if s["type"] == "llm"),
               "tools_used": [s["name"] for s in steps if s["type"] == "tool"], "usage": used,
               "cost_usd": round((used["prompt"] * PRICE_IN + used["output"] * PRICE_OUT) / 1e6, 6),
               "latency_s": round(time.perf_counter() - t0, 2), "model": getattr(self.llm, "model", "?"),
               "params": getattr(self.llm, "params", {}), "prompt_version": self.prompt_version, "defenses": self.defenses,
               "output_leaks": leaks, "rejected_tools": getattr(self.tools, "rejected_tools", []),
               "evil_calls": getattr(self.tools, "evil_calls", []), "steps": steps}
        self.trace_path.parent.mkdir(exist_ok=True)
        with open(self.trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False, default=str) + "\n")
        return res


async def amain(args) -> int:
    questions = []
    if args.demo:
        questions = [l.strip() for l in (ROOT / "scripts" / "demo_questions.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    elif args.file:
        questions = [json.loads(l)["question"] for l in Path(args.file).read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.question:
        questions.append(args.question)
    if not questions:
        print("Дайте питання, --demo або --file", file=sys.stderr)
        return 2
    system = PROMPT_PATH.read_text(encoding="utf-8")
    async with McpTools(access_level=args.level, defenses=args.defenses) as tools:
        agent = Agent(GeminiLLM(system), tools, defenses=args.defenses == "on", system_text=system, level=args.level)
        for i, q in enumerate(questions):
            r = await agent.run(q)
            print(f"\nQ: {q}\nA: {r['answer']}\n   [{r['stop_reason']}] кроків LLM={r['llm_steps']} викликів={r['tool_calls']} "
                  f"токенів={r['usage']['total']} {r['latency_s']}s tools={r['tools_used']}")
            if args.sleep and i < len(questions) - 1:
                await asyncio.sleep(args.sleep)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--file")
    ap.add_argument("--level", default="public", choices=["public", "internal", "restricted"])
    ap.add_argument("--defenses", default="on", choices=["on", "off"])
    ap.add_argument("--sleep", type=float, default=4.0, help="пауза між запитами (ліміти free tier)")
    sys.exit(asyncio.run(amain(ap.parse_args())))


if __name__ == "__main__":
    main()
