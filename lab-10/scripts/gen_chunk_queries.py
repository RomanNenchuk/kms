"""Генерує 10 кандидатів тестових запитів (питання + речення-доказ) через Gemini.
Запуск з кореня проєкту: python -m scripts.gen_chunk_queries
Результат: data/chunking_queries_draft.jsonl  (ти перевіряєш і правиш вручну)
"""
import json, random, re
from src.config import ROOT, SEED
from src.chunking import load_docs, sections
from src.llm import ask

PROMPT_VERSION = "chunkq-v1"
N = 10
SYSTEM = "You write evaluation questions for a retrieval system. Output JSON only."
TEMPLATE = """Read the passage and write ONE question that a user could ask a search system about air transport,
whose answer is stated in the passage.
Rules:
- The question must be self-contained: name the topic explicitly; never say "the passage", "this text" or "the article".
- Do not copy the wording of the answer sentence; paraphrase.
- "evidence" must be ONE sentence copied EXACTLY (character for character) from the passage that answers the question.
Return JSON: {{"question": "...", "evidence": "..."}}

Passage (from the article "{title}", section "{section}"):
\"\"\"
{passage}
\"\"\""""

norm = lambda s: re.sub(r"\s+", " ", s).strip()

rng = random.Random(SEED)
docs = load_docs()
rng.shuffle(docs)
out = []
for d in docs:
    if len(out) >= N:
        break
    cands = [(s, t) for s, t in sections(d["body"], d["title"])
             if 500 <= len(t) <= 1500 and sum(len(l) > 60 for l in t.splitlines()) >= 3]
    if not cands:
        continue
    sec, passage = rng.choice(cands)
    for attempt in range(3):
        raw = ask(TEMPLATE.format(title=d["title"], section=sec, passage=passage),
                  PROMPT_VERSION, temperature=0.3, system=SYSTEM, json_mode=True)
        try:
            j = json.loads(raw)
            q, ev = j["question"].strip(), j["evidence"].strip()
        except Exception:
            continue
        if norm(ev) in norm(passage) and len(ev) > 30:   # доказ — справжня цитата
            out.append({"id": f"q{len(out)+1:02d}", "doc_id": d["doc_id"], "section": sec,
                        "question": q, "evidence": norm(ev), "status": "pending"})
            print(f"{out[-1]['id']} [{d['title']} / {sec}]\n   Q: {q}\n   E: {norm(ev)}\n")
            break
    else:
        print("пропуск (не вдалося отримати коректну цитату):", d["title"])

path = ROOT / "data" / "chunking_queries_draft.jsonl"
path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
print(f"Записано {len(out)} кандидатів -> {path}")
