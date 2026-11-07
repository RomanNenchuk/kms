# ЛР 12. OLAP-куб на основі таксономії (авіаційні перевезення)

Курс «Сховища знань та управління знаннями», ЛНУ ім. І. Франка. Гілка: `lab12`.
Зіркова схема над синтетичними даними рейсів (5000 рядків, 2025 рік), OLAP-запити у DuckDB, семантичний шар метрик, text-to-SQL (Gemini) із захистами та аналітична панель.

## Середовище
Ubuntu, Python 3.10+ (точні версії пакетів: `docs/environment.txt`, створюється `make versions`), venv без Docker.

## Запуск з нуля
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # потрібен лише для text-to-SQL: GEMINI_API_KEY, GEMINI_MODEL

make generate SEED=42           # data/*.parquet + data/VERSION
make load                       # DuckDB + 21 перевірка якості (data/quality_report.json)
make olap                       # 9 OLAP-запитів, CSV у data/olap_out/
make verify                     # незалежна перевірка 2 результатів у pandas
make semantic                   # узгодженість семантичного шару (4 питання)
make test                       # pytest (AST-перевірка, семантика, оцінювач на mock-відповідях)
make dashboard                  # dashboard/index.html
make t2sql                      # оцінка text-to-SQL на Gemini (потрібен ключ)
make claims                     # claims/claims.csv, docs/claims_summary.md, заповнення docs/t2sql_report.md
```
**Seed:** 42 (параметр `SEED`). Версія даних: `data/VERSION` (dataset_version, seed, rows, версії numpy/pandas).
Ключі API лише в `.env` (у `.gitignore`); у код і звіт не потрапляють. Дані синтетичні, персональних даних немає.

## Структура
| Шлях | Результат | Вміст |
|---|---|---|
| `docs/star_design.md`, `sql/ddl.sql` | 1 | зерно, питання, виміри (5 таблиць, таксономія з IRI), міри, SCD, діаграма |
| `etl/generate.py`, `etl/load.py`, `etl/quality.py`, `data/*.parquet`, `docs/data.md` | 2 | генератор, завантаження, 21 перевірка, версія |
| `sql/olap/*.sql`, `docs/olap_results.md`, `etl/verify_olap.py` | 3 | 9 запитів, інтерпретації, перевірка в pandas |
| `semantic/metrics.yml`, `semantic/metrics.py`, `semantic/check_consistency.py`, `docs/semantic_layer.md` | 4 | 9 метрик, генерація SQL, узгодженість |
| `text2sql/`, `tests/t2sql.jsonl`, `dashboard/`, `docs/t2sql_report.md`, `docs/t2sql_risks.md` | 5 | конвеєр, оцінка, панель, ризики |
| `llm_log/`, `claims/claims.csv`, `docs/claims_summary.md`, `docs/ai_declaration.md` | протокол | журнал взаємодії з LLM, твердження, декларація ШІ |
| `reports/report.md`, `docs/defense_notes.md` | звіт | звіт і нотатки до захисту |

## Тести
`pytest -q`. Тести, що потребують БД, пропускаються, доки не виконано `make load`.
