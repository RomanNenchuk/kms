"""Офлайн-тести перевіряльника сценаріїв і всього конвеєра evaluate на скриптованому LLM."""
import asyncio
import json
from agent import evaluate as ev
from agent.llm import FakeLLM


def res(answer, tools=("query_metric",), cited=("sql:ab",), abstained=False, stop="done", ok=True):
    return {"answer": answer, "abstained": abstained, "tools_used": list(tools), "stop_reason": stop,
            "citations": {"cited": list(cited), "invalid": [], "ok": ok}}


def test_numbers_parsing():
    assert ev.has_number("Весна — 63,43%, зима 51.8%", 63.43)
    assert ev.has_number("Весна — 63,4%", 63.43)                 # округлення в межах допуску
    assert ev.has_number("Усього 5 000 рейсів", 5000)
    assert not ev.has_number("Весна — 60%", 63.43)


def test_check_success_pass_and_fail():
    sc = {"expected_tools": ["query_metric"], "numbers": [27.78], "must_cite_prefix": ["sql:"]}
    ok = ev.check_scenario(sc, res("Лоукост 27,78 хв [sql:ab]"))
    assert all(ok.values())
    bad = ev.check_scenario(sc, res("Лоукост 30 хв [sql:ab]"))
    assert bad["numbers"] is False
    wrong_tool = ev.check_scenario(sc, res("27,78 [sql:ab]", tools=("vector_search",)))
    assert wrong_tool["tools"] is False


def test_check_unknown_and_leak():
    sc = {"expect_abstain": True, "not_contains": ["Oleh Nowak"]}
    assert all(ev.check_scenario(sc, res("NO_ANSWER: немає даних", abstained=True, cited=())).values())
    leaked = ev.check_scenario(sc, res("Oleh Nowak був у рейсі", abstained=False))
    assert leaked["abstain"] is False and leaked["not_contains"] is False


def test_check_conflict_flag():
    sc = {"flag_conflict": True}
    assert ev.check_scenario(sc, res("У графі 288, у кубі 5000: цифри відрізняються"))["flags_conflict"]
    assert not ev.check_scenario(sc, res("Усього 5000"))["flags_conflict"]


def test_summarize_and_pipeline(tmp_path, monkeypatch):
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    scenarios = [
        {"id": "t1", "kind": "success", "question": "q1", "expected_tools": ["graph_lookup"], "must_cite_prefix": ["graph:"]},
        {"id": "t2", "kind": "unknown", "question": "q2", "expect_abstain": True},
        {"id": "t3", "kind": "conflict", "question": "q3", "requires_neo4j": True},
    ]
    script = [{"calls": [{"name": "graph_lookup", "args": {"entity": "LWO"}}]}, {"text": "Є аеропорт [graph:Airport:LWO]."},
              {"text": "NO_ANSWER: немає даних"}]
    llm = FakeLLM(script)
    import agent.agent as ag
    monkeypatch.setattr(ag, "TRACE", tmp_path / "t.jsonl")
    rows = asyncio.run(ev.run_all(scenarios, lambda: llm, trace=tmp_path / "t.jsonl"))
    assert [r["id"] for r in rows] == ["t1", "t2", "t3"]
    assert rows[2].get("skipped")
    s = ev.summarize(rows)
    assert s["scenarios"] == 2 and s["skipped"] == 1 and s["success_rate"] == 1.0
    assert "| t1 |" in ev.md_table(rows)


def test_bare_ids_and_cite_format():
    assert ev.bare_ids("рейс `graph:Flight:CA101-20261102` і [graph:Risk:RK01]") == ["graph:Flight:CA101-20261102"]
    assert ev.bare_ids("все в дужках [graph:Flight:CA101-20261102, kb:x#1]") == []
    bad = ev.check_scenario({}, res("рейс graph:Flight:CA101-20261102 зачеплений"))
    assert bad["cite_format"] is False


def test_allowed_flights():
    sc = {"allowed_flight_ids": ["CA101-20261102"]}
    assert ev.check_scenario(sc, res("Є [graph:Flight:CA101-20261102]"))["only_expected_flights"]
    assert not ev.check_scenario(sc, res("Є SU111-20261102"))["only_expected_flights"]
