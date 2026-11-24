"""Набір запитів (C1) і наскрізний конвеєр на заглушці: run -> judge -> classify -> sheet -> kappa -> report."""
import csv
import os

import pytest

from sr11 import config as C
from sr11.queries import load_queries, validate


def test_query_set_meets_c1_and_evidence_is_in_corpus():
    qs = load_queries()
    if not C.CORPUS.exists():
        pytest.skip("lab-11 корпус недоступний")
    problems, summary = validate(qs)
    assert not problems, problems
    assert summary["n"] == 20 and len(summary["categories"]) >= 4 and summary["unanswerable_or_harmful"] >= 4


def test_every_query_has_expected_and_checks():
    for q in load_queries():
        assert q["expected"]
        if q["category"] in ("simple", "multistep", "conflict"):
            assert q["checks"]["must_regex"]
        if q["category"] in ("unanswerable", "harmful"):
            assert q["checks"].get("expect")
        if q["fixtures"]:
            assert "СИНТЕТИЧН" in q["note"]            # фікстури завжди позначені як синтетичні


def test_full_pipeline_on_stub(tmp_path, monkeypatch):
    from sr11 import table, report, review
    from sr11.judge import run_judge
    from sr11.runner import run_queries, load_run
    from sr11.stub import StubRAG, stub_judge
    monkeypatch.setattr(C, "RESULTS", C.RESULTS)
    monkeypatch.setattr(C, "LLM_LOG", tmp_path / "llm_log")
    C.set_results_dir(tmp_path)
    monkeypatch.setenv("GEMINI_MODEL", "g")
    monkeypatch.setenv("JUDGE_MODEL", "j")

    qs = load_queries()
    run_queries(StubRAG(qs), qs, sleep=0, printer=lambda *_: None)
    assert len(load_run()) == 20

    # --resume не дублює і не перезаписує
    run_queries(StubRAG(qs), qs, sleep=0, resume=True, printer=lambda *_: None)
    assert len(load_run()) == 20

    run_judge(sleep=0, rpm=10 ** 6, call=stub_judge, printer=lambda *_: None)
    assert all("judge" in r for r in load_run().values() if not r["abstained"])
    assert (tmp_path / "llm_log" / "judge_calls.jsonl").exists()

    rows = table.save(table.build())
    assert len(rows) == 20 and all(r["auto_verdict"] in C.VERDICTS for r in rows)
    assert all(r["auto_cause"] in C.CAUSES + ("—",) for r in rows)

    # ручні правки переживають повторний classify
    with open(tmp_path / "classification.csv", encoding="utf-8-sig", newline="") as f:
        data = list(csv.DictReader(f))
    data[0]["human_verdict"], data[0]["human_cause"] = "частково", "генерація"
    with open(tmp_path / "classification.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=table.COLS)
        w.writeheader()
        w.writerows(data)
    rows = table.save(table.build())
    assert table.final(rows[0]) == ("частково", "генерація")

    # ручна перевірка: аркуш -> заповнення -> κ
    picked = review.make_sheet(8)
    assert len(picked) == 8
    with open(tmp_path / "human_sheet.csv", encoding="utf-8-sig", newline="") as f:
        sheet = list(csv.reader(f))
    for row in sheet[1:]:
        row[5] = "1"
    with open(tmp_path / "human_sheet.csv", "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(sheet)
    k = review.compute_kappa()
    assert k["n"] == 8 and 0 <= k["agreement"] <= 1

    md = report.write()
    for needle in ("Розподіл причин відмов", "Чернетка висновків", "Чернетка плану", "суддя vs людина (n=8)"):
        assert needle in md
    assert md.count("\n1. ") + md.count("\n2. ") + md.count("\n3. ") >= 3            # ≥ 3 спостереження для C3


def test_kappa_requires_five(tmp_path):
    from sr11 import review
    assert review.cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == (1.0, 1.0)
    a, k = review.cohen_kappa([1, 1, 1], [1, 1, 1])
    assert a == 1.0 and k is None                                                       # вироджений розподіл
