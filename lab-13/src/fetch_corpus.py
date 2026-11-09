"""Завантаження корпусу з англійської Вікіпедії (MediaWiki API).

Запуск:
  python src/fetch_corpus.py             # свіжі версії статей, фіксує revid у data/sources.csv
  python src/fetch_corpus.py --pinned    # відтворює корпус за revid із data/sources.csv

Результат: data/raw/Dxx.txt (назва + чистий текст) і data/sources.csv (permalink з oldid, ліцензія).
Лише стандартна бібліотека; User-Agent без персональних даних (вимога політики Wikimedia).
"""
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SOURCES = ROOT / "data" / "sources.csv"
API = "https://en.wikipedia.org/w/api.php"
UA = os.getenv("WIKI_USER_AGENT", "kms-lab13-student/1.0 (university lab; text-extraction exercise)")
PAUSE = 1.5               # секунд між запитами (ввічливий темп для API)
RETRIES = 6
MAX_CHARS = 4000          # фрагмент статті на документ (обрізання по абзацу)
MIN_DOCS = 22             # потрібно ≥ 20 + запас

# (тип джерела, назва статті). Кандидатів більше за MIN_DOCS: відсутні сторінки пропускаються.
TITLES = [
    ("airline", "Lufthansa"), ("airline", "Ryanair"), ("airline", "Wizz Air"),
    ("airline", "Ukraine International Airlines"), ("airline", "Austrian Airlines"),
    ("airport", "Warsaw Chopin Airport"), ("airport", "Vienna Airport"),
    ("airport", "Lviv Danylo Halytskyi International Airport"), ("airport", "Frankfurt Airport"),
    ("regulator", "European Union Aviation Safety Agency"),
    ("regulator", "International Civil Aviation Organization"),
    ("regulator", "National Transportation Safety Board"),
    ("accident", "Gimli Glider"), ("accident", "US Airways Flight 1549"),
    ("accident", "Tenerife airport disaster"), ("accident", "Germanwings Flight 9525"),
    ("accident", "British Airways Flight 38"),
    ("aircraft", "Airbus A320neo family"), ("aircraft", "Embraer E-Jet E2 family"),
    ("aircraft", "Boeing 767"),
    ("concept", "Airport slot"), ("concept", "Codeshare agreement"), ("concept", "Air traffic control"),
    ("concept", "Bird strike"), ("concept", "Airworthiness directive"), ("concept", "Ground handling"),
    ("concept", "Air traffic flow management"), ("concept", "Star Alliance"),
]


def api_get(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == RETRIES - 1:
                raise
            wait = int(e.headers.get("Retry-After", 0) or 0) or 5 * 2 ** attempt
            print(f"  HTTP {e.code}, чекаю {wait} c (спроба {attempt + 1}/{RETRIES})...")
            time.sleep(wait)


def fetch(title, revid=None):
    """Повертає (title, revid, timestamp, text) або None, якщо сторінки немає."""
    params = {"action": "query", "prop": "extracts|revisions", "explaintext": 1,
              "exsectionformat": "plain", "rvprop": "ids|timestamp", "format": "json",
              "formatversion": 2, "redirects": 1}
    params["revids" if revid else "titles"] = revid or title
    data = api_get(params)
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or "extract" not in pages[0]:
        return None
    p = pages[0]
    rev = p["revisions"][0]
    return p["title"], rev["revid"], rev["timestamp"], clean(p["extract"])


def clean(text):
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    out, n = [], 0
    for para in text.split("\n\n"):
        if n + len(para) > MAX_CHARS and out:
            break
        out.append(para)
        n += len(para) + 2
    return "\n\n".join(out)


def main():
    pinned = "--pinned" in sys.argv
    old = {}
    if pinned:
        with open(SOURCES, encoding="utf-8") as f:
            old = {row["title"]: int(row["revid"]) for row in csv.DictReader(f)}
    rows, texts, skipped = [], {}, []
    for stype, title in TITLES:
        if len(rows) >= MIN_DOCS + 4 and not pinned:
            break
        got = fetch(title, old.get(title)) if (not pinned or title in old) else None
        time.sleep(PAUSE)
        if not got:
            skipped.append(title)
            continue
        real_title, revid, ts, text = got
        did = f"D{len(rows) + 1:02d}"
        texts[did] = f"{real_title}\n\n{text}\n"
        rows.append({
            "doc_id": did, "file": f"data/raw/{did}.txt", "source_type": stype,
            "publisher": "Wikipedia (English)", "date": ts[:10], "title": real_title, "revid": revid,
            "url": f"https://en.wikipedia.org/w/index.php?title={urllib.parse.quote(real_title.replace(' ', '_'))}&oldid={revid}",
            "license": "CC BY-SA 4.0", "retrieved": date.today().isoformat(), "chars": len(text),
        })
        print(f"{did} {real_title} (rev {revid}, {len(text)} chars)")
    if len(rows) < MIN_DOCS:
        sys.exit(f"Замало документів ({len(rows)} < {MIN_DOCS}); нічого не записано. Пропущено: {skipped}")
    RAW.mkdir(parents=True, exist_ok=True)
    for f in RAW.glob("D*.txt"):
        f.unlink()
    for did, t in texts.items():
        (RAW / f"{did}.txt").write_text(t, encoding="utf-8")
    with open(SOURCES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nГотово: {len(rows)} документів. Пропущено (немає сторінки): {skipped or '—'}")


if __name__ == "__main__":
    main()
