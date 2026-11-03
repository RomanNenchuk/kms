"""Результат 5, крок 1: кандидати для золотого набору через Gemini.
Типи: keyword (10), multistep (6), unanswerable (12 кандидатів, лишиться ≥6).
Запуск: python -m scripts.gen_gold      Вихід: data/gold_draft.jsonl (ти перевіряєш)
"""
import json, random, re
from rank_bm25 import BM25Okapi
from src.config import ROOT, SEED
from src.chunking import load_docs, sections, STRATEGIES
from src.llm import ask

N_KW, N_MS, N_NA = 10, 6, 12
PV = "gold-gen-v1"
STOP = set("a an the of in on at to for and or is are was were be by with as from that this it its which what who when how why".split())
tok = lambda s: [w for w in re.findall(r"\w+", s.lower()) if w not in STOP]
norm = lambda s: re.sub(r"\s+", " ", s).strip()

rng = random.Random(SEED + 10)
docs = load_docs()
by_id = {d["doc_id"]: d for d in docs}
SYSTEM = "You write evaluation data for a retrieval system. Output JSON only."

def passages(d):
    return [(s, t) for s, t in sections(d["body"], d["title"])
            if 500 <= len(t) <= 1500 and sum(len(l) > 60 for l in t.splitlines()) >= 3]

def good_ev(ev, passage):
    ev = norm(ev)
    return ev if ev in norm(passage) and 40 <= len(ev) <= 220 else None

out = []
import atexit
path = ROOT / "data" / "gold_draft.jsonl"
def save():
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
atexit.register(save)      # зберігаємо згенероване, навіть якщо скрипт упаде

# ---------- 1. ключові слова ----------
KW = """Read the passage and write ONE short keyword-style search query (2 to 6 words, NOT a full question, no question mark),
the way a user types into a search box, that should lead to this passage. It must contain at least one distinctive
term from the passage (a name, number or technical term).
"evidence" must be ONE short sentence (under 220 characters) copied EXACTLY from the passage that is relevant to the query.
Return JSON: {{"query": "...", "evidence": "..."}}

Passage (article "{title}", section "{section}"):
\"\"\"
{passage}
\"\"\""""
order = docs[:]; rng.shuffle(order); n = 0
for d in order:
    if n >= N_KW: break
    ps = passages(d)
    if not ps: continue
    sec, p = rng.choice(ps)
    for _ in range(3):
        try:
            j = json.loads(ask(KW.format(title=d["title"], section=sec, passage=p), PV, 0.3, SYSTEM, True))
            q, ev = j["query"].strip(), good_ev(j["evidence"], p)
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            continue
        if ev and 2 <= len(q.split()) <= 7 and "?" not in q and any(w in p.lower() for w in tok(q)):
            n += 1
            out.append({"id": f"kw{n:02d}", "type": "keyword", "question": q, "evidence": [ev],
                        "doc_ids": [d["doc_id"]], "section": sec, "status": "pending"})
            print(f"kw{n:02d} [{d['title']} / {sec}]  Q: {q}\n      E: {ev}\n"); break

# ---------- 2. багатокрокові (два місця корпусу) ----------
MS = """Below are two passages from different articles about air transport. Write ONE question that can only be answered
completely by combining a fact from passage A with a fact from passage B (for example a comparison or a question with two parts).
The question must be self-contained, natural, and must not mention "passage A/B".
"evidence_a" and "evidence_b" must each be ONE short sentence (under 220 characters) copied EXACTLY from the respective passage.
Return JSON: {{"question": "...", "evidence_a": "...", "evidence_b": "..."}}

Passage A (article "{ta}", section "{sa}"):
\"\"\"
{pa}
\"\"\"

Passage B (article "{tb}", section "{sb}"):
\"\"\"
{pb}
\"\"\""""
RELATED = [("en_computer_reservation_system", "en_global_distribution_system"),
           ("en_icao_airport_code", "en_iata_airport_code"),
           ("en_overselling", "en_revenue_management"),
           ("en_air_passengers_rights_regulation", "en_flight_cancellation_and_delay"),
           ("en_aircraft_maintenance", "en_aircraft_ground_handling"),
           ("en_international_air_transport_association", "en_iata_airport_code"),
           ("en_low_cost_carrier", "en_airline_hub"),
           ("en_aircrew", "en_airline"),
           ("en_aircraft_lease", "en_airline"),
           ("en_eurocontrol", "en_convention_on_international_civil_aviation")]
rng.shuffle(RELATED); n = 0
for a, b in RELATED:
    if n >= N_MS: break
    if a not in by_id or b not in by_id: continue
    pa_l, pb_l = passages(by_id[a]), passages(by_id[b])
    if not pa_l or not pb_l: continue
    for _ in range(3):
        (sa, pa), (sb, pb) = rng.choice(pa_l), rng.choice(pb_l)
        try:
            j = json.loads(ask(MS.format(ta=by_id[a]["title"], sa=sa, pa=pa, tb=by_id[b]["title"], sb=sb, pb=pb), PV, 0.3, SYSTEM, True))
            q, ea, eb = j["question"].strip(), good_ev(j["evidence_a"], pa), good_ev(j["evidence_b"], pb)
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            continue
        if ea and eb:
            n += 1
            out.append({"id": f"ms{n:02d}", "type": "multistep", "question": q, "evidence": [ea, eb],
                        "doc_ids": [a, b], "section": f"{sa} | {sb}", "status": "pending"})
            print(f"ms{n:02d} [{a} + {b}]  Q: {q}\n      E1: {ea}\n      E2: {eb}\n"); break

# ---------- 3. без відповіді ----------
NA = """The search corpus consists of English Wikipedia articles with these titles:
{titles}

Write {n} realistic questions about AIR TRANSPORT MANAGEMENT that a user could ask, but whose answers are almost certainly
NOT contained in these general articles (e.g. very specific numbers for one airline or airport in a given year, internal
company procedures, prices, national rules of one particular country, events after 2024). Each question must still sound
on-topic and use vocabulary related to the articles, so that a search system is tempted to return something.
Return JSON: {{"questions": ["...", "..."]}}"""
j = json.loads(ask(NA.format(titles="; ".join(d["title"] for d in docs), n=N_NA), PV, 0.7, SYSTEM, True))
cands = [q.strip() for q in j["questions"]][:N_NA]
ctxs = sorted({c["context"] for c in STRATEGIES["hierarchical"](docs)})
bm = BM25Okapi([tok(c) for c in ctxs])
for i, q in enumerate(cands, 1):
    sc = bm.get_scores(tok(q)); top = sc.argsort()[::-1][:2]
    check = [{"bm25": round(float(sc[t]), 1), "snippet": ctxs[t][:200].replace("\n", " ")} for t in top]
    out.append({"id": f"na{i:02d}", "type": "unanswerable", "question": q, "evidence": [], "doc_ids": [],
                "status": "pending", "bm25_check": check})
    print(f"na{i:02d}  Q: {q}")
    for c in check: print(f"      BM25 {c['bm25']}: {c['snippet']}")
    print()

path = ROOT / "data" / "gold_draft.jsonl"
path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
from collections import Counter
print("Записано:", dict(Counter(r["type"] for r in out)), "->", path)
