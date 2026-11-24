# СР11 — Тестування RAG: сценарії відмов (авіаційні перевезення)

Тестується RAG із **lab-11** (`../lab-11/src/rag.py`: гібридний пошук e5 + BM25 → reranker → Gemini, промпт `rag_v1`, перевірка цитат, рівні доступу).
Тут — 20 тестових запитів, прогін, класифікація відмов, LLM-суддя faithfulness, ручна перевірка, звіт. Середовище: Ubuntu, venv, CPU, без Docker.

## Запуск з нуля
```bash
cd ~/Documents/university/kms/self-edu-11     # поруч із lab-11 і lab-10
bash setup.sh                                  # venv, CPU-torch, залежності, .env, перевірки, завантаження моделей
source .venv/bin/activate
python -m sr11 run --sleep 3                   # 20 запитів через RAG
python -m sr11 judge                           # faithfulness (JUDGE_MODEL ≠ GEMINI_MODEL); free tier ≈ 5 запитів/хв
python -m sr11 classify                        # results/classification.csv — перевір і виправ human_* колонки
python -m sr11 sheet                           # results/human_sheet.csv — заповни ≥ 5 рядків (0/1) НЕ дивлячись на суддю
python -m sr11 kappa && python -m sr11 report  # results/report_tables.md
```
Якщо `run` обірвався (429): `python -m sr11 run --resume`. Без API все можна перевірити так: `python -m sr11 validate`, `python -m sr11 selftest`, `pytest`.

## Набір запитів (`data/queries.jsonl`, збирає `scripts/build_queries.py`)
| Категорія | id | Що перевіряє |
|---|---|---|
| прості (5) | q01–q05 | факт з одного фрагмента; q04 українською до англійського корпусу |
| багатокрокові (3) | q06–q08 | два фрагменти + обчислення; q08 — два документи; q06 українською |
| без відповіді (4) | q09–q12 | галюцинації; q09–q11 — near-miss (тема є в корпусі, відповіді немає) |
| суперечливі (3) | q13–q15 | два джерела з різними значеннями (**синтетичні фікстури**); q14 — корпус проти фікстури |
| шкідливі/атаки (5) | q16–q20 | відповідь із власних знань, непряма ін'єкція, обхід доступу, шкідливий how-to, персональні дані |

Докази (`evidence`) — дослівні речення з корпусу; `python -m sr11 validate` це перевіряє. Фікстури вигадані мною для тесту й завжди позначені `СИНТЕТИЧНІ` в `note`.

## Класи причин відмов
`пошук` — gold-документ не в top-k · `контекст` — документ є, доказового речення в контексті LLM немає · `генерація` — контекст був, відповідь хибна/без цитат/галюцинація/конфлікт не позначено · `політика` — зайва відмова, ін'єкція, витік, права доступу, шкідливий запит.
Вердикт і клас пропонує **евристика** (`sr11/classify.py`); остаточне слово за вами (`human_verdict`, `human_cause`, `human_note` у `classification.csv`; повторний `classify` їх не стирає).

## Що треба зробити вручну (інакше C2–C4 не зараховані)
1. Пройти `classification.csv`, особливо рядки з `needs_manual = так` (q19 «шкідливий how-to» — прочитати відповідь!).
2. Заповнити `human_sheet.csv` (≥ 5 оцінок) → `kappa`.
3. Переписати висновки (≥ 3) і план виправлень власними словами за `report_tables.md` (там лише чернетки з цифрами) → `report/report.md`.
4. Заповнити декларацію ШІ в `report/report.md` (рядки `[ЗАПОВНИ]`).

## Структура
`sr11/` (config, queries, classify, runner, judge, table, review, report, stub, `__main__`) · `data/queries.jsonl` · `results/` (run.jsonl, classification.csv, human_sheet.csv, kappa.json, report_tables.md) · `llm_log/` (rag_calls.jsonl, judge_calls.jsonl) · `report/report.md` · `tests/`
lab-11 не змінюється: журнал RAG і індекси перенаправляються з `sr11/runner.py`.
