# Журнал LLM: Claude Code — чернетка золотого набору A1 (ЛР 13, Результат 2)

| Поле | Значення |
|---|---|
| Дата | 2026-11-07 |
| Інструмент і модель | Claude Code; модель **Sonnet 5.5** |
| Параметри | temperature/seed не задавались (значення за замовчуванням) |
| Версія підказки | `gold-draft-v1` (текст нижче) |
| Сирий вихід | `data/gold_draft_raw.jsonl` — скопіюй у `llm_log/raw/gold_draft_raw_2026-11-07.jsonl` **[ЗБЕРЕЖИ]** |
| Результат | чернетка → після `fill` `data/gold_draft.jsonl`; на момент передачі на узгодження 153 твердження у 24 документах |

## Підказка `gold-draft-v1`
```
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
```

## Рішення людини
Порівняння виходу моделі з поточним золотим набором (`python src/gold_tools.py diff data/gold_draft_raw.jsonl data/gold.jsonl`):

| Показник | Кількість |
|---|---|
| Твердження в сирому виході моделі | **153** |
| Видалено людиною | **0** |
| Додано людиною | **2** |
| Змінено людиною | **7** |
| Твердження у `data/gold.jsonl` | 155 |

Окремо, при узгодженні з розмітником A2: додано 2 (Aeroflot → Moscow, Avia International → Dublin), відхилено 1 (див. `claims/claims.csv`, `D14-REJ-001`), перетиповано 7 (Lufthansa Group: `Airline` → `Organization`).
