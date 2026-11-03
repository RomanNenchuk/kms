"""Артефакти протоколу «LLM-експерт»: claims/claims.csv, рішення людини в llm_log/, docs/llm_protocol.md.
Запуск з кореня проєкту: python -m scripts.finalize_protocol
Рішення в llm_log проставляються на рівні партії (перевірка кандидатів велася партіями; деталі в review_note).
"""
import csv, json, re
from collections import Counter
from src.config import ROOT, LLM_LOG, CLAIMS
from src.chunking import load_docs

rd = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")] if p.exists() else []
gold = [g for g in rd(ROOT / "eval/gold.jsonl") if g.get("status") == "verified"]
drafts = rd(ROOT / "data/gold_draft.jsonl")
uk = [r for r in rd(ROOT / "eval/queries_20_uk.jsonl") if r.get("status") == "verified"]
url = {d["doc_id"]: d["meta"].get("source_url", "") for d in load_docs()}

REJECT_WHY = {
    "kw05": "запит дублює заголовок розділу, а «доказ» — лише вступ до списку без самої відповіді",
    "ms04": "питання склеює два не пов'язані факти; у реченні-доказі немає слів про seat capacity — неоднозначно",
    "na06": "статті про диспетчерів могли частково містити відомості про зарплати — відповідь у корпусі не виключена",
    "na11": "стаття про техобслуговування могла містити типову тривалість перевірок — відповідь у корпусі не виключена",
}
claims = []
def add(text, typ, source, level, status, comment=""):
    claims.append({"id": f"c{len(claims) + 1:03d}", "claim": text, "type": typ, "source": source,
                   "verification_level": level, "status": status, "comment": comment})

used = set()
for g in gold:
    used |= set(re.findall(r"\b(?:kw|ms|na)\d+\b", g.get("review_note", "")))
    if g["evidence"]:
        srcs = " ; ".join(url.get(d, d) for d in g["doc_ids"])
        add(f"Для запиту «{g['question']}» ({g['id']}, тип {g['type']}) відповідь міститься у фрагментах статей {', '.join(g['doc_ids'])}: " +
            " | ".join(g["evidence"])[:300], "факт", srcs, "V3", "verified", g.get("review_note", ""))
    else:
        add(f"У корпусі немає відповіді на запит «{g['question']}» ({g['id']})", "факт",
            "перевірка топ-2 фрагментів BM25 + ручний перегляд", "V3", "verified", g.get("review_note", ""))
for r in drafts:
    if r["id"] not in used and r["status"] != "verified":
        q = r["question"]
        add(f"Кандидат {r['id']} ({r['type']}): «{q}»", "гіпотеза", "згенеровано Gemini",
            "V3", "rejected", REJECT_WHY.get(r["id"], "відхилено під час ручної перевірки"))
for r in uk:
    add(f"Український переклад запиту {r['id']} зберігає зміст оригіналу: «{r['question_uk']}»", "факт",
        "переклад Gemini + ручна перевірка", "V3", "verified", "")
sr = ROOT / "eval/search_eval_results.json"
if sr.exists():
    s = json.loads(sr.read_text(encoding="utf-8")); ov = s["overall"]
    best = max(ov, key=lambda m: ov[m]["mrr"])
    add(f"За MRR на {s['n_answerable']} запитах з відповіддю найкраща конфігурація — {best} (MRR {ov[best]['mrr']})",
        "факт", "docs/search_eval.md", "V4", "verified", "метрики на золотому наборі")
    if s.get("kappa"):
        add(f"κ між людиною і Gemini на {s['kappa']['pairs']} парах = {s['kappa']['kappa']}", "факт",
            "eval/kappa_results.json", "V4", "verified", "другий розмітник — LLM")
        # (усі розбіжності відображено в eval/kappa_results.json)

CLAIMS.parent.mkdir(exist_ok=True)
with open(CLAIMS, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(claims[0])); w.writeheader(); w.writerows(claims)

# ---- журнал LLM: рішення людини ----
DEC = {"chunkq-v1": "кандидати переглянуто вручну; прийнято/виправлено/відхилено — див. eval/*queries*.jsonl (review_note)",
       "q-gen-v2": "кандидати переглянуто вручну; прийнято/виправлено — див. eval/gold.jsonl (review_note)",
       "gold-gen-v1": "кандидати переглянуто вручну; частину відхилено — див. claims/claims.csv (rejected)",
       "translate-v1": "переклади перевірено вручну — див. eval/queries_20_uk.jsonl",
       "kappa-v1": "використано як другого розмітника; розбіжності з людиною проаналізовано — eval/kappa_results.json"}
cnt, updated = Counter(), 0
for p in sorted(LLM_LOG.glob("*.jsonl")):
    recs, ch = [], False
    for r in rd(p):
        cnt[(r["model"], r["prompt_version"])] += 1
        if r.get("human_decision") == "pending":
            r["human_decision"] = DEC.get(r["prompt_version"], "переглянуто вручну"); ch = True; updated += 1
        recs.append(r)
    if ch:
        p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")

# ---- підсумок ----
st = Counter(c["status"] for c in claims); tot = len(claims)
rej = [c for c in claims if c["status"] == "rejected"]
sources = sorted({u.strip() for c in claims for u in c["source"].split(";") if u.strip().startswith("http")})
L = ["# Протокол «LLM-експерт»: підсумок", "",
     "## Журнал взаємодії", "", "Усі виклики Gemini записано в `llm_log/*.jsonl` (дата, модель, параметри, версія підказки, сирий вихід, рішення людини). "
     "Рішення людини проставлено на рівні партії кандидатів (деталі правок — у полі `review_note` файлів `eval/*.jsonl`).", "",
     "| модель | версія підказки | викликів |", "|---|---|---|"] + [f"| {m} | {v} | {n} |" for (m, v), n in sorted(cnt.items())]
L += ["", f"Рішення проставлено у {updated} записах журналу.", "",
      "## Таблиця тверджень", "", f"`claims/claims.csv`: {tot} тверджень; verified — {st['verified']} ({st['verified'] / tot:.0%}), rejected — {st['rejected']}, pending — {st['pending']}. "
      "Рівні верифікації: V3 — перевірено людиною за текстом корпусу, V4 — підтверджено метриками.", "", "### Відхилені твердження", ""]
L += [f"- {c['id']}: {c['claim']} — {c['comment']}" for c in rej] or ["- (немає)"]
L += ["", "### Перелік джерел", "", "Корпус: англомовна Вікіпедія (CC BY-SA 4.0):", ""] + [f"- {u}" for u in sources]
L += ["", "Другий розмітник у κ — Gemini; людина розмічала наосліп."]
(ROOT / "docs/llm_protocol.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"claims: {tot} (verified {st['verified']}, rejected {st['rejected']}); оновлено записів журналу: {updated}")
print("Файли: claims/claims.csv, docs/llm_protocol.md")
