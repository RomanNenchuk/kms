PY=.venv/bin/python
.PHONY: all build queries flaws diagram test clean
all: build queries flaws diagram test
build:   ; $(PY) src/build_db.py
queries: ; $(PY) src/run_queries.py
flaws:   ; $(PY) src/flaws.py
diagram: ; $(PY) src/diagram.py
test:    ; $(PY) -m pytest -q
clean:   ; rm -f db/sr12.duckdb
