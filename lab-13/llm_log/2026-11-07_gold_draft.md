# Журнал: чернетка золотого набору

- **Дата:** 2026-11-07
- **Модель:** Claude Sonnet 5.5 (`claude-sonnet-5-5`), Claude Code CLI
- **Результат:** `data/gold_draft_raw.jsonl` → `data/gold_draft.jsonl`; `aliases.csv`; `gold_notes.md`
- **Кількість тверджень:** 153 у 24 документах із 26 (D23, D24 — 0). Ціль ≥ 170 не досягнута: текст не підтримує більше тверджень без порушення R1 (див. `data/gold_notes.md`).
- **Перевірка:** `gold_tools.py fill` — без помилок; `validate` — «OK: 153 тверджень валідні»; `stats` — SERVES 32, OWNS_STAKE_IN 30, HUB_AT 23, LOCATED_IN 20, INVOLVED_IN 14, OPERATES 11, AGREEMENT_WITH 9, ISSUED_BY 9, MANUFACTURED_BY 3, OPERATED_BY 2; asserted 149 / planned 4.
- **Статус:** чернетка, потребує ручної перевірки автором (кожне твердження звірити з текстом).

## Промпт

Прочитай docs/extraction_schema.md (схема v1.2, правила R1–R12, граничні випадки, приклади) і data/sources.csv.

Завдання: зроби чернетку золотого набору для всіх документів data/raw/D01.txt … D26.txt.

1. Читай кожен документ повністю. Витягай лише твердження, які прямо сказані в тексті (R1), строго за схемою: 9 типів сутностей, 10 відношень, сигнатури, qualifiers, modality, implicit_topic.
2. Результат записуй у data/gold_draft_raw.jsonl, по одному JSON на рядок, БЕЗ claim_id і БЕЗ start/end. Поля: doc_id, subject, relation, object, evidence{text}, qualifiers (якщо є), modality, annotator="claude-draft". У subject/object: type, canonical, text (або implicit_topic:true без text).
3. Усі text (мітки й evidence) — точні копії підрядків документа, символ у символ, без виправлень склеєних слів і без зміни регістру. Evidence — одне речення, що містить обидві мітки.
4. Мета: ≥ 170 тверджень, не менше 5 на кожен документ, де текст це дозволяє. Якість важливіша за кількість: не вигадуй, не використовуй власні знання, не додавай твердження «про всяк випадок».
5. Пілотні твердження з розділу 7 схеми (D04, D06, D14, D20, D21) включи в чернетку.
6. Веди data/aliases.csv (alias,canonical,type) для скорочень, колишніх назв і прізвиськ.
7. Запусти: python src/gold_tools.py fill data/gold_draft_raw.jsonl data/gold_draft.jsonl
   і виправляй рядки, поки не зникнуть помилки. Потім: python src/gold_tools.py validate data/gold_draft.jsonl та stats.
8. Створи llm_log/2026-11-07_gold_draft.md: дата, модель, цей промпт, і кількість тверджень.
Схему, інструкцію й src/gold_tools.py не змінюй. Якщо правило схеми заважає, залиш примітку у файлі data/gold_notes.md, а не міняй схему.
