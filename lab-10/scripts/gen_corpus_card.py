"""data/corpus.jsonl -> docs/corpus_card.md (авто-частини). Запуск: python scripts/gen_corpus_card.py"""
import json, datetime as dt
from pathlib import Path
from collections import OrderedDict, Counter

rows = [json.loads(l) for l in open("data/corpus.jsonl", encoding="utf-8")]
docs = OrderedDict()
for r in rows:
    d = docs.setdefault(r["doc_id"], {**{k: r[k] for k in ("title","type","source_url","license","date","lang")}, "n": 0})
    d["n"] += 1
lens = [len(r["text"]) for r in rows]
sens = Counter(r["sensitivity"] for r in rows)
ovr_path = Path("data/sensitivity_overrides.json")
ovr = json.loads(ovr_path.read_text(encoding="utf-8")) if ovr_path.exists() else {}
restricted = [r for r in rows if r["sensitivity"] == "restricted"]

L = ["# Картка корпусу", "",
 "## Загальне",
 "- Домен: управління авіаційними перевезеннями (проєкт Domain Knowledge Hub)",
 f"- Мова: {', '.join(sorted({r['lang'] for r in rows}))} (одномовний корпус; моделі embeddings багатомовні)",
 f"- Документів: {len(docs)}; фрагментів: {len(rows)}; довжина фрагмента, симв.: min {min(lens)}, середня {sum(lens)//len(lens)}, max {max(lens)}",
 f"- Дата збору: {max(d['date'] for d in docs.values())}",
 "- Формат: `data/corpus.jsonl` (chunk_id, doc_id, title, section, type, date, sensitivity, source_url, lang, license, text)",
 "", "## Джерела та ліцензії",
 "Усі документи — статті англійської Вікіпедії (ліцензія CC BY-SA 4.0), завантажені через MediaWiki API.", "",
 "| doc_id | назва | тип | ліцензія | фрагментів | джерело |", "|---|---|---|---|---|---|"]
for k, d in docs.items():
    L.append(f"| {k} | {d['title']} | {d['type']} | {d['license']} | {d['n']} | {d['source_url']} |")
L += ["", "## Правила очищення від шуму",
 "1. Беремо лише текст статті (plain text через `explaintext`): таблиці, зображення, інфобокси та розмітка відсутні.",
 "2. Видаляємо розділи без змістовного тексту: See also, References, External links, Further reading, Notes, Bibliography, Sources, Footnotes, Citations.",
 "3. Заголовки `== X ==` перетворено на markdown `## X`; зайві порожні рядки стиснуто.",
 "4. Статті коротші за 2000 символів відкинуто.",
 "5. Розбиття: за заголовками; розділи довші за 1200 символів діляться по абзацах/реченнях; фрагменти коротші за 250 символів склеюються із сусіднім у межах розділу; фрагменти коротші за 80 символів відкидаються.",
 "6. Вручну прибрано статті не за темою (напр., загальна «Meteorology»).",
 "", "## Розподіл за sensitivity",
 *[f"- {k}: {v}" for k, v in sorted(sens.items())],
 "", "Правило: `public` — за замовчуванням для відкритих джерел; `internal` — власні матеріали; "
 "`restricted` — фрагмент, де знайдено email, телефон або позначку «confidential / для службового користування». "
 "Автоматичну мітку можна змінити вручну (`data/sensitivity_overrides.json`) із поясненням:"]
if ovr:
    L += ["", "| chunk_id | нова мітка | причина |", "|---|---|---|"]
    L += [f"| {k} | {v['label']} | {v['reason']} |" for k, v in ovr.items()]
else:
    L.append("(ручних змін немає)")
if restricted:
    L += ["", "Фрагменти з міткою restricted: " + ", ".join(r["chunk_id"] for r in restricted)]
L += ["", "## Відомі прогалини",
 "- Лише вторинне енциклопедичне джерело; немає первинних нормативних текстів (повні Annex ICAO, регламенти ЄС, Повітряний кодекс України).",
 "- Немає операційних даних авіакомпаній/аеропортів (розклади, інциденти, внутрішні регламенти).",
 "- Лише англійська мова; українські запити перевірятимемо окремо як cross-lingual.",
 "- Зрізи статей на дату збору; Вікіпедія може містити неточності й не завжди актуальна.",
 "- Таблиці й зображення не збережено, тому табличні факти недоступні для пошуку.",
 "- Нерівномірність: деякі теми (Airline, Airport) охоплені значно ширше за інші."]
Path("docs/corpus_card.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("docs/corpus_card.md записано")
