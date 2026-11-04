# ЛР 11 — RAG + граф чат-бот (Domain Knowledge Hub)

Середовище: Docker Compose (Ubuntu), сервіси `app` (Python 3.12) і `neo4j` (5 Community). seed = 42.

## Запуск з нуля
```bash
cp .env.example .env            # заповни GEMINI_API_KEY, GEMINI_MODEL, JUDGE_MODEL, NEO4J_PASSWORD
sed -i "s/^HOST_UID=.*/HOST_UID=$(id -u)/; s/^HOST_GID=.*/HOST_GID=$(id -g)/" .env
docker compose up -d --build
docker compose exec app python scripts/generate_data.py      # CSV графа ЛР 9
docker compose exec app python scripts/load_graph.py --wipe  # завантаження в Neo4j
docker compose exec app python scripts/check_env.py --models --llm
```
Браузер Neo4j: http://localhost:7474 (логін `neo4j`, пароль з `.env`). API: http://localhost:8000/docs

## Структура
src/ (rag.py, graph_context.py, index.py, config.py, chunking.py) · api/main.py · prompts/ · eval/ · docs/ · llm_log/ · claims/ · data/ · indexes/
