"""Цикл агента на скриптованому LLM (без мережі): цитати, ліміти, зациклення."""
import asyncio
import json
from agent.agent import Agent, verify_citations
from agent.llm import FakeLLM
from agent.policies import Limits


class FakeTools:
    async def list_tools(self):
        return [{"name": "graph_lookup", "description": "", "schema": {"type": "object"}, "read_only": True}]

    async def call(self, name, args):
        return {"ok": True, "found": True, "nodes": [{"id": "graph:Airport:LWO"}], "citation_ids": ["graph:Airport:LWO"]}


def run(script, limits=None, tmp=None):
    ag = Agent(FakeLLM(script), FakeTools(), limits or Limits(), trace_path=tmp)
    return asyncio.run(ag.run("питання"))


def test_verify_citations():
    assert verify_citations("Є [graph:Airport:LWO]", {"graph:Airport:LWO"})["ok"]
    assert not verify_citations("Є [graph:Airport:XXX]", {"graph:Airport:LWO"})["ok"]
    assert not verify_citations("Без посилань", {"graph:Airport:LWO"})["ok"]
    assert verify_citations("NO_ANSWER: немає даних", set())["ok"]


def test_happy_path_and_trace(tmp_path):
    t = tmp_path / "trace.jsonl"
    r = run([{"calls": [{"name": "graph_lookup", "args": {"entity": "LWO"}}]},
             {"text": "Аеропорт є [graph:Airport:LWO]."}], tmp=t)
    assert r["citations"]["ok"] and r["tool_calls"] == 1 and r["stop_reason"] == "done"
    rec = json.loads(t.read_text().splitlines()[0])
    assert [s["type"] for s in rec["steps"]] == ["llm", "tool", "llm", "verify"]


def test_fabricated_citation_is_withheld(tmp_path):
    r = run([{"calls": [{"name": "graph_lookup", "args": {"entity": "LWO"}}]},
             {"text": "Так [graph:Airport:ZZZ]."}, {"text": "Все одно [graph:Airport:ZZZ]."}], tmp=tmp_path / "t.jsonl")
    assert r["abstained"] and r["stop_reason"] == "citation_failed"


def test_loop_detection(tmp_path):
    call = {"calls": [{"name": "graph_lookup", "args": {"entity": "LWO"}}]}
    r = run([call] * 10, tmp=tmp_path / "t.jsonl")
    assert r["stop_reason"] == "loop_detected" and r["abstained"]


def test_step_limit(tmp_path):
    scripts = [{"calls": [{"name": "graph_lookup", "args": {"entity": str(i)}}]} for i in range(10)]
    r = run(scripts, Limits(max_steps=3, max_tool_calls=99), tmp=tmp_path / "t.jsonl")
    assert r["stop_reason"] == "step_limit" and r["llm_steps"] == 3


def test_grouped_and_bare_citations():
    from agent.agent import extract_citations, bare_ids
    allowed = {"kb:a#1", "kb:b#2"}
    assert extract_citations("Так [kb:a#1, kb:b#2]; ще [sql:x1]") == ["kb:a#1", "kb:b#2", "sql:x1"]
    assert verify_citations("Так [kb:a#1, kb:b#2].", allowed)["ok"]
    fab = verify_citations("Так [kb:a#1, kb:ЗМІШАНО#9].", allowed)          # вигаданий id у групі раніше не перевірявся
    assert not fab["ok"] and fab["invalid"] == ["kb:ЗМІШАНО#9"]
    bare = verify_citations("Рейс `graph:Flight:CA101-20261102` є [kb:a#1].", allowed)
    assert not bare["ok"] and bare["bare"] == ["graph:Flight:CA101-20261102"]
    assert bare_ids("все ок [graph:Risk:RK01]") == []
