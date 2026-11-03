"""Завантаження статей англійської Вікіпедії -> kb/wiki/*.md з YAML-метаданими.
Запуск з кореня проєкту:  python scripts/fetch_wiki.py   (можна запускати повторно)
"""
import json, re, time, datetime as dt, urllib.parse, urllib.request, urllib.error
from pathlib import Path

OUT = Path("kb/wiki"); OUT.mkdir(parents=True, exist_ok=True)
# Вікіпедія просить вказувати контакт у User-Agent — підстав свій email
UA = {"User-Agent": "DomainKnowledgeHub-lab10/1.0 (student project; contact: your_email@example.com)"}
TODAY = dt.date.today().isoformat()
LANG = "en"
PAUSE = 2.0
# Розділи-шум: правило очищення (описати в corpus_card.md)
NOISE = {"see also", "references", "external links", "further reading", "notes",
         "bibliography", "sources", "footnotes", "citations"}

TOPICS = [  # (назва статті, тип)
 ("Airline","overview"), ("Airport","overview"), ("Air cargo","overview"),
 ("Low-cost carrier","overview"), ("Airline alliance","overview"),
 ("Hub airport","operations"), ("Codeshare agreement","operations"),
 ("Wet leasing","operations"), ("Airport slot","operations"),
 ("Overbooking","operations"), ("Revenue management","operations"),
 ("Air traffic control","operations"), ("Air traffic management","operations"),
 ("Air traffic flow management","operations"), ("Flight dispatcher","operations"),
 ("Aircrew","operations"), ("Crew resource management","operations"),
 ("Aircraft maintenance","operations"), ("Ground handling","operations"),
 ("Aviation meteorology","operations"), ("Flight cancellation and delay","operations"),
 ("Global distribution system","operations"), ("Computer reservation system","operations"),
 ("Airline timetable","operations"), ("Fleet planning","operations"),
 ("International Civil Aviation Organization","regulation"),
 ("Convention on International Civil Aviation","regulation"),
 ("International Air Transport Association","regulation"),
 ("Eurocontrol","regulation"), ("Aviation security","regulation"),
 ("Montreal Convention","regulation"), ("Warsaw Convention","regulation"),
 ("Air operator's certificate","regulation"), ("Aviation safety","regulation"),
 ("Regulation (EC) No 261/2004","regulation"),
 ("IATA airport code","reference"), ("ICAO airport code","reference"),
 ("Runway","reference"), ("Airliner","reference"),
]

def api(**p):
    url = f"https://{LANG}.wikipedia.org/w/api.php?" + urllib.parse.urlencode({**p, "format": "json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", 0)) or 10 * (attempt + 1)
                print(f"   429, чекаю {wait}с..."); time.sleep(wait)
            else:
                raise
    raise RuntimeError("забагато 429")

def get_page(title):
    q = api(action="query", prop="extracts", explaintext=1, titles=title, redirects=1)
    pg = next(iter(q["query"]["pages"].values()))
    if "missing" in pg:  # запасний варіант: пошук
        hits = api(action="query", list="search", srsearch=title, srlimit=1)["query"]["search"]
        if not hits: return None, ""
        time.sleep(PAUSE)
        return get_page_exact(hits[0]["title"])
    return pg["title"], pg.get("extract", "")

def get_page_exact(title):
    q = api(action="query", prop="extracts", explaintext=1, titles=title, redirects=1)
    pg = next(iter(q["query"]["pages"].values()))
    return pg.get("title"), pg.get("extract", "")

def clean(text):
    """Прибрати розділи-шум і перетворити == H == на markdown-заголовки."""
    out, skip = [], False
    for line in text.splitlines():
        m = re.match(r"^(={2,})\s*(.+?)\s*\1\s*$", line)
        if m:
            skip = m.group(2).strip().lower() in NOISE
            if not skip: out.append("#" * len(m.group(1)) + " " + m.group(2))
        elif not skip:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()

def slug(s): return re.sub(r"[^\w]+", "_", s.lower()).strip("_")[:50]

seen, ok = set(), 0
for want, typ in TOPICS:
    try:
        fname = OUT / f"{LANG}_{slug(want)}.md"
        if fname.exists(): print("ВЖЕ    ", want); ok += 1; continue
        title, text = get_page(want)
        time.sleep(PAUSE)
        if not title: print("НЕМАЄ  ", want); continue
        if title in seen: print("ДУБЛЬ  ", want, "->", title); continue
        text = clean(text)
        if len(text) < 2000: print("КОРОТКА", title, len(text)); continue
        seen.add(title)
        url = f"https://{LANG}.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        meta = (f"---\ndoc_id: {LANG}_{slug(title)}\ntitle: {title}\nlang: {LANG}\ntype: {typ}\n"
                f"date: {TODAY}\nsensitivity: public\nsource_url: {url}\nlicense: CC BY-SA 4.0\n---\n\n")
        fname = OUT / f"{LANG}_{slug(title)}.md"
        fname.write_text(meta + f"# {title}\n\n" + text, encoding="utf-8")
        ok += 1; print("OK     ", f"{title} ({len(text)} симв.)")
    except Exception as e:
        print("ПОМИЛКА", want, e)
print(f"\nДокументів у kb/wiki: {len(list(OUT.glob('*.md')))}")
