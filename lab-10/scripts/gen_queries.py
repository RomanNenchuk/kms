"""Генерація кандидатів запитів (питання + речення-доказ) через Gemini.
Приклад:
  python -m scripts.gen_queries --n 10 --exclude eval/chunking_queries.jsonl \
      --out data/queries_batch2_draft.jsonl --start-id 11 --seed-offset 1
Кожен виклик пишеться в llm_log/. Результат ти перевіряєш і правиш вручну.
"""
import argparse, json, random, re
from src.config import ROOT, SEED
from src.chunking import load_docs, sections
from src.llm import ask

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=10)
ap.add_argument("--exclude", default=None, help="jsonl з уже використаними запитами (беремо інші статті)")
ap.add_argument("--out", required=True)
ap.add_argument("--start-id", type=int, default=1)
ap.add_argument("--seed-offset", type=int, default=0)
args = ap.parse_args()

PROMPT_VERSION = "q-gen-v2"
SYSTEM = "You write evaluation questions for a retrieval system. Output JSON only."
TEMPLATE = """Read the passage and write ONE question that a user could ask a search system about air transport,
whose answer is stated in the passage.
Rules:
- Natural wording, like a real user would type. Do not start with "Which specific".
- Self-contained: name the topic explicitly; never say "the passage", "this text" or "the article".
- Paraphrase; do not copy the wording of the answer sentence.
- Prefer a question whose answer is a fact, definition, reason, number or name.
- "evidence" must be ONE short sentence (under 220 characters) copied EXACTLY, character for character,
  from the passage, that directly answers the question. Do not use list-like sentences.
Return JSON: {{"question": "...", "evidence": "..."}}

Passage (from the article "{title}", section "{section}"):
\"\"\"
{passage}
\"\"\""""

norm = lambda s: re.sub(r"\s+", " ", s).strip()

used_docs = set()
if args.exclude:
    used_docs = {json.loads(l)["doc_id"] for l in open(ROOT / args.exclude, encoding="utf-8")}

rng = random.Random(SEED + args.seed_offset)
docs = [d for d in load_docs() if d["doc_id"] not in used_docs]
rng.shuffle(docs)
print(f"Доступних статей: {len(docs)} (виключено {len(used_docs)})")

out = []
for d in docs:
    if len(out) >= args.n:
        break
    cands = [(s, t) for s, t in sections(d["body"], d["title"])
             if 500 <= len(t) <= 1500 and sum(len(l) > 60 for l in t.splitlines()) >= 3]
    if not cands:
        continue
    sec, passage = rng.choice(cands)
    for _ in range(3):
        raw = ask(TEMPLATE.format(title=d["title"], section=sec, passage=passage),
                  PROMPT_VERSION, temperature=0.3, system=SYSTEM, json_mode=True)
        try:
            j = json.loads(raw)
            q, ev = j["question"].strip(), norm(j["evidence"])
        except Exception:
            continue
        if ev in norm(passage) and 40 <= len(ev) <= 220:
            qid = f"q{args.start_id + len(out):02d}"
            out.append({"id": qid, "doc_id": d["doc_id"], "section": sec,
                        "question": q, "evidence": ev, "status": "pending"})
            print(f"{qid} [{d['title']} / {sec}]\n   Q: {q}\n   E: {ev}\n")
            break
    else:
        print("пропуск:", d["title"])

path = ROOT / args.out
path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
print(f"Записано {len(out)} кандидатів -> {path}")
