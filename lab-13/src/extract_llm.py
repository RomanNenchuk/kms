"""Метод Б: видобування тверджень через Gemini зі схемою (structured output), закритим словником,
обов'язковим evidence, повторами при помилках та валідацією. Лише dev, якщо не вказано --split test --final.

Запуск:  python src/extract_llm.py --split dev
Вихід:   results/llm_{split}.jsonl, results/llm_{split}_rejected.jsonl, results/llm_{split}_summary.json,
         llm_log/gemini_calls.jsonl (протокол усіх викликів).
"""
import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, ValidationError

import common as cm
import gold_tools as gt
from config import GEMINI_MODEL, SEED, gemini_key

PROMPT_VERSION = "B-v3"
MAX_RETRIES = 3                      # повторні спроби на документ (мінімум 2 за вимогою)
ETYPES = ["Airline", "Airport", "AircraftType", "Organization", "Location", "Flight", "Event", "Person", "Regulation"]
EType = Literal["Airline", "Airport", "AircraftType", "Organization", "Location", "Flight", "Event", "Person", "Regulation"]
Rel = Literal["HUB_AT", "SERVES", "OPERATES", "MANUFACTURED_BY", "OWNS_STAKE_IN", "LOCATED_IN", "OPERATED_BY",
              "INVOLVED_IN", "ISSUED_BY", "AGREEMENT_WITH"]
Kind = Literal["codeshare", "alliance", "risk_sharing", "slot_trade", "other"]


class LMention(BaseModel):
    type: EType
    text: Optional[str] = None       # дослівно з тексту; null лише якщо implicit_topic
    implicit_topic: bool = False     # сутність — тема документа (з заголовка), у реченні не названа


class LAmount(BaseModel):
    value: float
    currency: str


class LQual(BaseModel):
    time: Optional[str] = None       # ISO: 2019, 2019-03, 2019-03-05
    count: Optional[int] = None
    amount: Optional[LAmount] = None
    role: Optional[str] = None
    kind: Optional[Kind] = None      # лише для AGREEMENT_WITH


class LClaim(BaseModel):
    subject: LMention
    relation: Rel
    object: LMention
    evidence: str                    # ДОСЛІВНЕ речення (або фрагмент) з документа
    qualifiers: LQual = LQual()
    modality: Literal["asserted", "planned"] = "asserted"


class LOutput(BaseModel):
    claims: List[LClaim]


def sig_text():
    return "\n".join(f"- {r}: {'|'.join(sorted(s))} -> {'|'.join(sorted(o))}" for r, (s, o) in gt.SIGNATURES.items())


SYSTEM = f"""Ти витягуєш факти (твердження) з англомовного тексту про авіаційні перевезення для графа знань.
Твердження = (subject, relation, object) + evidence + qualifiers + modality.

ТИПИ СУТНОСТЕЙ (закритий список): {', '.join(ETYPES)}.
ВІДНОШЕННЯ (закритий список) і дозволені типи subject -> object:
{sig_text()}
Інших відношень і типів не існує. Якщо факт не вкладається в список — не витягуй його.

ПРАВИЛА
R1. Витягуй лише те, що прямо сказано в тексті. Ніяких знань ззовні, ніяких припущень.
R2. evidence — ДОСЛІВНИЙ фрагмент тексту, що підтверджує факт (копіюй символ у символ, без змін і скорочень).
    Якщо subject і object названі в сусідніх реченнях, evidence = ці речення разом (безперервний фрагмент).
R3. subject.text і object.text — дослівні фрагменти, які ОБОВ'ЯЗКОВО лежать усередині evidence
    (повна назва, напр. «Lufthansa Group», а не «Lufthansa»; без артиклів the/a і присвійних 's).
    Місто/країна в SERVES і LOCATED_IN — окрема сутність Location (напр. «London»), якщо названа так у тексті.
R4. Типи й напрямок відношення мають відповідати сигнатурам вище.
R5. Якщо суб'єкт або об'єкт — тема документа (заголовок), але в реченні названий лише займенником
    («it», «the airline», «the airport»), став implicit_topic=true і text=null.
R6. Перелік («A, B and C») = окреме твердження для кожного елемента.
R7. modality=planned для планів, намірів, майбутніх подій («will», «plans to», «is scheduled»); інакше asserted.
R8. qualifiers: time (ISO), count (кількість, якщо вказано), amount{{value,currency}} (суми), role (роль особи),
    kind (ТІЛЬКИ для AGREEMENT_WITH: codeshare|alliance|risk_sharing|slot_trade|other). Не вигадуй відсутні значення.
R8b. MANUFACTURED_BY лише якщо виробника названо в тексті поруч із типом літака; INVOLVED_IN — також члени екіпажу
    й пасажири, названі поіменно, та тип літака, що брав участь у події. AGREEMENT_WITH — також спільні програми/угоди між виробниками.
    LOCATED_IN — штаб-квартира/розташування організації, аеропорт у місті. ISSUED_BY — норма (напр. директива) і орган, що її видав;
    для кожного органу окреме твердження. Типи літаків називай з моделлю («Boeing 767-200», якщо так написано).
R4b. Напрямок: SERVES — subject лише Airline або Flight (не Airport); OPERATES — Airline -> AircraftType; HUB_AT — Airline -> Airport;
    OWNS_STAKE_IN — власник -> об'єкт володіння (напр. «Lufthansa Group owns Austrian Airlines»).
R9. HUB_AT — лише якщо сказано, що аеропорт є хабом/базою авіакомпанії. SERVES — маршрути/напрямки авіакомпанії або рейсу.
R10. Не дублюй твердження. Якщо тверджень немає — поверни {{"claims": []}}.
R11. Відповідай ЛИШЕ JSON за схемою.

ПРИКЛАД (вигаданий)
Текст: «Northwind Airlines operates a hub at Lakeview International Airport. The airline flies the Aerotek 200,
which is built by Aerotek Industries. In 2020 it signed a codeshare agreement with Skyline Air.»
Тема документа: Northwind Airlines (Airline).
Відповідь: claims = [
 {{subject:{{type:Airline,text:"Northwind Airlines"}}, relation:HUB_AT, object:{{type:Airport,text:"Lakeview International Airport"}}, evidence:"Northwind Airlines operates a hub at Lakeview International Airport."}},
 {{subject:{{type:Airline,implicit_topic:true}}, relation:OPERATES, object:{{type:AircraftType,text:"Aerotek 200"}}, evidence:"The airline flies the Aerotek 200, which is built by Aerotek Industries."}},
 {{subject:{{type:AircraftType,text:"Aerotek 200"}}, relation:MANUFACTURED_BY, object:{{type:Organization,text:"Aerotek Industries"}}, evidence:"The airline flies the Aerotek 200, which is built by Aerotek Industries."}},
 {{subject:{{type:Airline,implicit_topic:true}}, relation:AGREEMENT_WITH, object:{{type:Airline,text:"Skyline Air"}}, evidence:"In 2020 it signed a codeshare agreement with Skyline Air.", qualifiers:{{time:"2020",kind:"codeshare"}}}}
]
"""


def user_prompt(doc_id, text, topic, feedback=None):
    t = f"{topic['text']} ({topic['type']})" if topic else "немає"
    s = f"Тема документа: {t}\n\nТЕКСТ ДОКУМЕНТА {doc_id}:\n\"\"\"\n{text}\n\"\"\"\n\nВитягни всі твердження."
    if feedback:
        s += f"\n\nПопередня відповідь не пройшла перевірку: {feedback}\nВиправ і поверни повний JSON знову."
    return s


def ws_find(text, frag, start=0):
    """Пошук фрагмента: точний, інакше з гнучкими пробілами. Повертає (a, b) або None."""
    i = text.find(frag, start)
    if i >= 0:
        return i, i + len(frag)
    parts = [re.escape(p) for p in frag.split()]
    if not parts:
        return None
    m = re.search(r"\s+".join(parts), text[start:])
    return (start + m.start(), start + m.end()) if m else None


def expand(text, a, b, etype, aliases):
    """Розширює мітку до найдовшого аліаса того ж типу, що починається з неї в цій позиції."""
    best = (a, b)
    for surf, (_, t) in aliases.items():
        if t == etype and len(surf) > best[1] - a and surf.startswith(text[a:b]) and text.startswith(surf, a):
            best = (a, a + len(surf))
    return best


SWAPPABLE = {"HUB_AT", "OPERATES", "OPERATED_BY", "MANUFACTURED_BY"}   # напрямок, який модель часто плутає


def snap(text, a, b):
    """Розширює фрагмент до меж речень (щоб evidence було цілим реченням)."""
    i = max(text.rfind(". ", 0, a), text.rfind("\n", 0, a))
    a2 = 0 if i < 0 else i + (2 if text.startswith(". ", i) else 1)
    m = re.search(r"[.!?](?=\s|$)", text[b:])
    b2 = b + m.end() if m else b
    return a2, max(b2, b)


def nearest(text, frag, a, b, window=600):
    """Входження frag, найближче до фрагмента [a, b); None, якщо немає в околі."""
    best, start = None, max(0, a - window)
    while True:
        pos = ws_find(text, frag, start)
        if not pos or pos[0] > b + window:
            break
        d = 0 if (pos[0] >= a and pos[1] <= b) else min(abs(pos[0] - b), abs(pos[1] - a))
        if best is None or d < best[0]:
            best = (d, pos)
        start = pos[0] + 1
    return best[1] if best else None


def build(doc_id, text, lc, topic, aliases, prov):
    """LClaim -> твердження зі схеми v1.2. Повертає (claim, [проблеми])."""
    problems = []
    ev = ws_find(text, lc.evidence.strip())
    verified = ev is not None
    if ev is None:
        return None, ["evidence не знайдено в тексті"]
    ev_a, ev_b = ev
    subj, obj = lc.subject, lc.object
    sig = gt.SIGNATURES[lc.relation]
    if (subj.type not in sig[0] or obj.type not in sig[1]) and lc.relation in SWAPPABLE \
            and obj.type in sig[0] and subj.type in sig[1]:
        subj, obj = obj, subj                               # виправлення переплутаного напрямку

    spans = []

    def mention(m):
        if m.implicit_topic or not m.text:
            if not topic or topic["type"] != m.type:
                problems.append("implicit_topic без відповідної теми документа")
                return None
            return {"type": topic["type"], "canonical": topic["canonical"], "implicit_topic": True}
        pos = nearest(text, m.text.strip(), ev_a, ev_b)
        if pos is None:
            problems.append(f"мітку «{m.text}» не знайдено поряд з evidence")
            return None
        pos = expand(text, pos[0], pos[1], m.type, aliases)
        spans.append(pos)
        canon, ctype = cm.canonical_for(text[pos[0]:pos[1]], m.type, aliases)
        return {"type": m.type, "canonical": canon, "text": text[pos[0]:pos[1]], "start": pos[0], "end": pos[1]}

    s, o = mention(subj), mention(obj)
    if problems or not s or not o:
        return None, problems
    lo, hi = min([ev_a] + [x[0] for x in spans]), max([ev_b] + [x[1] for x in spans])
    if (lo, hi) != (ev_a, ev_b):                            # evidence мало охопити обидві мітки
        ev_a, ev_b = snap(text, lo, hi)
    q = {}
    ql = lc.qualifiers
    if ql.time:
        q["time"] = ql.time
    if ql.count is not None:
        q["count"] = ql.count
    if ql.amount:
        q["amount"] = {"value": ql.amount.value, "currency": ql.amount.currency}
    if ql.role:
        q["role"] = ql.role
    if lc.relation == "AGREEMENT_WITH":
        q["kind"] = ql.kind or "other"
    claim = {"doc_id": doc_id, "subject": s, "relation": lc.relation, "object": o,
             "evidence": {"text": text[ev_a:ev_b], "start": ev_a, "end": ev_b},
             "modality": lc.modality, "annotator": "gemini", "evidence_verified": verified, "provenance": prov}
    if q:
        claim["qualifiers"] = q
    probs = cm.check_prediction(claim, text)
    return (None if probs else claim), probs


class Gemini:
    def __init__(self):
        from google import genai
        from google.genai import types
        self.types = types
        self.client = genai.Client(api_key=gemini_key())

    def call(self, system, prompt):
        cfg = self.types.GenerateContentConfig(system_instruction=system, temperature=0.0, seed=SEED,
                                               response_mime_type="application/json", response_schema=LOutput)
        r = self.client.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=cfg)
        u = getattr(r, "usage_metadata", None)
        return r.text, (getattr(u, "prompt_token_count", 0) or 0), (getattr(u, "candidates_token_count", 0) or 0)


def log_call(path, entry):
    path.parent.mkdir(exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def extract_doc(client, doc_id, text, topic, aliases, sources, logpath, split):
    feedback, tin, tout, attempts = None, 0, 0, 0
    parsed = None
    for attempt in range(MAX_RETRIES + 1):
        attempts += 1
        entry = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": GEMINI_MODEL,
                 "temperature": 0.0, "seed": SEED, "prompt_version": PROMPT_VERSION, "doc_id": doc_id,
                 "split": split, "attempt": attempt, "human_decision": "pending"}
        try:
            raw, ti, to = client.call(SYSTEM, user_prompt(doc_id, text, topic, feedback))
            tin, tout = tin + ti, tout + to
            entry.update(raw_output=raw, tokens_in=ti, tokens_out=to)
            parsed = LOutput.model_validate_json(raw)
            log_call(logpath, entry)
            break
        except ValidationError as e:                       # некоректний JSON/схема -> просимо виправити
            feedback = f"помилка схеми: {str(e)[:300]}"
            entry["error"] = feedback
        except Exception as e:                             # мережа/ліміти -> пауза й повтор
            entry["error"] = f"API: {type(e).__name__}: {str(e)[:200]}"
            time.sleep(min(2 ** (attempt + 1), 30))
        log_call(logpath, entry)
    if parsed is None:
        return [], [], tin, tout, attempts, True
    prov = cm.provenance("llm", GEMINI_MODEL, PROMPT_VERSION, doc_id, temperature=0.0, seed=SEED,
                         tokens_in=tin, tokens_out=tout)
    ok, rejected = [], []
    for lc in parsed.claims:
        c, probs = build(doc_id, text, lc, topic, aliases, prov)
        if c:
            ok.append(c)
        else:
            rejected.append({"doc_id": doc_id, "raw": lc.model_dump(), "problems": probs, "provenance": prov})
    return cm.dedupe(ok), rejected, tin, tout, attempts, False


def main(client=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--final", action="store_true", help="дозвіл на test (лише Результат 4)")
    ap.add_argument("--docs", nargs="*")
    a = ap.parse_args()
    docs = cm.split_docs(a.split, a.final)
    if a.docs:
        docs = [d for d in docs if d in a.docs]
    client = client or Gemini()
    aliases, sources = cm.load_aliases(), cm.load_sources()
    logpath = gt.ROOT / "llm_log" / "gemini_calls.jsonl"
    price_in, price_out = float(os.getenv("GEMINI_PRICE_IN", 0)), float(os.getenv("GEMINI_PRICE_OUT", 0))  # $ за 1M токенів
    rows, rej, tot_in, tot_out, failed = [], [], 0, 0, []
    for d in docs:
        text = cm.read_doc(d)
        topic = cm.topic_of(d, text, sources, aliases)
        ok, rj, ti, to, att, fail = extract_doc(client, d, text, topic, aliases, sources, logpath, a.split)
        rows += ok
        rej += rj
        tot_in, tot_out = tot_in + ti, tot_out + to
        if fail:
            failed.append(d)
        print(f"{d}: {len(ok)} тверджень, відхилено {len(rj)}, спроб {att}{' ПОМИЛКА' if fail else ''}")
    cm.RESULTS.mkdir(exist_ok=True)
    gt.write_jsonl(cm.RESULTS / f"llm_{a.split}.jsonl", rows)
    gt.write_jsonl(cm.RESULTS / f"llm_{a.split}_rejected.jsonl", rej)
    cost = (tot_in * price_in + tot_out * price_out) / 1e6
    unv = sum(1 for r in rej if any(p.startswith("evidence не знайдено") for p in r["problems"]))
    summary = {"split": a.split, "model": GEMINI_MODEL, "prompt_version": PROMPT_VERSION, "docs": len(docs),
               "claims": len(rows), "rejected": len(rej), "failed_docs": failed, "tokens_in": tot_in,
               "tokens_out": tot_out, "cost_usd": round(cost, 4),
               "cost_per_doc_usd": round(cost / len(docs), 4) if docs else 0, "unverified_evidence": unv,
               "unverified_share": round(unv / (len(rows) + len(rej)), 3) if rows or rej else 0}
    (cm.RESULTS / f"llm_{a.split}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()