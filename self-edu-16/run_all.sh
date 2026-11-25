#!/usr/bin/env bash
# Повний запуск: основна оцінка, чутливість до «seen», холодний старт, етика, чернетка звіту (~10 с на CPU).
set -euo pipefail
cd "$(dirname "$0")"
python -m src.evaluate
python -m src.evaluate --include-seen --no-plots > /dev/null
python -m src.cold_start
python -m src.ethics
python -m src.make_report
echo; echo "Готово: results/ (таблиці, json, графіки) і report/report_draft.md"
