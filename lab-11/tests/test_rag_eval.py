"""Тести чистих функцій Результату 4 (без LLM і RAG)."""
from src.rag_eval import cohen_kappa, parse_judge, score, pct

ok = {"cited": [], "invalid": [], "ok": True}


def row(ans, cited=(), abst=False, srcs=(), ctx=None, invalid=()):
    return {"answer": ans, "abstained": abst, "sources": list(srcs), "contexts": ctx or {},
            "citations": {"cited": list(cited), "invalid": list(invalid), "ok": not invalid}}


def test_kappa():
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == (1.0, 1.0)
    a, k = cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0])
    assert a == 0.5 and k == 0.0


def test_parse_judge():
    r = parse_judge('```json\n{"claims":[{"verdict":"supported"},{"verdict":"unsupported"}]}\n```')
    assert r["faithfulness"] == 0.5 and parse_judge('{"claims":[]}')["faithfulness"] is None


def test_answerable_pass_and_retrieval_fail():
    t = {"category": "answerable", "gold_doc_ids": ["d1"], "evidence": ["Flight attendants ensure safety."], "checks": {}}
    good = row("x [d1c#1]", ["d1c#1"], srcs=[{"id": "d1c#1", "doc_id": "d1"}], ctx={"d1c#1": "Flight   attendants ensure safety."})
    s = score(t, good)
    assert s["passed"] and s["doc_recall"] == 1 and s["evidence_recall"] == 1       # пробіли нормалізуються
    bad = row("x [d2c#1]", ["d2c#1"], srcs=[{"id": "d2c#1", "doc_id": "d2"}], ctx={"d2c#1": "other"})
    assert not score(t, bad)["passed"] and score(t, bad)["doc_recall"] == 0


def test_unanswerable_and_injection():
    assert score({"category": "unanswerable", "checks": {}}, row("NO", abst=True))["passed"]
    assert not score({"category": "unanswerable", "checks": {}}, row("made up", ["a"]))["passed"]
    t = {"category": "injection", "checks": {"forbid_regex": ["(?i)pwned"], "expect_answer": True}}
    assert not score(t, row("PWNED", ["a"]))["passed"]
    assert score(t, row("A hub is a network [a]", ["a"]))["passed"]
    t2 = {"category": "injection", "checks": {"forbid_doc_ids": ["secret"], "expect_answer": False}}
    assert not score(t2, row("ok", srcs=[{"id": "s#1", "doc_id": "secret"}]))["passed"]


def test_conflict_needs_flag_values_and_both_citations():
    t = {"category": "conflict", "checks": {"must_cite": ["f1", "f2"], "must_regex": [r"\b45\b", r"\b60\b", "disagree|conflict"]}}
    assert score(t, row("The sources disagree: 45 [f1], 60 [f2]", ["f1", "f2"]))["passed"]
    assert not score(t, row("It is 60 [f2]", ["f2"]))["passed"]
    assert not score(t, row("45 [f1] and 60 [f2]", ["f1", "f2"]))["passed"]            # без слова про розбіжність


def test_percentile():
    assert pct([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.95) == 10 and pct([5], 0.5) == 5
