#!/usr/bin/env bash
# Демо Результату 3: дві ролі, права доступу, коди помилок, ліміт.  Потрібні: запущений сервер і .demo_keys
# (python scripts/gen_api_keys.py --write). Запуск з хоста:  bash scripts/demo_api.sh
set -u
cd "$(dirname "$0")/.."
source .demo_keys
B=${BASE:-http://localhost:8000}
j() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }
code() { curl -s -o /dev/null -w "%{http_code}" "$@"; }
hr() { printf '\n== %s\n' "$1"; }

hr "1. /health (без ключа)";                       curl -s $B/health; echo
hr "2. /ask без ключа -> 401";                      code -X POST $B/ask -H 'Content-Type: application/json' -d '{"question":"What is an airline alliance?"}'; echo
hr "3. невалідне тіло -> 422";                      code -X POST $B/ask -H "X-API-Key: $VIEWER_KEY" -H 'Content-Type: application/json' -d '{"question":"hi","max_level":"restricted"}'; echo

Q='{"question":"What is an airline alliance?"}'
hr "4. viewer (public) питає про документ рівня restricted"
curl -s -X POST $B/ask -H "X-API-Key: $VIEWER_KEY" -H 'Content-Type: application/json' -d "$Q" | j "{k: d[k] for k in ('answer','abstained','access_level','sources')}"
hr "5. admin (restricted) — те саме питання"
R=$(curl -s -X POST $B/ask -H "X-API-Key: $ADMIN_KEY" -H 'Content-Type: application/json' -d "$Q")
echo "$R" | j "{k: d[k] for k in ('answer','abstained','access_level','sources')}"
SID=$(echo "$R" | j "next((s['id'] for s in d['sources'] if s['doc_id']=='en_airline_alliance'), '')")   # фрагмент restricted-документа
[ -z "$SID" ] && { echo "admin не отримав en_airline_alliance у джерелах — зміни питання Q"; exit 1; }
ENC=${SID//#/%23}                                   # '#' у URL треба кодувати
hr "6. GET /sources/$SID: viewer -> 403, admin -> 200"
echo "viewer: $(code $B/sources/$ENC -H "X-API-Key: $VIEWER_KEY")   admin: $(code $B/sources/$ENC -H "X-API-Key: $ADMIN_KEY")"
hr "7. use_graph: viewer -> 403, analyst -> 200"
G='{"question":"Which flights are affected by Fog at Lviv?","use_graph":true}'
echo "viewer: $(code -X POST $B/ask -H "X-API-Key: $VIEWER_KEY" -H 'Content-Type: application/json' -d "$G")   analyst: $(code -X POST $B/ask -H "X-API-Key: $ANALYST_KEY" -H 'Content-Type: application/json' -d "$G")"
hr "8. неіснуюче джерело -> 404";                   code $B/sources/nope%23000 -H "X-API-Key: $ADMIN_KEY"; echo
hr "9. ліміт: 65 GET /sources запитів поспіль (ліміт read = 60/хв)"
for i in $(seq 65); do code $B/sources/$ENC -H "X-API-Key: $ADMIN_KEY"; echo; done | sort | uniq -c
