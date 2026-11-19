#!/usr/bin/env bash
# Одноразове налаштування середовища СР10 (Ubuntu, venv, CPU).
set -euo pipefail
cd "$(dirname "$0")"

if ! python3 -m venv --help >/dev/null 2>&1 || ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  echo ">> Потрібен python3-venv: sudo apt update && sudo apt install -y python3-venv python3-pip"
  exit 1
fi

[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip

# CPU-збірка PyTorch (~200 МБ замість ~2 ГБ із CUDA)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# завантажити моделі в кеш (~/.cache/huggingface); e5 і minilm-multi уже є після ЛР 10, нова лише all-MiniLM-L6-v2 (~90 МБ)
python src/run_experiment.py --download-only

echo
echo "Готово. Далі:"
echo "  source .venv/bin/activate"
echo "  python src/run_experiment.py --with-baseline"
