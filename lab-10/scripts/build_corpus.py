"""kb/**/*.md -> data/corpus.jsonl (фрагменти + метадані). Запуск: python scripts/build_corpus.py"""
import json, re, random
from pathlib import Path
from collections import Counter

KB, OUT = Path("kb"), Path("data/corpus.jsonl")
OVR = Path("data/sensitivity_overrides.json")  # {"chunk_id": {"label": "public", "reason": "..."}}
overrides = json.loads(OVR.read_text(encoding="utf-8")) if OVR.exists() else {}
MAX_CHARS, MIN_CHARS, DROP_CHARS = 1200, 250, 80

RESTRICTED_RE = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.-]+|\+?\d[\d\s().-]{8,}\d|confidential|internal use only|конфіденційно|для службового користування",
    re.I)

def parse(path):
    raw = path.read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1); meta[k.strip()] = v.strip()
        raw = raw[m.end():]
    return meta, raw

def sections(body, title):
    """Повертає [(section, text)] за заголовками markdown."""
    out, cur, buf = [], title, []
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            if "".join(buf).strip(): out.append((cur, "\n".join(buf).strip()))
            cur, buf = m.group(2).strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip(): out.append((cur, "\n".join(buf).strip()))
    return out

def split_long(text):
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        if len(cur) + len(para) > MAX_CHARS and cur:
            parts.append(cur.strip()); cur = ""
        while len(para) > MAX_CHARS:            # дуже довгий абзац — ріжемо по реченнях
            cut = para.rfind(". ", 0, MAX_CHARS) + 1 or MAX_CHARS
            parts.append((cur + "\n\n" + para[:cut]).strip()); cur, para = "", para[cut:].strip()
        cur += "\n\n" + para
    if cur.strip(): parts.append(cur.strip())
    return parts

def chunk_doc(meta, body):
    pieces = []
    for sec, text in sections(body, meta["title"]):
        for p in split_long(text):
            if pieces and len(pieces[-1][1]) < MIN_CHARS and pieces[-1][0] == sec:
                pieces[-1] = (sec, pieces[-1][1] + "\n\n" + p)   # склеюємо малі
            else:
                pieces.append((sec, p))
    return [(s, t) for s, t in pieces if len(t) >= DROP_CHARS]

rows = []
for path in sorted(KB.rglob("*.md")):
    meta, body = parse(path)
    meta.setdefault("doc_id", path.stem); meta.setdefault("title", path.stem)
    meta.setdefault("type", "internal_doc"); meta.setdefault("date", "unknown")
    meta.setdefault("source_url", f"local:{path.as_posix()}"); meta.setdefault("lang", "en")
    meta.setdefault("license", "own work")
    default_sens = "public" if "wikipedia.org" in meta["source_url"] else "internal"
    meta.setdefault("sensitivity", default_sens)
    for i, (sec, text) in enumerate(chunk_doc(meta, body)):
        sens = "restricted" if RESTRICTED_RE.search(text) else meta["sensitivity"]
        cid = f"{meta['doc_id']}#{i:03d}"
        if cid in overrides: sens = overrides[cid]["label"]
        rows.append({"chunk_id": f"{meta['doc_id']}#{i:03d}", "doc_id": meta["doc_id"],
                     "title": meta["title"], "section": sec, "type": meta["type"],
                     "date": meta["date"], "sensitivity": sens, "source_url": meta["source_url"],
                     "lang": meta["lang"], "license": meta["license"], "text": text})

OUT.parent.mkdir(exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")

lens = [len(r["text"]) for r in rows]
print(f"Документів: {len({r['doc_id'] for r in rows})}   Фрагментів: {len(rows)}")
print(f"Довжина фрагмента, симв.: min={min(lens)} avg={sum(lens)//len(lens)} max={max(lens)}")
print("За sensitivity:", dict(Counter(r['sensitivity'] for r in rows)))
print("За type:", dict(Counter(r['type'] for r in rows)))
