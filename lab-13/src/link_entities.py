"""Зв'язування сутностей з Wikidata. Запускати ЛОКАЛЬНО (потрібен інтернет до wikidata.org).

  python src/link_entities.py --top 40       # -> data/entity_links.csv (кандидати)
Далі відкрий CSV і в колонці `verified` постав:  y  (кандидат правильний), n (жоден не підходить),
або впиши інший QID. Рядки з y або QID потрапляють у граф.
"""
import argparse
import csv
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

import gold_tools as gt

API = "https://www.wikidata.org/w/api.php"
UA = "kms-lab13-entity-linking/1.0 (university lab; contact via GitHub RomanNenchuk)"
KEYWORDS = {
    "Airline": r"airline|carrier|air cargo|aviation company",
    "Airport": r"airport|airfield|air base",
    "AircraftType": r"aircraft|airliner|jet|airplane|helicopter|family",
    "Organization": r"company|corporation|organi[sz]ation|agency|authority|board|group|manufacturer|alliance|association|administration",
    "Location": r"city|town|country|state|region|capital|district|municipality|island|province|continent",
    "Flight": r"flight|accident|crash|disaster|incident",
    "Event": r"accident|crash|disaster|incident|attack|event",
    "Person": r"pilot|captain|person|businessman|aviator|executive",
    "Regulation": r"directive|regulation|act|law|agreement|standard",
}


def call(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(2 ** attempt)
    return {}


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def score(label_text, etype, cand):
    s = 0.0
    names = [cand.get("label", "")] + [a for a in cand.get("aliases", [])]
    if norm(label_text) == norm(cand.get("label", "")):
        s += 0.6
    elif any(norm(label_text) == norm(n) for n in names):
        s += 0.4
    elif norm(label_text) in norm(cand.get("label", "")) or norm(cand.get("label", "")) in norm(label_text):
        s += 0.2
    if re.search(KEYWORDS.get(etype, "."), cand.get("description", "") or "", re.I):
        s += 0.35
    return round(min(s, 1.0), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=40, help="скільки найчастіших сутностей зв'язувати")
    ap.add_argument("--out", default=str(gt.ROOT / "data" / "entity_links.csv"))
    a = ap.parse_args()
    cnt, etype, surf = Counter(), {}, defaultdict(Counter)
    for r in gt.read_jsonl(gt.ROOT / "data" / "gold.jsonl"):
        for role in ("subject", "object"):
            m = r[role]
            cnt[m["canonical"]] += 1
            etype[m["canonical"]] = m["type"]
            if m.get("text"):
                surf[m["canonical"]][m["text"]] += 1
    rows = []
    for canon, n in cnt.most_common(a.top):
        t = etype[canon]
        # мітка для пошуку: найчастіша форма з тексту (або з канонічного імені)
        label = surf[canon].most_common(1)[0][0] if surf[canon] else canon.split(":", 1)[1].replace("_", " ")
        res = call({"action": "wbsearchentities", "search": label, "language": "en", "type": "item", "limit": 5})
        cands = res.get("search", [])
        best = None
        for c in cands:
            c["aliases"] = c.get("aliases", []) + ([c["match"]["text"]] if c.get("match") else [])
            c["_score"] = score(label, t, c)
            if best is None or c["_score"] > best["_score"]:
                best = c
        alt = "; ".join(f'{c["id"]}:{c.get("label","")} ({c.get("description","")})' for c in cands[:5])
        rows.append({"canonical": canon, "type": t, "claims": n, "search_label": label,
                     "qid": best["id"] if best else "", "wd_label": best.get("label", "") if best else "",
                     "wd_description": best.get("description", "") if best else "",
                     "score": best["_score"] if best else 0, "alternatives": alt, "verified": ""})
        print(f'{canon:55} -> {rows[-1]["qid"]:10} {rows[-1]["wd_label"]} [{rows[-1]["score"]}]')
        time.sleep(0.3)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Записано {len(rows)} -> {a.out}. Заповни колонку verified (y / n / інший QID).")


if __name__ == "__main__":
    main()