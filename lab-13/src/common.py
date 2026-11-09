"""Спільні функції методів А (правила/spaCy) і Б (LLM): документи, split-захист, аліаси, provenance, перевірка."""
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import gold_tools as gt

ROOT = gt.ROOT
RESULTS = ROOT / "results"
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
SOURCE_TOPIC_TYPE = {"airline": "Airline", "airport": "Airport", "regulator": "Organization",
                     "aircraft": "AircraftType", "accident": "Flight"}
TOPIC_OVERRIDE = {"Airworthiness directive": "Regulation"}      # concept-документи, де тема — норма


def split_docs(split, final=False):
    """Список документів частини. test відкривається лише з --final і фіксується в results/test_access.log."""
    sp = json.loads((ROOT / "data" / "split.json").read_text(encoding="utf-8"))
    if split == "test":
        if not final:
            sys.exit("test заборонено для налаштування. Запускай --split test --final лише у Результаті 4.")
        RESULTS.mkdir(exist_ok=True)
        with open(RESULTS / "test_access.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {Path(sys.argv[0]).name} {' '.join(sys.argv[1:])}\n")
        print("УВАГА: відкрито test; результати використовуй лише для фінальної оцінки.")
    return sp[split]


def load_sources():
    with open(ROOT / "data" / "sources.csv", encoding="utf-8") as f:
        return {r["doc_id"]: r for r in csv.DictReader(f)}


def dev_canonicals():
    """canonical-сутності, що зустрічаються в золотому наборі dev-документів (знання, дозволене для налаштування)."""
    dev = set(json.loads((ROOT / "data" / "split.json").read_text(encoding="utf-8"))["dev"])
    out = set()
    for r in gt.read_jsonl(ROOT / "data" / "gold.jsonl"):
        if r["doc_id"] in dev:
            out |= {r["subject"]["canonical"], r["object"]["canonical"]}
    return out


def load_aliases():
    """surface -> (canonical, type); лише аліаси сутностей із dev, щоб test не просочився в методи."""
    allowed, out = dev_canonicals(), {}
    path = ROOT / "data" / "aliases.csv"
    if path.exists():
        for row in csv.reader(path.open(encoding="utf-8")):
            if len(row) >= 3 and row[1] in allowed and not row[0].startswith("#"):
                out[row[0]] = (row[1], row[2])
    return out


def canonical_for(surface, etype, aliases):
    if surface in aliases:
        return aliases[surface]
    return f"{etype.lower()}:{gt.slug(surface)}", etype


def read_doc(doc_id):
    return gt.read_doc(doc_id)


def topic_of(doc_id, text, sources, aliases):
    """Сутність із заголовка документа (для implicit_topic) або None."""
    title = text.split("\n", 1)[0].strip()
    stype = sources.get(doc_id, {}).get("source_type", "")
    ttype = TOPIC_OVERRIDE.get(title) or SOURCE_TOPIC_TYPE.get(stype)
    if stype == "accident" and not ttype == "Flight":
        ttype = None
    if title in aliases:
        return {"text": title, "canonical": aliases[title][0], "type": aliases[title][1]}
    if not ttype:
        return None
    if stype == "accident" and "Flight" not in title:
        ttype = "Event"
    return {"text": title, "canonical": f"{ttype.lower()}:{gt.slug(title)}", "type": ttype}


def paragraphs(text):
    """(зсув, рядок) для змістовних рядків документа; заголовок файлу й назви розділів пропускаються."""
    pos, first = 0, True
    for line in text.split("\n"):
        start = pos
        pos += len(line) + 1
        if first:
            first = False
            continue
        s = line.strip()
        if not s or (len(s) <= 80 and not re.search(r"[.!?:;\"”)]$", s)):
            continue
        yield start + (len(line) - len(line.lstrip())), s


def provenance(method, model, prompt_version, doc_id, **extra):
    return {"method": method, "model": model, "prompt_version": prompt_version, "doc_id": doc_id,
            "run_id": RUN_ID, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), **extra}


def check_prediction(r, text):
    """Список проблем одного передбачення: сигнатура, підрядки, офсети."""
    p = []
    try:
        sig = gt.SIGNATURES[r["relation"]]
        if r["subject"]["type"] not in sig[0] or r["object"]["type"] not in sig[1]:
            p.append("сигнатура")
        if r["relation"] == "AGREEMENT_WITH" and "kind" not in r.get("qualifiers", {}):
            p.append("немає kind")
        ev = r["evidence"]
        if "start" not in ev or text[ev["start"]:ev["end"]] != ev["text"]:
            p.append("evidence не знайдено в тексті")
        for role in ("subject", "object"):
            m = r[role]
            if m.get("implicit_topic"):
                continue
            if "start" not in m or text[m["start"]:m["end"]] != m["text"]:
                p.append(f"{role}: мітку не знайдено")
            elif "start" in ev and not (ev["start"] <= m["start"] and m["end"] <= ev["end"]):
                p.append(f"{role}: поза evidence")
    except (KeyError, TypeError) as e:
        p.append(f"структура: {e}")
    return p


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        k = (r["doc_id"], r["subject"]["canonical"], r["relation"], r["object"]["canonical"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out