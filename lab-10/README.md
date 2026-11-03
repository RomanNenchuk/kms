# Domain Knowledge Hub — ЛР 10: векторне сховище та семантичний пошук
Домен: управління авіаційними перевезеннями.

## Запуск з нуля (Ubuntu, Python 3.10+)
```bash
git checkout -b lab10
./setup.sh
source .venv/bin/activate
# відредагуй .env і встав GEMINI_API_KEY з AI Studio
python -m src.check_env
```
Seed скрізь = 42 (`src/config.py`). Перший запуск check_env завантажує моделі (~1–2 ГБ у кеш HuggingFace).

## Структура
| Папка | Призначення |
|---|---|
| kb/ | вхідні .md з ЛР 2 |
| data/ | corpus.jsonl (Результат 1) |
| src/ | chunking.py, index.py, hybrid.py, llm.py, config.py |
| eval/ | gold.jsonl, metrics.py (Результат 5) |
| docs/ | звіти по кожному результату, corpus_card, llm_declaration |
| llm_log/ | журнал викликів LLM (пишеться автоматично) |
| claims/ | claims.csv — таблиця тверджень |

## Результати
1. Корпус і метадані 2. Chunking 3. Індекс і embeddings 4. Гібрид + rerank 5. Золотий набір і метрики

## Порядок запуску (від нуля, seed = 42)
```bash
./setup.sh && source .venv/bin/activate && python -m src.check_env
python scripts/fetch_wiki.py                      # корпус (kb/wiki)
python scripts/build_corpus.py                    # data/corpus.jsonl
python scripts/gen_corpus_card.py                 # docs/corpus_card.md
python -m scripts.gen_chunk_queries               # кандидати запитів -> перевірка вручну
python -m src.compare_chunking                    # Результат 2
python -m src.index                               # Результат 3: HNSW, час
python -m src.compare_embeddings && python -m src.test_update
python -m src.hybrid                              # Результат 4
python -m scripts.gen_gold                        # Результат 5: кандидати -> перевірка -> eval/gold.jsonl
python -m src.kappa prepare && python -m src.kappa label && python -m src.kappa gemini && python -m src.kappa compute
python -m src.evaluate && python -m scripts.finalize_protocol
```
Залежності: `requirements.txt` (Python 3.10+); потрібен `GEMINI_API_KEY` у `.env`. Результати: `docs/*.md`, `eval/*.json`.
