"""Результат 2: три стратегії chunking.

Кожен фрагмент — dict:
  chunk_id, doc_id, title, section, text  — те, що індексується (embeddings)
  context                                  — те, що віддається користувачеві/LLM
У fixed і headings context == text; у hierarchical context — батьківський розділ.
"""
import re
from pathlib import Path
from .config import ROOT


# ---------- завантаження документів ----------
def parse_doc(path):
    raw = Path(path).read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        raw = raw[m.end():]
    meta.setdefault("doc_id", Path(path).stem)
    meta.setdefault("title", Path(path).stem)
    return meta, raw


def load_docs(kb_dir=None):
    kb_dir = Path(kb_dir) if kb_dir else ROOT / "kb"
    docs = []
    for p in sorted(kb_dir.rglob("*.md")):
        meta, body = parse_doc(p)
        docs.append({"doc_id": meta["doc_id"], "title": meta["title"], "meta": meta, "body": body})
    return docs


def sections(body, title):
    """[(section_title, text)] за markdown-заголовками."""
    out, cur, buf = [], title, []
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            if "".join(buf).strip():
                out.append((cur, "\n".join(buf).strip()))
            cur, buf = m.group(2).strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        out.append((cur, "\n".join(buf).strip()))
    return out


def _mk(doc, i, section, text, context=None, tag=""):
    return {"chunk_id": f"{doc['doc_id']}{tag}#{i:03d}", "doc_id": doc["doc_id"],
            "title": doc["title"], "section": section, "text": text,
            "context": context if context is not None else text}


# ---------- 1. фіксований розмір з overlap ----------
def fixed_chunks(docs, size=800, overlap=160):
    out = []
    for d in docs:
        text = re.sub(r"\n{2,}", "\n", d["body"]).strip()
        start, i, n = 0, 0, len(text)
        while start < n:
            end = min(start + size, n)
            if end < n:  # не різати посеред слова
                ws = text.rfind(" ", start + int(size * 0.85), end)
                end = ws if ws > start else end
            piece = text[start:end].strip()
            if len(piece) >= 80:
                out.append(_mk(d, i, "", piece)); i += 1
            if end >= n:
                break
            nxt = end - overlap
            ws = text.find(" ", nxt)
            start = ws + 1 if 0 <= ws < end else end
    return out


# ---------- 2. за заголовками / структурою ----------
def _split_long(text, max_chars):
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        if len(cur) + len(para) > max_chars and cur:
            parts.append(cur.strip()); cur = ""
        while len(para) > max_chars:
            cut = para.rfind(". ", 0, max_chars) + 1 or max_chars
            parts.append((cur + "\n\n" + para[:cut]).strip()); cur, para = "", para[cut:].strip()
        cur += "\n\n" + para
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _section_pieces(d, max_chars, min_chars, drop_chars=80):
    pieces = []
    for sec, text in sections(d["body"], d["title"]):
        for p in _split_long(text, max_chars):
            if pieces and len(pieces[-1][1]) < min_chars and pieces[-1][0] == sec:
                pieces[-1] = (sec, pieces[-1][1] + "\n\n" + p)
            else:
                pieces.append((sec, p))
    return [(s, t) for s, t in pieces if len(t) >= drop_chars]


def heading_chunks(docs, max_chars=1200, min_chars=250):
    out = []
    for d in docs:
        for i, (sec, t) in enumerate(_section_pieces(d, max_chars, min_chars)):
            out.append(_mk(d, i, sec, t))
    return out


# ---------- 3. ієрархічна (parent-child) ----------
def hierarchical_chunks(docs, child_size=350, parent_max=1500, parent_min=250):
    out = []
    for d in docs:
        j = 0
        for sec, parent in _section_pieces(d, parent_max, parent_min):
            sents = re.split(r"(?<=[.!?])\s+|\n+", parent)
            cur = ""
            for s in sents:
                if cur and len(cur) + len(s) + 1 > child_size:
                    if len(cur) >= 60:
                        out.append(_mk(d, j, sec, cur.strip(), context=parent, tag="c")); j += 1
                    cur = ""
                cur += (" " if cur else "") + s
            if len(cur) >= 60:
                out.append(_mk(d, j, sec, cur.strip(), context=parent, tag="c")); j += 1
    return out


STRATEGIES = {"fixed": fixed_chunks, "headings": heading_chunks, "hierarchical": hierarchical_chunks}


if __name__ == "__main__":
    docs = load_docs()
    print(f"Документів: {len(docs)}")
    for name, fn in STRATEGIES.items():
        ch = fn(docs)
        avg_t = sum(len(c["text"]) for c in ch) // len(ch)
        avg_c = sum(len(c["context"]) for c in ch) // len(ch)
        print(f"{name:13s} фрагментів={len(ch):5d}  сер. text={avg_t:5d}  сер. context={avg_c:5d}")
