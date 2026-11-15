"""Питання до бази знань для демонстратора (без LLM): пошук у KB (mcp_server/vector.py) з трьома можливими статусами:
  ANSWER    — знайдено фрагмент(и); відповідь екстрактивна (уривок документа) + id цитат kb:<chunk_id>;
  NO_ANSWER — «не знаю»: терміни питання не покриваються знайденими фрагментами (поріг COVERAGE_MIN) АБО питання не називає
              тему, на яку є документ (жоден термін не збігається з назвою/розділом знайдених фрагментів — «заземлення»);
  REFUSED   — у питанні ознаки prompt injection (mcp_server/guards.py), пошук не виконується.
Права: рівень доступу користувача застосовується як pre-filter у vector.search."""
import re
from mcp_server import guards, vector

COVERAGE_MIN = 0.5
STOP = set("""a an the of in on at to for from by with and or is are was were be been being what who whom which when where why how
does do did can could should would will shall may might this that these those it its as about into than then there their they them you your
we our i me my tell explain describe give please define meaning mean much many some any""".split())


def terms(q: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-zа-яіїєґ0-9]+", q.lower()) if w not in STOP and len(w) > 2}


def strip_wrapper(text: str) -> str:
    return re.sub(r"</?untrusted_document[^>]*>\s*", "", text).strip()


def ask(question: str, level: str = "public", k: int = 3) -> dict:
    flags = guards.scan_untrusted(question)
    if flags:
        return {"status": "REFUSED", "reason": "possible_prompt_injection", "flags": flags, "question": question}
    q_terms = terms(question)
    res = vector.search(question, k, level)
    chunks = res["results"]
    if not q_terms or not chunks:
        return {"status": "NO_ANSWER", "reason": "no_relevant_passages", "coverage": 0.0, "question": question}
    texts = " ".join(strip_wrapper(c["text"]).lower() for c in chunks)
    hit = {t for t in q_terms if t in texts}
    coverage = len(hit) / len(q_terms)
    if coverage < COVERAGE_MIN:
        return {"status": "NO_ANSWER", "reason": "low_coverage", "coverage": round(coverage, 2),
                "missing_terms": sorted(q_terms - hit), "question": question}
    head = set()
    for c in chunks:
        head |= terms(c["title"] + " " + (c.get("section") or ""))
    if not (q_terms & head):                       # терміни є в тексті, але питання не про тему жодного з документів
        return {"status": "NO_ANSWER", "reason": "topic_not_in_knowledge_base", "coverage": round(coverage, 2), "question": question}
    best = chunks[0]
    snippet = strip_wrapper(best["text"])
    sents = re.split(r"(?<=[.!?])\s+", snippet)
    return {"status": "ANSWER", "answer": " ".join(sents[:3])[:600], "title": best["title"], "coverage": round(coverage, 2),
            "citations": [{"id": c["id"], "title": c["title"], "source_url": c.get("source_url")} for c in chunks],
            "mode": res["mode"], "question": question}
