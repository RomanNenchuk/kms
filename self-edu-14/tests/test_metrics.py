import json
import pandas as pd
import pytest
from src import store, measure
from src.metrics import Ctx, q1, q2, q3, q4, q7, q8, q5, q6

CFG = {"reference_date": "2026-11-14"}


def ctx(tables=None, corpus=None):
    return Ctx(tables or {}, corpus or [], CFG)


def df(rows, cols):
    return pd.DataFrame(rows, columns=cols, dtype=str)


def test_q1_completeness_by_hand():
    cols = ["id", "a", "b"]
    t = {k: df([["1", "x", "y"], ["2", "", "y"]], cols) for k in ["flights", "aircraft", "pilots", "passengers", "airports", "delays", "risks"]}
    v, n, bad, _, _ = q1(ctx(t), {})
    assert (n, bad) == (42, 7) and v == pytest.approx(35 / 42)


def test_q2_provenance_by_hand():
    cols = ["startId", "endId", "source", "confidence", "validFrom"]
    t = {k: df([["a", "b", "s", "0.9", "2026-01-01"]], cols) for k in store.RELS}
    t["rel_has_pilot"] = df([["a", "b", "s", "0.9", "2026-01-01"], ["a", "c", "", "0.9", "2026-01-01"]], cols)
    v, n, bad, _, _ = q2(ctx(t), {})
    assert (n, bad) == (15, 1) and v == pytest.approx(14 / 15)


def test_q3_functional_by_hand():
    cols = ["startId", "endId"]
    t = {r: df([["F1", "A"], ["F2", "A"]], cols) for r in ["rel_operated_by", "rel_uses_aircraft", "rel_departs_from", "rel_arrives_at", "rel_owned_by", "rel_located_in", "rel_in_country"]}
    t["rel_operated_by"] = df([["F1", "A"], ["F1", "B"], ["F2", "A"]], cols)      # F1 має двох операторів
    v, n, bad, ex, _ = q3(ctx(t), {})
    assert (n, bad) == (14, 1) and "F1" in ex[0]


def test_q4_freshness_by_hand():
    corpus = [{"doc_id": "a", "date": "2026-10-31"}, {"doc_id": "b", "date": "2025-03-12"}, {"doc_id": "c", "date": "2025-11-14"}, {"doc_id": "d", "date": "2025-11-13"}]   # поріг: 2025-11-14 включно
    v, n, bad, _, _ = q4(ctx(corpus=corpus), {"max_age_days": 365})
    assert (n, bad) == (4, 2) and v == 0.5


def test_q8_metadata_by_hand():
    ok = {"chunk_id": "a", "sensitivity": "public", "source_url": "https://x.org", "text": "t"}
    bad = [{**ok, "chunk_id": "b", "sensitivity": "secret"}, {**ok, "chunk_id": "c", "source_url": "ftp://x"}, {**ok, "chunk_id": "d", "text": "  "}]
    v, n, nb, ex, _ = q8(ctx(corpus=[ok] + bad), {})
    assert (n, nb) == (4, 3) and sorted(ex) == ["b", "c", "d"]


def test_q5_q6_duplicates_by_hand():
    t = {"passengers": df([["P1", "Olena Kovalenko"], ["P2", "Kovalenko Olena"], ["P3", "Ivan Petrenko"]], ["passengerId", "name"]),
         "pilots": df([["K1", "Taras Bondar"]], ["pilotId", "name"]),
         "airports": df([["LWO", "Lviv International Airport"]], ["iata", "name"]),
         "aircraft": df([["UR-ABC"], ["URABC"], ["UR-XYZ"]], ["registration"])}
    v, n, bad, _, _ = q5(ctx(t), {})
    assert n == 8 and bad == 2                                   # P1~P2 і UR-ABC~URABC
    corpus = [{"doc_id": "a", "text": "Air cargo is any property carried in an aircraft"}, {"doc_id": "b", "text": "Air cargo is any property carried in an aircraft"},
              {"doc_id": "c", "text": "Runway markings indicate the touchdown zone"}]
    v, n, bad, _, _ = q6(ctx(corpus=corpus), {})
    assert (n, bad) == (3, 1)


def test_q7_ranges_by_hand():
    t = {"pilots": df([["1", "100"], ["2", "-5"]], ["pilotId", "flightHours"]), "delays": df([["d", "9999"]], ["delayId", "minutes"]),
         "risks": df([["r", "7"]], ["riskId", "level"]),
         "aircraft": df([["R1", "Airbus A320", "180"], ["R2", "Boeing 737-800F", "0"], ["R3", "Airbus A320", "0"]], ["registration", "model", "seatCapacity"]),
         "flights": df([["f", "2026-11-02", "2026-11-02T05:15:00"]], ["flightId", "date", "scheduledDeparture"])}
    for r in store.RELS:
        t[r] = df([["a", "b", "2026-11-02"]], ["startId", "endId", "validFrom"])
    v, n, bad, ex, _ = q7(ctx(t), {})
    assert bad == 4 and any("flightHours" in e for e in ex) and any("R3" in e for e in ex) and not any("R2" in e for e in ex)


def test_history_does_not_duplicate_same_data(tmp_path, monkeypatch):
    monkeypatch.setattr(measure, "HIST", tmp_path / "h.jsonl")
    res = {"variant": "clean", "measured": "2026-11-25T10:00:00+02:00", "data_sha256": "abc", "summary": {}, "metrics": [{"id": "Q1", "value": 1.0}]}
    assert measure.record(res) is True and measure.record(res) is False
    assert measure.record({**res, "data_sha256": "def"}) is True
    assert len(measure.read_history()) == 2
