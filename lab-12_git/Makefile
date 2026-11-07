PY=python
SEED?=42
.PHONY: all generate load olap verify semantic test t2sql claims dashboard versions

all: generate load olap verify semantic test dashboard

generate:
	$(PY) etl/generate.py --seed $(SEED) --rows 5000

load:
	$(PY) etl/load.py

olap:
	$(PY) etl/run_olap.py

verify:
	$(PY) etl/verify_olap.py

semantic:
	$(PY) semantic/check_consistency.py

test:
	pytest -q

t2sql:
	$(PY) text2sql/evaluate.py --delay 4

claims:
	$(PY) tools/make_claims.py
	$(PY) tools/fill_t2sql_report.py

dashboard:
	$(PY) dashboard/build.py

versions:
	$(PY) tools/versions.py
