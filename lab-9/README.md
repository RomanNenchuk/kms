# ЛР 9. Графова база знань у Neo4j — домен «Управління авіаційними перевезеннями»

Пакет містить усе для 5 результатів: дані (CSV), скрипти імпорту/запитів/GDS, text-to-Cypher, шаблони документів і протокол «LLM-експерт».
**Важливо:** Cypher-скрипти я не міг виконати на реальному Neo4j (у середовищі, де готувався пакет, його немає). Те, що можна було перевірити
незалежно, перевірено на pandas/networkx/rdflib (див. `docs/expected_results.txt`). Якщо будь-який Cypher-запит дасть помилку — надішліть текст помилки, виправимо.

## 0. Що з ЛР 8 придатне, а що ні
Придатне: словник `av:` (класи/властивості) → основа схеми; запити Q1–Q6 → зразки для порівняння зі SPARQL; Fuseki-конфіг → для Результату 5.
Недостатнє: у `data.ttl` лише ≈ 25 вузлів і 4 рейси, а ЛР 9 вимагає ≥ 100 вузлів і ≥ 200 зв'язків; файлу `triples_final.csv` немає.
Рішення: `scripts/generate_data.py` (seed = 42) генерує **673 вузли і 2592 зв'язки** (+343 похідні = 2935). Довідкові дані (50 аеропортів, 30 країн) — публічні IATA-коди;
рейси/пасажири/пілоти/ризики/затримки — **синтетичні** (це треба прямо написати у звіті; поле `source` на ребрах це фіксує).
Сценарій узгоджено з ЛР 8: ті ж Sky Ukraine / AeroLink Europe, «Fog at Lviv», «Hydraulic fault».

## 1. Що встановити (Linux/Ubuntu; Protégé не потрібен)
1. Docker + Compose: `sudo apt update && sudo apt install -y docker.io docker-compose-v2 && sudo usermod -aG docker $USER` → вийти й увійти знову. (macOS/Windows: Docker Desktop.)
2. Python 3.10+: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. Neo4j 5.x + плагін GDS — **через `docker-compose.yml` з цього пакета** (окремо нічого ставити не треба).
   Neo4j Aura Free не підходить: у ньому немає GDS (Результат 4).
   Альтернатива без Docker — Neo4j Desktop: створити локальну БД 5.x, встановити плагін Graph Data Science, скопіювати `data/*.csv` у каталог *import* БД.
4. Для Результату 5: Apache Jena Fuseki з ЛР 8 (потрібна Java 17+). Якщо видалили — завантажте binary distribution Fuseki 6.x з jena.apache.org.
5. Для text-to-Cypher: безкоштовний ключ Gemini API (Google AI Studio → «Get API key», без картки). Без ключа — режим `manual`.

## 2. Запуск Neo4j
```bash
cd lab9
export NEO4J_PASSWORD='придумайте_пароль_8+символів'
docker compose up -d
docker logs -f lab9-neo4j        # дочекайтесь "Started."; при першому старті завантажується GDS (потрібен інтернет)
```
Браузер: http://localhost:7474 (bolt://localhost:7687, користувач `neo4j`). Перевірка з Python (**Підготовка**): `python scripts/check_connection.py`.
Скрипти `.cypher` можна вставляти в Neo4j Browser **або** виконувати так:
```bash
docker exec -i lab9-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain < import/01_constraints_indexes.cypher
```
(`cypher-shell` зупиняється на першій помилці — тому порушення обмеження в окремому файлі.)

## 3. Порядок виконання за результатами

### Результат 1 — схема (`docs/graph_schema.drawio|png`, `docs/cq_mapping.md`)
Усе вже підготовлено. Відкрийте `.drawio` у draw.io (diagrams.net) — перегляньте, за потреби змініть; перевірте таблицю CQ та порівняння з ЛР 7 і **перепишіть своїми словами те, що не збігається з вашою онтологією**.

### Результат 2 — імпорт (`import/*.cypher`, `data/*.csv`)
```bash
python scripts/generate_data.py          # необов'язково: CSV вже в data/ (генерація детермінована)
for f in 01_constraints_indexes 02_import_nodes 03_import_rels 04_counts; do
  docker exec -i lab9-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain < import/$f.cypher; done
```
- **C1:** `04_counts.cypher` має дати **673 вузли і 2935 зв'язків** (скріншот).
- **C2:** `SHOW CONSTRAINTS` (10) / `SHOW INDEXES` (скріншоти; 3 власних індекси + 10 від обмежень).
- **C3 ідемпотентність:** виконайте ще раз `02_import_nodes` і `03_import_rels`, потім `04_counts` — числа ті самі.
- **C4:** `import/05_constraint_violation.cypher` окремо → помилка `ConstraintValidationFailed` (скріншот).

### Результат 3 — запити (`queries/01_queries.cypher`, `docs/cypher_results.md`)
Виконайте Q1–Q13 (+Q3b) по одному, вставте результат і напишіть інтерпретацію в `docs/cypher_results.md`.
Еталонні числа для звірки: `docs/expected_results.txt` / `python scripts/verify_expected.py`.
Ручна перевірка (≥ 3 запити) — таблиця наприкінці `cypher_results.md`.

### Результат 4 — GDS і PROFILE (`queries/02_gds.cypher`, `queries/03_profile.cypher`, `docs/gds_report.md`)
Виконуйте `02_gds.cypher` блоками. Якщо `gds.version()` невідома — плагін не підвантажився (`docker logs lab9-neo4j | grep -i gds`).
У `03_profile.cypher` — «до» (індекс видалено) і «після» (створено); у Browser дописуйте `PROFILE` перед запитом і фіксуйте db hits та план.

### Результат 5 — SPARQL vs Cypher, text-to-Cypher
**5.1 SPARQL.** Ті самі дані в RDF: `python scripts/csv_to_ttl.py` (→ `data/data9.ttl`).
```bash
cd ~/tools/apache-jena-fuseki-6.2.0 && ./fuseki-server --mem --update /aviation9      # інший термінал далі
cd lab9/data
curl -X POST -H "Content-Type: text/turtle" --data-binary @vocabulary_lab8.ttl http://localhost:3030/aviation9/data
curl -X POST -H "Content-Type: text/turtle" --data-binary @data9.ttl            http://localhost:3030/aviation9/data
```
Запити C1–C5 — `queries/sparql_for_comparison.rq` (Fuseki UI → aviation9 → query). Заповніть `docs/sparql_vs_cypher.md`.

**5.2 text-to-Cypher.**
```bash
export NEO4J_PASSWORD=...            # той самий пароль
export GEMINI_API_KEY=...            # лише в середовищі, НЕ в коді/звіті
python t2c/t2c.py --provider gemini  # ~14 запитів, пауза 7 с між ними (ліміти безкоштовного рівня)
```
Без ключа: питання з `tests/t2c.jsonl` задайте будь-якому чат-LLM (з `t2c/schema_prompt.txt` як системною підказкою), запишіть відповіді в
`tests/manual_cypher.jsonl` за зразком `tests/manual_cypher.jsonl.example` і запустіть `python t2c/t2c.py --provider manual`.
Вихід: частка коректних, `tests/t2c_results_*.jsonl`, автоматичний журнал `llm_log/t2c_*.jsonl`. Проаналізуйте **3 помилки** (таблиця в `sparql_vs_cypher.md`).
Якщо помилок менше трьох — додайте складніші питання в `tests/t2c.jsonl` (еталон обов'язково перевірте виконанням).
Модель за замовчуванням `gemini-2.5-flash`; якщо ключ її не бачить (404), задайте іншу: `export GEMINI_MODEL=<назва з AI Studio>`.
Безкоштовний рівень Google може використовувати запити для покращення продуктів, тому в LLM іде лише схема й питання, **без даних** (так і задумано).

## 4. Протокол «LLM-експерт» (без нього максимум 0.25 за результат)
- `llm_log/` — журнал: дата, модель, параметри, версія підказки, сирий вихід, **ваше рішення**. Запис 001 про цей чат — шаблон у `llm_log/README.md`; збережіть експорт цього діалогу.
- `claims/claims.csv` — таблиця тверджень; усі стоять у `pending` — **кожне треба перевірити самому** і змінити на `verified`/`rejected` з коментарем (c05, c06, c08 потребують посилань на документацію/довідники).
- У звіті — декларація використання ШІ (інструмент, призначення, приклад запиту, як перевірено), частка підтверджених тверджень, відхилені з поясненням, перелік джерел.
- Репозиторій Hub: гілка `lab09`; у README — версії (Neo4j 5.26, GDS — з `gds.version()`), команди, seed = 42.

## 5. Структура
`data/` CSV + `data9.ttl` · `import/` Cypher імпорту · `queries/` запити, GDS, PROFILE, SPARQL · `docs/` схема, CQ, результати, GDS-звіт, SPARQL vs Cypher, захист ·
`t2c/` + `tests/` text-to-Cypher · `llm_log/`, `claims/` протокол · `scripts/` генератор, конвертер, перевірки.

## 6. Типові проблеми
- `Couldn't load the external resource at file:/.../x.csv` — CSV не в каталозі import (перевірте volume у compose; `docker exec lab9-neo4j ls /var/lib/neo4j/import`).
- `Unknown function gds.version` — плагін GDS не завантажився (інтернет при першому старті; перевірте логи).
- Порожній результат Q12/Q13 — імпорт `03_import_rels` не відпрацював повністю; перевірте `04_counts`.
- Немає Docker — Neo4j Desktop (див. п. 1).
