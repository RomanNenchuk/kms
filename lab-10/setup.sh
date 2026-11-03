#!/usr/bin/env bash
set -e
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
echo "Готово. Далі: source .venv/bin/activate && python -m src.check_env"
