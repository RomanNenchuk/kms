"""Переклад 20 запитів українською через Gemini (для порівняння за мовою).
Запуск: python -m scripts.translate_queries
Вхід: eval/queries_20.jsonl   Вихід: eval/queries_20_uk_draft.jsonl (ти перевіряєш)
"""
import json
from src.config import ROOT
from src.llm import ask

SYSTEM = "You are a professional EN->UK translator for aviation terminology. Output JSON only."
PROMPT = """Translate each question into natural Ukrainian, as a native speaker would type it into a search box.
Rules:
- Keep proper names, airline names, airports and abbreviations (ICAO, IATA, GDS, CRS etc.) as in the original.
- Use standard Ukrainian aviation terminology.
- Do not add or remove information.
Return JSON: {{"translations": [{{"id": "...", "question_uk": "..."}}, ...]}}

Questions:
{items}"""

qs = [json.loads(l) for l in open(ROOT / "eval" / "queries_20.jsonl", encoding="utf-8")]
qs = [q for q in qs if q.get("status") == "verified"]
items = "\n".join(f'{q["id"]}: {q["question"]}' for q in qs)
raw = ask(PROMPT.format(items=items), "translate-v1", temperature=0.2, system=SYSTEM, json_mode=True)
tr = {t["id"]: t["question_uk"].strip() for t in json.loads(raw)["translations"]}
missing = [q["id"] for q in qs if q["id"] not in tr]
assert not missing, f"немає перекладів для {missing}"

out = [{"id": q["id"], "question_en": q["question"], "question_uk": tr[q["id"]], "status": "pending"} for q in qs]
path = ROOT / "eval" / "queries_20_uk_draft.jsonl"
path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
for r in out:
    print(f'{r["id"]}\n   EN: {r["question_en"]}\n   UK: {r["question_uk"]}')
print(f"\nЗаписано {len(out)} -> {path}")
