#!/usr/bin/env bash
# Вимірювання на трьох станах сховища + дашборд (~10 с на CPU). Повторний запуск на тих самих даних нових замірів не додає.
set -euo pipefail
cd "$(dirname "$0")"
python -m src.measure
python -m src.dashboard > /dev/null
echo; echo "Готово: results/dashboard.html (відкрий у браузері), results/tables.md, results/fig_*.png, results/history.jsonl"
