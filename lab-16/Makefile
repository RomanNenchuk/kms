PY ?= python
.PHONY: whitepaper smoke fresh-check explain-demo explain-eval explain-llm cold-start reco-eval gen-data filters-demo reco-demo load-reco check-cypher api ui up down setup test inspect demo schemas neo4j load-graph embeddings eval compare pin attack-off attack-on attack-compare hitl-demo hitl-review hitl-metrics
LABEL ?= baseline

setup:            ## venv + залежності (Hub + ЛР 16)
	python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt -r requirements-reco.txt

api:              ## FastAPI локально (venv)
	$(PY) -m uvicorn reco.api:app --reload --port 8000

ui:               ## Streamlit локально (venv)
	streamlit run ui/app.py

up:               ## весь Hub у Docker Compose
	docker compose up --build

down:
	docker compose down

embeddings:       ## dense-пошук (torch CPU + sentence-transformers)
	pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements-embeddings.txt

test:             ## офлайн-тести (без ключа і мережі)
	EMBED_BACKEND=bm25 $(PY) -m pytest -q

inspect:          ## MCP Inspector у браузері
	mcp dev mcp_server/server.py

schemas:          ## JSON-схеми інструментів -> docs/tool_schemas.json (для agent_spec.md)
	$(PY) scripts/export_tool_schemas.py

demo:             ## 5 запитань агента -> logs/trace.jsonl (потрібен ключ Gemini)
	$(PY) -m agent.agent --demo

neo4j:
	docker compose up -d neo4j

load-graph:       ## завантажити граф у Neo4j
	$(PY) scripts/load_graph.py --wipe

eval:             ## сценарії -> tests/agent_results_$(LABEL).jsonl (make eval LABEL=fixed)
	$(PY) -m agent.evaluate --label $(LABEL) --md

compare:          ## «до / після»: make compare A=baseline B=fixed
	$(PY) -m agent.evaluate --compare $(A) $(B)

pin:              ## відбитки інструментів -> docs/tool_pins.json (після зміни інструментів)
	$(PY) scripts/pin_tools.py

attack-off:       ## red teaming без захистів (потрібен ключ Gemini; a05 потребує Neo4j)
	$(PY) -m agent.redteam --mode off --md

attack-on:        ## red teaming з усіма захистами
	$(PY) -m agent.redteam --mode on --md

attack-compare:   ## таблиця «до / після»
	$(PY) -m agent.redteam --compare

hitl-demo:        ## Р5: 3 сценарії + негативні випадки (пропозиції; рішення людини — окремо)
	$(PY) scripts/demo_hitl.py --reset

hitl-review:      ## Р5: ви схвалюєте/відхиляєте: make hitl-review REVIEWER=roman
	$(PY) -m agent.propose_fact interactive --reviewer $(REVIEWER)

hitl-metrics:     ## Р5: метрики з журналу аудиту
	$(PY) -m agent.propose_fact metrics && $(PY) -m agent.propose_fact verify-audit

gen-data:         ## синтетичні взаємодії (seed=42) -> data/interactions/
	$(PY) scripts/gen_interactions.py

filters-demo:     ## Р1 C2: демо фільтрів -> reports/filters_demo.txt
	$(PY) scripts/demo_filters.py | tee reports/filters_demo.txt

reco-demo:        ## Р1: топ-5 для користувача: make reco-demo U=U001 M=hybrid
	$(PY) -c "import json,sys; from reco.recommender import Recommender as R; r=R(); print(json.dumps(r.recommend('$(or $(U),U001)',5,'$(or $(M),hybrid)',as_of=r.ds.end[:10]),ensure_ascii=False,indent=1))"

load-reco:        ## вузли User/Doc/Topic... у Neo4j (після make load-graph)
	$(PY) scripts/load_reco_graph.py

check-cypher:     ## паритет Cypher == Python (потрібен Neo4j)
	$(PY) scripts/check_cypher.py

reco-eval:        ## Р2: офлайн-оцінка -> reports/eval_results.json, eval_table.md, fig_*.png (~10 с)
	$(PY) -m reco.eval

explain-demo:     ## Р3: 5 прикладів пояснень зі шляху -> docs/explain_examples.md
	$(PY) -m reco.explain --examples

explain-eval:     ## Р3: автоперевірка шаблонних пояснень + мутаційні тести -> reports/explain_eval.json
	$(PY) -m reco.explain --eval

explain-llm:      ## Р3: Gemini перефразовує пояснення + автоперевірка (потрібен ключ) -> docs/explain_examples_llm.md, reports/explain_llm.json, llm_log/explain_calls.jsonl
	$(PY) -m reco.explain --llm --n 60

cold-start:       ## Р3: холодний старт -> reports/cold_start_*.{json,md,png}
	$(PY) -m reco.cold_start

smoke:            ## Р4: димовий тест запущеного Hub (потрібен make up або make api)
	$(PY) scripts/smoke_check.py $(ARGS)

fresh-check:      ## Р4 C4: запуск «з нуля» у чистій теці + лог -> docs/fresh_start_log.txt (потрібен Docker)
	bash scripts/fresh_start_check.sh | tee docs/fresh_start_log.txt

whitepaper:       ## Р5: рисунки + docs/whitepaper.pdf (потрібні pandoc, xelatex, шрифти DejaVu)
	$(PY) scripts/build_whitepaper.py
