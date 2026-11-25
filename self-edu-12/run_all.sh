#!/usr/bin/env bash
# Будує БД, виконує 5 запитів, показує дефекти чернетки, малює діаграму, запускає тести.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
echo "== 1. DDL + завантаження (v1) і чернетка v0"; $PY src/build_db.py
echo "== 2. П'ять запитів до v1";                    $PY src/run_queries.py
echo "== 3. Три недоліки чернетки v0 (числа)";      $PY src/flaws.py
echo "== 4. Діаграма";                               $PY src/diagram.py
echo "== 5. Тести";                                  .venv/bin/python -m pytest -q
echo; echo "Результати: results/ (q*.csv, flaws.json, star_diagram.png)"
