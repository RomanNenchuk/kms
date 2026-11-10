# ЛР 15. LLM-агент з інструментами (MCP) над сховищем знань

Курс «Сховища знань та управління знаннями», ЛНУ ім. І. Франка. Гілка: `lab15`. Предметна область: управління авіаційними перевезеннями.
Це **стартовий скелет**: середовище, дані з ЛР 9–12, робочий MCP-сервер, агент-клієнт і тести. Документи й експерименти результатів 1–5 ще треба зробити.

## Запуск з нуля (Ubuntu, Python 3.10+)
```bash
make setup && source .venv/bin/activate     # venv + залежності
cp .env.example .env                        # впиши GEMINI_API_KEY і GEMINI_MODEL
make test                                   # 31 офлайн-тест, ключ не потрібен
python scripts/check_env.py                 # що працює, а що ні
make schemas                                # docs/tool_schemas.json (для agent_spec.md)
make demo                                   # 5 запитань агента -> logs/trace.jsonl (потрібен ключ)
```
Необов'язково:
```bash
make embeddings                             # dense-пошук (torch CPU + sentence-transformers); без нього vector_search = BM25
echo 'NEO4J_PASSWORD=<пароль>' >> .env && make neo4j && make load-graph   # лише для інструмента run_cypher
make inspect                                # MCP Inspector у браузері
```
**seed = 42.** Ключі лише в `.env` (у `.gitignore`). Дані синтетичні, персональних даних немає.

## Що реалізовано
| Інструмент (MCP) | Джерело | Права / захисти |
|---|---|---|
| `graph_lookup` | граф ЛР 9/11 з CSV (без Neo4j) | Passenger і Pilot недоступні на рівні `public` |
| `run_cypher` | Neo4j (необов'язково) | лише читання: заборонені ключові слова, один оператор, LIMIT, READ-маршрутизація, заборона міток/зв'язків/властивостей за рівнем |
| `vector_search` | корпус і індекс e5 з ЛР 10/11 | pre-filter за `sensitivity`; фрагмент з ознаками ін'єкції відхиляється; текст загорнуто в `<untrusted_document>` |
| `list_metrics`, `query_metric` | DuckDB-куб і семантичний шар з ЛР 12 | вільного SQL немає; лише метрики зі статусом `approved`; read-only з'єднання |

Усі інструменти мають `readOnlyHint`. Права задає `ACCESS_LEVEL` у середовищі сервера, а не аргументи інструментів, тож модель не може підвищити собі права.

Агент (`agent/agent.py`): цикл LLM ↔ інструменти, вузол перевірки цитат (id мають походити з результатів інструментів, одна спроба виправлення, інакше `NO_ANSWER`), ліміти (кроки, виклики, токени, час, зациклення) і трасування в `logs/trace.jsonl`. Серверний журнал викликів: `logs/tool_calls.jsonl`.
Перемикач `DEFENSES=off` вимикає фільтри сервера. Він потрібен для стану «до захисту» в Результаті 4.

## Структура
```
mcp_server/   server.py (інструменти), guards.py (Cypher, права, ін'єкції), graph.py, vector.py, warehouse.py, neo4j_cypher.py, config.py
agent/        agent.py (цикл + verify + trace), llm.py (Gemini, FakeLLM), tools_client.py (MCP stdio), policies.py, prompts/system_v1.md
data/         graph/ (CSV ЛР 9/11) · kb/ + indexes/ (корпус і embeddings ЛР 10/11) · warehouse/hub.duckdb (ЛР 12)
semantic/     metrics.yml (ЛР 12)
tests/        test_guards, test_tools, test_mcp_smoke, test_agent_loop; agent_scenarios.jsonl, attacks.jsonl (порожні)
docs/         шаблони agent_spec, agent_eval, agent_security, hitl, ai_declaration; tool_schemas.json (генерується)
llm_log/, claims/   обов'язкові артефакти протоколу «LLM-експерт»
```
Звідки дані: `lab-11/data/*.csv` → `data/graph/`, `lab-11/data/corpus.jsonl` → `data/kb/`, `lab-10/indexes/e5_hierarchical.{json,npy}` → `data/indexes/`, `lab-12/data/hub.duckdb` і `lab-12/semantic/metrics.yml` → `data/warehouse/` та `semantic/`.

## Підключення до IDE / Claude Code (демо для Результату 2, C1)
Скопіюй `.mcp.json.example` у `.mcp.json`, підстав абсолютні шляхи й підключи в клієнті, який підтримує MCP.

## Дорожня карта
1. **Р1:** `docs/agent_spec.md`. Схеми інструментів уже є в `docs/tool_schemas.json`, ліміти в `agent/policies.py`.
2. **Р2:** демо `make demo` (≥5 трас), перевірка read-only (`tests/test_mcp_smoke.py`). Цитати вже перевіряються.
3. **Р3:** написати `tests/agent_scenarios.jsonl` (≥10: 5 успішних, 3 «не знаю», 2 із конфліктом джерел) і `agent/evaluate.py`.
4. **Р4:** `tests/attacks.jsonl` (≥6 атак ≥4 типів), прогін з `--defenses off` і `on`.
5. **Р5:** `agent/propose_fact.py` (pyshacl уже в залежностях), `docs/hitl.md`.
6. Протокол: кожен запит до LLM журналюється в `llm_log/`, твердження йдуть у `claims/claims.csv`. Без цього максимум 0.25 за результат.

## Відомі обмеження
- Neo4j Community не має ролей, тому окремого read-only користувача створити не можна. Захист тримається на guard-і та READ-транзакції (залишковий ризик для `docs/agent_security.md`).
- Фільтр ін'єкцій евристичний (регулярні вирази), його легко обійти перефразуванням.
- Без `sentence-transformers` пошук лексичний (BM25), `mode` у відповіді показує режим.
