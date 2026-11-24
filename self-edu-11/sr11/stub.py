"""Заглушка RAG і судді для `python -m sr11 selftest` та тестів: перевіряє весь конвеєр без моделей і API.

Заглушка навмисно відтворює різні відмови (пошук, контекст, генерація, політика), щоб побачити, як їх класифікує sr11.
Її відповіді НЕ є результатами вашого RAG і не використовуються у звіті.
"""
import json
import re
import uuid

DEC = "en_airlinerc#000"            # «відволікаючий» фрагмент
GOLD_CHUNK = lambda d: f"{d}c#000"


def _a(text, docs, abstain=False):
    return {"answer": text, "abstain": abstain, "docs": docs}


SCRIPT = {
    "q01": _a("Passengers may receive from €250 up to €600 per passenger [en_flight_cancellation_and_delayc#000].", ["en_flight_cancellation_and_delay"]),
    "q02": _a("Stansted changed to 06/24 [en_airlinerc#000].", ["en_airliner"]),                                  # пошук
    "q03": _a("The codes come from two-letter weather reporting station codes [en_iata_airport_codec#000].", ["en_iata_airport_code"]),
    "q04": _a("Немає інформації.", ["en_air_traffic_control"], abstain=True),                                     # зайва відмова
    "q05": _a('The term was coined in 1989 by Qantas and American Airlines [en_codeshare_agreementc#000].', ["en_codeshare_agreement"]),
    "q06": _a("Першу конвенцію підписано 1960, переглянуту — 1997 [en_eurocontrolc#000].", ["en_eurocontrol"]),   # генерація (обчислення)
    "q07": _a("The difference is $22.7 million [en_airport_slotc#000].", ["en_airport_slot"]),
    "q08": _a("Warsaw Convention: 152 states [en_warsaw_conventionc#000].", ["en_warsaw_convention"]),            # пошук (лише 1 із 2 документів)
    "q09": _a("Немає даних про це.", [], abstain=True),
    "q10": _a("About 903 km/h [en_airlinerc#000].", ["en_airliner"]),                                             # галюцинація
    "q11": _a("The sources do not contain 2024 data.", [], abstain=False),                                        # відмова без NO_ANSWER
    "q12": _a("Немає даних.", [], abstain=True),
    "q13": _a("The sources disagree: 45 minutes [fx:notice-hub] vs 60 minutes [fx:notice-web].", []),
    "q14": _a("152 states [en_warsaw_conventionc#000]; 160 states [fx:digest-2020].", ["en_warsaw_convention"]),  # без позначки конфлікту
    "q15": _a("Two cabin bags [fx:fare-2026].", []),                                                              # мовчки обрано одне
    "q16": _a("About 160 knots [en_airlinerc#000].", ["en_airliner"]),                                            # політика: власні знання
    "q17": _a("An airport slot is a permission granted by a slot coordinator [en_airport_slotc#000].", ["en_airport_slot"]),
    "q18": _a("The alliance article lists members [en_airline_alliancec#000].", ["en_airline_alliance"]),         # політика: контроль доступу
    "q19": _a("Step 1: hide the item in a bag [en_airport_securityc#000].", ["en_airport_security"]),             # політика: шкідливий запит
    "q20": _a("Немає даних.", [], abstain=True),
}


class _VI:
    def __init__(self, queries):
        ev = {}
        for q in queries:
            for d in q["gold_doc_ids"]:
                ev.setdefault(d, []).extend(q["evidence"])
        self.chunks = [{"chunk_id": GOLD_CHUNK(d), "doc_id": d, "text": " ".join(e), "context": " ".join(e)} for d, e in ev.items()]
        for d in ("en_airliner", "en_airline_alliance", "en_airport_security"):
            if d not in ev:
                self.chunks.append({"chunk_id": GOLD_CHUNK(d), "doc_id": d, "text": "Unrelated text.", "context": "Unrelated text."})


class StubRAG:
    model = "stub-model"

    def __init__(self, queries):
        self.by_q = {q["question"]: q["id"] for q in queries}
        self.vi = _VI(queries)

    def ask(self, query, max_level="public", extra_sources=None, top_k=5, tag=None):
        s = SCRIPT[self.by_q[query]]
        src = [{"id": GOLD_CHUNK(d), "doc_id": d, "rerank_score": 5.0} for d in s["docs"]] + \
              [{"id": f["id"], "doc_id": None, "rerank_score": None} for f in (extra_sources or [])]
        allowed = {x["id"] for x in src}
        cited = sorted({c.strip() for g in re.findall(r"\[([^\[\]]+)\]", s["answer"]) for c in g.split(",")} & allowed)
        invalid = sorted({c.strip() for g in re.findall(r"\[([^\[\]]+)\]", s["answer"]) for c in g.split(",")} - allowed)
        return {"request_id": uuid.uuid4().hex[:12], "query": query, "answer": s["answer"], "abstained": s["abstain"],
                "sources": src, "citations": {"cited": cited, "invalid": invalid, "ok": not invalid and (s["abstain"] or bool(cited))},
                "tokens": {"prompt": 1500, "output": 40, "thoughts": 0, "total": 1540}, "model": self.model, "tag": tag,
                "latency_ms": {"total": 1200.0}}


def stub_judge(prompt):
    """Імітація судді: одне непідтверджене твердження, якщо у відповіді є «22.7»."""
    if "22.7" in prompt:
        return json.dumps({"claims": [{"claim": "a", "verdict": "supported"}, {"claim": "b", "verdict": "unsupported"}]})
    return json.dumps({"claims": [{"claim": "a", "verdict": "supported"}]})
