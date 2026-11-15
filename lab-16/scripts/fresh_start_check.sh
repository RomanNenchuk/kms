#!/usr/bin/env bash
# Запуск «з нуля» (Результат 4, C4): чиста копія проєкту без .venv/.env/кешів -> docker compose -> smoke-тест -> зупинка.
# Використання:  bash scripts/fresh_start_check.sh | tee docs/fresh_start_log.txt
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'cd "$TMP" 2>/dev/null && docker compose -p lab16fresh down -v >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT
echo "== $(date -Is) | docker $(docker --version)"; echo "== копіюю проєкт у чисту теку $TMP"
tar -C "$SRC" --exclude=.venv --exclude=.env --exclude=.git --exclude='__pycache__' --exclude=.pytest_cache --exclude=logs -cf - . | tar -C "$TMP" -xf -
cd "$TMP"; printf 'NEO4J_PASSWORD=fresh-check-pass\n' > .env
echo "== docker compose up --build -d (одна команда запуску)"; docker compose -p lab16fresh up --build -d
echo "== чекаю на готовність API (до 3 хв)"
for i in $(seq 1 36); do curl -fsS http://localhost:8000/health >/dev/null 2>&1 && break; sleep 5; done
curl -fsS http://localhost:8000/health; echo; echo "== стан сервісів"; docker compose -p lab16fresh ps
echo "== чекаю на UI (Streamlit, до 1 хв)"
for i in $(seq 1 12); do curl -fsS -o /dev/null http://localhost:8501/_stcore/health 2>/dev/null && break; sleep 5; done
echo "== UI (Streamlit) відповідає:"; curl -fsS -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8501/_stcore/health
echo "== smoke-тест"; python3 "$SRC/scripts/smoke_check.py" --base http://localhost:8000
echo "== ГОТОВО: запуск з нуля підтверджено"
