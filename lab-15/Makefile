PY ?= python
.PHONY: setup test inspect demo schemas neo4j load-graph embeddings eval compare pin attack-off attack-on attack-compare hitl-demo hitl-review hitl-metrics
LABEL ?= baseline

setup:            ## venv + залежності
	python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt

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
