"""Метод А: правила + spaCy (NER, словник аліасів, шаблони, регулярні вирази).

  python src/extract_rules.py --split dev            # результати: results/rules_dev.jsonl
  python src/extract_rules.py --split dev --docs D06 D14
  python src/extract_rules.py --split test --final   # лише у Результаті 4

Налаштування (правила, словники) виконується лише на dev. Словник аліасів обмежений сутностями dev.
"""
import argparse
import re

import spacy

import common as cm
import gold_tools as gt
from config import SPACY_MODEL

RULES_VERSION = "A-0.1"
STOP_LEAD = {"the", "in", "at", "its", "it", "a", "an", "on", "from", "to", "of", "by", "with", "for", "since", "during", "after", "as"}
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], 1)}
MON = "|".join(MONTHS)

# --- регулярні вирази для сутностей -----------------------------------------------------------------
REGEX_ENTITIES = [
    ("AircraftType", re.compile(
        r"\b(?:Boeing 7\d7(?:-\d{3}(?:ER|F)?)?|Airbus A\d{3}(?:-\d{3}|neo)?(?: family)?|A\d{3}neo(?: family)?|"
        r"Embraer E-Jet E2 family|E\d{3}-E2|(?:McDonnell )?Douglas DC-\d+(?:-\d+)?|DC-\d+(?:-\d+)?|"
        r"McDonnell Douglas MD-\d+|MD-\d+|Vickers Viscount|7\d7-\d{3}(?:ER|F)?)\b")),
    ("Flight", re.compile(r"\b(?:[A-Z][\w&.]*\s+){1,3}Flight \d{1,4}\b")),
    ("Airport", re.compile(r"\b(?:[A-Z][\w.\-–]*\s+){1,6}Airport\b")),
    ("Airline", re.compile(r"\b(?:[A-Z][\w&]*\s+){1,3}(?:Air Lines|Airlines?|Airways|Air|Jet|Wings|Cargo)\b")),
]
NER_TYPE = {"GPE": "Location", "LOC": "Location", "PERSON": "Person", "EVENT": "Event"}
AIRLINE_WORD = re.compile(r"\b(Air Lines|Airlines?|Airways|Air|Jet|Wings|Cargo)\b")

# --- правила відношень ----------------------------------------------------------------------------------
A_, AP, AC, O_, L_, F_, P_, R_ = "Airline", "Airport", "AircraftType", "Organization", "Location", "Flight", "Person", "Regulation"
RULES = [
    dict(rel="HUB_AT", mode="bag", S={A_}, O={AP}, trig=r"\b(hub|bases?|focus city|operational bases?)\b"),
    dict(rel="LOCATED_IN", mode="first_after", S={AP, A_, O_}, O={L_},
         trig=r"\b(?:headquartered|based|located|situated|head offices?|headquarters(?: are| is)?|airport|agency|offices?)\s+in\b"),
    dict(rel="SERVES", mode="bag", S={A_, F_}, O={AP, L_},
         trig=r"\b(?:flights?|routes?|services?|destinations?|serves?|served|connected|fly|flew)\b"),
    dict(rel="OPERATES", mode="bag", S={A_}, O={AC},
         trig=r"\b(?:operates?|operators?|operating|fleet|entered service|introduced|use|used)\b"),
    dict(rel="MANUFACTURED_BY", mode="first_after", S={AC}, O={O_},
         trig=r"\b(?:manufactured|built|produced|developed|designed)\b[^.]*?\bby\b"),
    dict(rel="OWNS_STAKE_IN", mode="owns", S={O_, A_, P_}, O={A_, AP, O_},
         trig=r"\b(?:owns?|owned|subsidiar\w+|shareholders?|stake|acquir\w+|acquisitions?|purchased|investors?|equity)\b"),
    dict(rel="OPERATED_BY", mode="bag", S={F_}, O={A_}, trig=r"\bflights?\b"),
    dict(rel="INVOLVED_IN", mode="role", S={P_}, O={F_},
         trig=r"\b(?:pilot|captain|first officer|co-pilot|flight attendants?)\b"),
    dict(rel="ISSUED_BY", mode="bag", S={R_}, O={O_}, trig=r"\b(?:issu\w+|published|publishes|passed)\b"),
    dict(rel="AGREEMENT_WITH", mode="svo", S={A_, O_}, O={A_, O_},
         trig=r"\b(?:code ?shar\w+|alliance|risk-sharing agreements?|agreements? with|paid|joined|member)\b"),
]
SWAP = re.compile(r"\b(?:owned by|acquired by|purchased by|subsidiary of|part of)\b")
ROLES = [("pilot in command", r"pilot in command|captain"), ("first officer", r"first officer|co-pilot|second in command"),
         ("flight attendant", r"flight attendants?")]
KINDS = [("codeshare", r"code ?shar"), ("risk_sharing", r"risk-sharing"), ("slot_trade", r"slots?"), ("alliance", r"alliance")]
PLANNED = re.compile(r"\b(?:plans? to|planned|will|slated|announced .{0,40}would|expected to|intends?)\b", re.I)


# --- сутності ---------------------------------------------------------------------------------------
class Gazetteer:
    def __init__(self, aliases):
        self.aliases = aliases
        names = sorted(aliases, key=len, reverse=True)
        self.rx = re.compile(r"(?<![\w])(?:" + "|".join(map(re.escape, names)) + r")(?![\w])") if names else None

    def find(self, s):
        return [(m.start(), m.end(), self.aliases[m.group(0)][1], 3) for m in self.rx.finditer(s)] if self.rx else []


def strip_span(s, a, b):
    """Прибрати початкові службові слова й присвійне 's."""
    while True:
        m = re.match(r"([A-Za-z]+)\s+", s[a:b])
        if m and m.group(1).lower() in STOP_LEAD:
            a += m.end()
        else:
            break
    if s[a:b].endswith(("'s", "’s")):
        b -= 2
    return a, b


def find_entities(sent, gaz, aliases):
    s = sent.text
    cands = list(gaz.find(s))
    for etype, rx in REGEX_ENTITIES:
        for m in rx.finditer(s):
            a, b = strip_span(s, m.start(), m.end())
            if b > a:
                cands.append((a, b, etype, 2))
    for ent in sent.ents:
        a, b = ent.start_char - sent.start_char, ent.end_char - sent.start_char
        t = NER_TYPE.get(ent.label_)
        if ent.label_ in ("ORG", "FAC"):
            txt = ent.text
            t = "Airport" if "Airport" in txt else "Airline" if AIRLINE_WORD.search(txt) else "Organization"
        if ent.text.isupper() and len(ent.text) <= 5 and ent.text not in aliases:
            continue                                 # EPWA, IATA тощо без аліаса
        if t:
            a, b = strip_span(s, a, b)
            if b > a:
                cands.append((a, b, t, 1))
    cands.sort(key=lambda c: (-c[3], -(c[1] - c[0]), c[0]))
    taken, out = [], []
    for a, b, t, pr in cands:
        if any(a < y and x < b for x, y in taken):
            continue
        taken.append((a, b))
        surface = s[a:b]
        canon, ctype = cm.canonical_for(("Boeing " + surface) if (t == "AircraftType" and re.match(r"7\d7-", surface)) else surface, t, aliases)
        out.append(dict(start=a, end=b, text=surface, type=ctype, canonical=canon))
    return sorted(out, key=lambda e: e["start"])


# --- допоміжне -----------------------------------------------------------------------------------------
def parse_time(s):
    found = []
    for m in re.finditer(rf"\b(\d{{1,2}}) ({MON}) (\d{{4}})\b", s):
        found.append(f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}")
    for m in re.finditer(rf"\b({MON}) (\d{{1,2}}), (\d{{4}})\b", s):
        found.append(f"{m.group(3)}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}")
    if not found:
        for m in re.finditer(rf"\b({MON}) (\d{{4}})\b", s):
            found.append(f"{m.group(2)}-{MONTHS[m.group(1)]:02d}")
    if not found:
        found = re.findall(r"\b(1[89]\d{2}|20\d{2})\b", s)
    return found[0] if len(set(found)) == 1 else None


def parse_amount(s):
    m = re.search(r"(?:US)?\$\s?(\d+(?:\.\d+)?)\s?(million|billion|m|bn)\b", s)
    if not m:
        return None
    mult = 1e9 if m.group(2) in ("billion", "bn") else 1e6
    return {"value": round(float(m.group(1)) * mult), "currency": "USD"}


def pair_up(S, O):
    if not S or not O:
        return []
    if len(S) == 1 or len(O) == 1:
        return [(s, o) for s in S for o in O]
    out = []
    for o in O:
        before = [s for s in S if s["start"] < o["start"]]
        out.append(((before or S)[-1] if before else S[0], o))
    return out


def side(ents, types, exclude=()):
    return [e for e in ents if e["type"] in types and e not in exclude]


def apply_rule(rule, ents, sent_text, topic):
    m = re.search(rule["trig"], sent_text, re.I)
    if not m:
        return []
    t, S, O, mode = m.start(), rule["S"], rule["O"], rule["mode"]
    as_topic = lambda types: [dict(topic, implicit=True)] if topic and topic["type"] in types else []
    if mode == "bag":
        s_, o_ = side(ents, S), side(ents, O)
        if rule["rel"] == "SERVES":
            o_ = [e for e in o_ if e["start"] >= t]
            if any(e["type"] == F_ for e in s_):
                s_ = [e for e in s_ if e["type"] == F_]
            if any(e["type"] == AP for e in o_):
                o_ = [e for e in o_ if e["type"] == AP]
        if not s_:
            s_ = as_topic(S)
        if not o_:
            o_ = as_topic(O)
        return pair_up(s_, o_), {}
    if mode == "first_after":
        o_ = [e for e in side(ents, O) if e["start"] >= t][:1]
        before = [e for e in side(ents, S) if e["start"] < t]
        s_ = before[-1:] or as_topic(S)
        return [(s, o) for s in s_ for o in o_], {}
    if mode == "svo":
        before = [e for e in side(ents, S) if e["start"] < t]
        after = [e for e in side(ents, O) if e["start"] >= t]
        s_ = before[-1:] or as_topic(S)
        extra = {}
        txt = sent_text.lower()
        extra["kind"] = next((k for k, rx in KINDS if re.search(rx, txt)), "other")
        return [(s, o) for s in s_ for o in after], extra
    if mode == "owns":
        if SWAP.search(sent_text):
            sw = SWAP.search(sent_text).start()
            s_, o_ = [e for e in side(ents, S) if e["start"] > sw], [e for e in side(ents, O) if e["start"] < sw] or as_topic(O)
            return [(s, o) for s in s_ for o in o_], {}
        if re.search(r"shareholders?|stake|investors?|equity", m.group(0), re.I):
            s_ = side(ents, S)
            o_ = as_topic(O)
            return [(s, o) for s in s_ for o in o_], {}
        before = [e for e in side(ents, S) if e["start"] < t]
        after = [e for e in side(ents, O) if e["start"] >= t]
        s_ = before[-1:] or as_topic(S)
        return [(s, o) for s in s_ for o in after], {}
    if mode == "role":
        if not topic or topic["type"] not in O:
            return []
        role = next((r for r, rx in ROLES if re.search(rx, sent_text, re.I)), None)
        return [(p, dict(topic, implicit=True)) for p in side(ents, S)], ({"role": role} if role else {})
    return []


def to_claim(doc_id, text, off, sent_text, sent_start, rule, s, o, extra, prov):
    def mention(e):
        if e.get("implicit"):
            return {"type": e["type"], "canonical": e["canonical"], "implicit_topic": True}
        a = off + sent_start + e["start"]
        return {"type": e["type"], "canonical": e["canonical"], "text": e["text"], "start": a, "end": a + len(e["text"])}
    q = dict(extra)
    if (t := parse_time(sent_text)):
        q["time"] = t
    if (am := parse_amount(sent_text)):
        q["amount"] = am
    if rule["rel"] == "AGREEMENT_WITH":
        q.setdefault("kind", "other")
    else:
        q.pop("kind", None)
    ev_start = off + sent_start
    r = {"doc_id": doc_id, "subject": mention(s), "relation": rule["rel"], "object": mention(o),
         "evidence": {"text": sent_text, "start": ev_start, "end": ev_start + len(sent_text)},
         "modality": "planned" if PLANNED.search(sent_text) else "asserted", "annotator": "rules", "confidence": 0.5,
         "provenance": prov}
    if q:
        r["qualifiers"] = q
    return r


def run_doc(doc_id, nlp, aliases, gaz, sources):
    text = cm.read_doc(doc_id)
    topic = cm.topic_of(doc_id, text, sources, aliases)
    prov = cm.provenance("rules", f"spacy {spacy.__version__} {SPACY_MODEL} + rules", f"rules-{RULES_VERSION}", doc_id)
    out = []
    for off, line in cm.paragraphs(text):
        for sent in nlp(line).sents:
            st = sent.text
            ents = find_entities(sent, gaz, aliases)
            for rule in RULES:
                res = apply_rule(rule, ents, st, topic)
                if not res:
                    continue
                pairs, extra = res
                for s, o in pairs:
                    if s["canonical"] == o["canonical"]:
                        continue
                    out.append(to_claim(doc_id, text, off, st, sent.start_char, rule, s, o, extra, prov))
    return cm.dedupe(out), text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--final", action="store_true", help="дозвіл на test (лише Результат 4)")
    ap.add_argument("--docs", nargs="*", help="підмножина документів (для налагодження)")
    ap.add_argument("--out")
    a = ap.parse_args()
    docs = cm.split_docs(a.split, a.final)
    if a.docs:
        docs = [d for d in docs if d in a.docs]
    nlp, aliases, sources = spacy.load(SPACY_MODEL), cm.load_aliases(), cm.load_sources()
    gaz = Gazetteer(aliases)
    rows, bad = [], 0
    for d in docs:
        claims, text = run_doc(d, nlp, aliases, gaz, sources)
        for c in claims:
            if cm.check_prediction(c, text):
                bad += 1
                continue
            rows.append(c)
        print(f"{d}: {len(claims)} тверджень")
    cm.RESULTS.mkdir(exist_ok=True)
    out = a.out or str(cm.RESULTS / f"rules_{a.split}.jsonl")
    gt.write_jsonl(out, rows)
    print(f"Записано {len(rows)} тверджень ({a.split}, {len(docs)} док.; відкинуто перевіркою: {bad}) -> {out}")


if __name__ == "__main__":
    main()