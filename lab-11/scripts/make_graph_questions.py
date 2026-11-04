#!/usr/bin/env python3
"""Генерує eval/graph_questions.jsonl (v2).

A. 10 ГІБРИДНИХ питань: перша половина відповіді — у статті Вікіпедії з корпусу (must_text, перевіряється assert-ом
   проти data/corpus.jsonl), друга — у графі ЛР 9 (must_graph, еталон обчислено з data/*.csv).
B. 6 графових питань для перевірки самого підграфа (лінкінг, ліміти, відсутній зв'язок, захист ПДн).
Запуск: python scripts/make_graph_questions_v2.py"""
import json, re, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = lambda n: pd.read_csv(ROOT / "data" / f"{n}.csv", dtype=str)
ap, al, rk, ac, pl = D("airports"), D("airlines"), D("risks"), D("aircraft"), D("pilots")
dl, dep, arr = D("delays"), D("rel_departs_from"), D("rel_arrives_at")
own, atap, nxt = D("rel_owned_by"), D("rel_at_airport"), D("rel_next_leg")
hdel, caus, hpil, oper, aff = D("rel_has_delay"), D("rel_caused_by"), D("rel_has_pilot"), D("rel_operated_by"), D("rel_affected_by")
one = lambda df, col, val, out: df.loc[df[col] == val, out].iloc[0]
esc = lambda s: re.escape(s.lower())
corpus = {}
for line in open(ROOT / "data" / "corpus.jsonl", encoding="utf-8"):
    r = json.loads(line)
    corpus.setdefault(r["doc_id"], []).append(r["text"])
Q = []


def nr(n):
    """Число з необов'язковими роздільниками тисяч: 8373 | 8,373 | 8 373 | 8.373"""
    n = str(n)
    g = []
    while len(n) > 3:
        g.insert(0, n[-3:]); n = n[:-3]
    g.insert(0, n)
    return r"\b" + r"[,. \u00a0\u202f]?".join(g) + r"\b"




def add(qtype, hops, question, must_graph=(), must_text=(), text_doc=None, abstain=False, note=""):
    for rx in must_text:                                   # текстовий еталон має реально бути в статті
        assert any(re.search(rx, t, re.I) for t in corpus[text_doc]), f"{text_doc}: немає /{rx}/"
    Q.append({"id": f"h{len(Q) + 1:02d}" if qtype == "hybrid" else f"g{len(Q) - 9:02d}", "qtype": qtype, "hops": hops,
              "question": question, "must_text": list(must_text), "must_graph": list(must_graph),
              "text_doc": text_doc, "expect_abstain": abstain, "note": note})


# ---------- A. гібридні ----------
hub = "LWO"; nf = (dep.endId == hub).sum()
add("hybrid", 1, f"What is an airline hub, and how many flights depart from {one(ap, 'iata', hub, 'name')} airport in our data?",
    [rf"\b{nf}\b"], [r"hub-and-spoke|concentrate|transfer"], "en_airline_hub")

k = "KRK"
add("hybrid", 2, f"What is an IATA airport code, and which airport in our network has the code {k} and in which country is it?",
    [esc(one(ap, "iata", k, "name").split()[0]), "poland"], [r"three-letter"], "en_iata_airport_code")

f0 = hdel.loc[~hdel.endId.isin(dl.loc[dl.propagated == "true", "delayId"]), "startId"].iloc[0]
d0 = one(hdel, "startId", f0, "endId"); r0 = one(caus, "startId", d0, "endId"); m0 = one(dl, "delayId", d0, "minutes")
add("hybrid", 2, f"What are common causes of flight delays, and what caused the delay of flight {f0}?",
    [f"{r0.lower()}|{esc(one(rk, 'riskId', r0, 'name'))}"], [r"weather"], "en_flight_cancellation_and_delay")

add("hybrid", 2, f"Under the EU Air Passengers Rights Regulation, from how many hours of delay is compensation due, and how long was the delay of flight {f0}?",
    [rf"\b{m0}\b"], [r"three hours|3 hours"], "en_air_passengers_rights_regulation",
    note="інтеграція: 42 хв < 3 год, тож компенсації немає")

g = "RK05"
add("hybrid", 2, "How can weather limit airport capacity, and which risk is recorded at Gdansk in our graph?",
    [f"{g.lower()}|{esc(one(rk, 'riskId', g, 'name'))}"], [r"weather"], "en_air_traffic_flow_management")

reg = "SU-001"
add("hybrid", 1, f"What is an aircraft lease, and what are the model and seat capacity of aircraft {reg}?",
    [esc(one(ac, "registration", reg, "model").split()[-1]), rf"\b{one(ac, 'registration', reg, 'seatCapacity')}\b"], [r"leas"], "en_aircraft_lease")

pid = hpil.endId.value_counts().index[0]
add("hybrid", 1, f"Which crew member is the pilot-in-command, and how many flight hours does pilot {one(pl, 'pilotId', pid, 'name')} have?",
    [nr(one(pl, 'pilotId', pid, 'flightHours'))], [r"captain"], "en_aircrew")

fleet = sorted(ac.loc[ac.registration.isin(own.loc[own.endId == "CA", "startId"]), "model"].unique())
add("hybrid", 2, "What does aircraft maintenance include, and which aircraft models does CarpathAir own?",
    [esc(m) for m in fleet], [r"inspection|overhaul|repair"], "en_aircraft_maintenance")

w = "WAW"; na = (arr.endId == w).sum()
add("hybrid", 1, f"What is an airport slot, and how many flights arrive at {one(ap, 'iata', w, 'name')} airport in our data?",
    [rf"\b{na}\b"], [r"slot coordinator|permission|take-?off"], "en_airport_slot")

add("hybrid", 1, "What is a codeshare agreement, and what is the home country of AeroLink Europe?",
    [r"\bpl\b|poland"], [r"codeshar"], "en_codeshare_agreement")

# ---------- B. суто графові (перевірка підграфа) ----------
s0 = next(s for s in dict(zip(nxt.startId, nxt.endId)) if dict(zip(nxt.startId, nxt.endId))[s] in dict(zip(nxt.startId, nxt.endId)) and s not in set(nxt.endId))
nm, gap = dict(zip(nxt.startId, nxt.endId)), dict(zip(nxt.startId, nxt.gapMin))
add("graph_only", 1, f"Which flight is the next leg after {s0}, and what is the gap in minutes?", [nm[s0].split("-")[0].lower(), rf"\b{gap[s0]}\b"])
add("graph_only", 2, f"Which flight comes two legs after {s0}?", [nm[nm[s0]].split("-")[0].lower()])
regs = own.loc[own.endId == "CA", "startId"].tolist(); assert len(regs) <= 8
add("graph_only", 1, "Which aircraft registrations does CarpathAir own?", [esc(r) for r in regs])
hub_air = sorted({one(al, "code", one(oper, "startId", f, "endId"), "name") for f in dep.loc[dep.endId == hub, "startId"]})
add("graph_only", 2, f"Which airlines operate flights departing from {one(ap, 'iata', hub, 'name')} airport?", [esc(x) for x in hub_air],
    note=f"агрегація понад ліміт: {len(hub_air)} авіакомпаній серед {nf} рейсів, підграф бачить ≤ 8 рейсів")
tech = rk.loc[(rk.kind == "technical") & ~rk.riskId.isin(atap.startId), "name"].iloc[0]
add("graph_only", 1, f"Which airport does the risk {tech} apply to?", abstain=True, note="технічний ризик без AT_AIRPORT")
add("graph_only", 1, f"Who are the passengers on flight {f0}?", abstain=True, note="пасажири виключені з підграфа (ПДн)")

out = ROOT / "eval" / "graph_questions.jsonl"
out.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in Q) + "\n", encoding="utf-8")
for q in Q:
    print(q["id"], q["qtype"], "|", q["question"], "| text:", q["must_text"], "| graph:", q["must_graph"] or "ABSTAIN")
print(f"\nЗбережено {len(Q)} питань -> {out}")
