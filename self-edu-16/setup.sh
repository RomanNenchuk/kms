#!/usr/bin/env bash
# Одноразове налаштування середовища СР16 (Ubuntu, venv, CPU). Мережа потрібна лише для pip.
set -euo pipefail
cd "$(dirname "$0")"

if ! python3 -m venv --help >/dev/null 2>&1 || ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  echo ">> Потрібен python3-venv: sudo apt update && sudo apt install -y python3-venv python3-pip"
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3, 10), "потрібен Python >= 3.10"'

[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt

echo ">> Перевірка: тести"
python -m pytest -q tests
echo
echo "Готово. Далі:"
echo "  source .venv/bin/activate && bash run_all.sh"
