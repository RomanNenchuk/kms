#!/usr/bin/env bash
# Одноразове налаштування середовища СР11 (Ubuntu, venv, CPU). Docker не потрібен.
set -euo pipefail
cd "$(dirname "$0")"

# 1) python3-venv
if ! python3 -m venv --help >/dev/null 2>&1 || ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  echo ">> Потрібен python3-venv:  sudo apt update && sudo apt install -y python3-venv python3-pip"
  exit 1
fi

# 2) сусідні каталоги: RAG береться з lab-11, індекси — з lab-11/indexes або lab-10/indexes
if [ ! -f ../lab-11/src/rag.py ]; then
  echo ">> Не знайдено ../lab-11/src/rag.py. Поклади self-edu-11 поруч із lab-11 (репозиторій kms) або задай LAB11_DIR=/шлях/до/lab-11"
  exit 1
fi
if [ -f ../lab-11/indexes/e5_hierarchical.faiss ]; then
  echo ">> Індекси: ../lab-11/indexes"
elif [ -f ../lab-10/indexes/e5_hierarchical.faiss ]; then
  [ -e indexes ] || ln -s ../lab-10/indexes indexes
  echo ">> Індекси: ../lab-10/indexes (корпус ідентичний lab-11; символічне посилання indexes/)"
else
  echo ">> Немає індексів e5_hierarchical.* ні в lab-11, ні в lab-10. Збудуй: cd ../lab-10 && python -m src.index (див. README lab-10)"
  exit 1
fi

# 3) venv + залежності (CPU-збірка PyTorch ~200 МБ замість ~2 ГБ із CUDA)
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 4) .env: беремо ключ і моделі з ../lab-11/.env, якщо він є
if [ ! -f .env ]; then
  if [ -f ../lab-11/.env ]; then
    grep -E '^(GEMINI_API_KEY|GEMINI_MODEL|JUDGE_MODEL)=' ../lab-11/.env > .env || true
    printf 'GEN_TEMPERATURE=0\nSEED=42\n' >> .env
    echo ">> .env створено з ../lab-11/.env (перевір значення)"
  else
    cp .env.example .env
    echo ">> Створено .env — ЗАПОВНИ GEMINI_API_KEY (https://aistudio.google.com/apikey)"
  fi
fi

# 5) перевірки без витрат API + завантаження моделей у кеш HuggingFace (кілька сотень МБ; якщо вже є після ЛР 10/11 — візьме з кешу)
python -m sr11 validate
python -m sr11 selftest | head -3
python -m sr11 check --models || echo ">> check не пройшов: найімовірніше, не заповнено .env (GEMINI_API_KEY/GEMINI_MODEL/JUDGE_MODEL)"

echo
echo "Готово. Далі:"
echo "  source .venv/bin/activate"
echo "  python -m sr11 run --sleep 3          # 20 запитів через RAG (≈ 2–3 хв)"
echo "  python -m sr11 judge                  # faithfulness від судді (безкоштовний тариф: ~5 запитів/хв)"
echo "  python -m sr11 classify && python -m sr11 sheet"
echo "  # заповни results/human_sheet.csv (≥ 5 рядків), потім:"
echo "  python -m sr11 kappa && python -m sr11 report"
