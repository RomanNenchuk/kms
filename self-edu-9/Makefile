PY = .venv/bin/python

.PHONY: venv up down data check load bench all clean

venv:
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

up:
	docker compose up -d
	docker compose ps

down:
	docker compose down

data:
	$(PY) src/gen_data.py

check:        ## офлайн-перевірка SPARQL (потрібен rdflib)
	.venv/bin/pip install -q rdflib
	$(PY) src/check_sparql_local.py

load:
	$(PY) src/load.py

bench:
	$(PY) src/bench.py

all: data load bench

clean:        ## зупинити і ВИДАЛИТИ томи з даними
	docker compose down -v
