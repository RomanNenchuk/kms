#!/usr/bin/env bash
# Створює .venv і ставить залежності (Ubuntu, Python 3.10+).
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
echo "Готово. Далі: bash run_all.sh"
command -v twopi >/dev/null || echo "Порада: sudo apt install graphviz (потрібен лише для PNG-діаграми)"
