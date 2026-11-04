# REST API (ЛР 11, Результат 3)

Код: `api/main.py` (ендпоінти), `api/security.py` (ключі, ролі, ліміти). Специфікація OpenAPI: `docs/openapi.json` (генерується) і живий Swagger на `http://localhost:8000/docs`.

## Запуск
```bash
docker compose exec app python scripts/gen_api_keys.py --write       # хеші ключів -> .env, відкриті ключі -> .demo_keys
docker compose exec -d app uvicorn api.main:app --host 0.0.0.0 --port 8000     # або без -d, щоб бачити логи
docker compose exec app python scripts/export_openapi.py             # docs/openapi.json
bash scripts/demo_api.sh                                             # демо двох ролей, помилок і ліміту (з хоста)
docker compose exec app pytest tests/test_security.py tests/test_api.py
```
Сервіс не стартує без `API_KEYS` (fail fast): відкритого API без ключа не буде.

## Ендпоінти
| Метод і шлях | Призначення | Автентифікація | Ліміт |
|---|---|---|---|
| `POST /ask` | питання -> відповідь, джерела, цитати, токени, затримки | так | 10 запитів/хв на ключ |
| `GET /sources/{id}` | текст джерела за `id` із відповіді (`graph:<вузол>` — підграф) | так | 60 запитів/хв на ключ |
| `GET /health` | стан сервісу | ні | — |

Тіло `POST /ask` (Pydantic, `extra="forbid"`): `question` (3–1000 символів, без керівних символів), `top_k` (1–10, за замовчуванням 5), `use_graph` (bool).
Ідентифікатори джерел містять `#` (наприклад `en_aircrewc#018`); у URL його кодують як `%23`, інакше клієнт обріже шлях як фрагмент.

## Ролі та права
| Роль | Документи | Підграф (`use_graph`, `graph:*`) |
|---|---|---|
| viewer | public | заборонено (403) |
| analyst | public + internal | дозволено |
| admin | public + internal + restricted | дозволено |

- Рівень доступу **визначається ключем на сервері** і передається в RAG як `max_level`; клієнт не може його вказати (поле в тілі дає 422).
- Фільтр за правами працює до пошуку (pre-filter у FAISS), тож недозволені фрагменти не потрапляють ні в контекст LLM, ні в `sources`.
- Підграф (рейси, ризики) вважаємо операційними даними, тому він недоступний ролі viewer. Пасажири з графа виключені для всіх (персональні дані).
- Рівні internal/restricted для кількох статей (`data/sensitivity_overrides.json`) призначено **умовно, для демо**: усі статті — публічна Вікіпедія.

## Автентифікація
Заголовок `X-API-Key`. У `.env` зберігаються лише SHA-256 хеші (`API_KEYS=<hash>:<role>,...`), порівняння сталого часу (`hmac.compare_digest`). Відкритий ключ видно тільки при генерації.
Невдалі спроби обмежено за IP (20/хв), щоб ускладнити підбір ключа.

## Коди відповідей
| Код | Коли |
|---|---|
| 200 | успіх (включно з відмовою «не знаю»: `abstained: true`) |
| 401 | немає або неправильний `X-API-Key` (заголовок `WWW-Authenticate: ApiKey`) |
| 403 | недостатньо прав: `use_graph`/`graph:*` для viewer, документ вищого рівня |
| 404 | джерела немає |
| 422 | некоректне тіло або параметр шляху (Pydantic) |
| 429 | перевищено ліміт; заголовки `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining` |
| 502 | помилка LLM-провайдера (деталі лише в журналі сервера) |
| 503 | граф недоступний або LLM тимчасово обмежує запити (`Retry-After`) |

Рішення, яке варто пояснити: для недоступного документа повертаємо 403, а не 404. Це розкриває існування `id`, але тільки тим, хто його вже отримав у відповіді; 404 лишається для неіснуючих.

## Приклади (curl)
```bash
source .demo_keys; B=http://localhost:8000

# viewer: публічні документи
curl -s -X POST $B/ask -H "X-API-Key: $VIEWER_KEY" -H 'Content-Type: application/json' \
     -d '{"question":"What is an airline hub?"}'

# admin: той самий запит, але доступні й restricted-документи
curl -s -X POST $B/ask -H "X-API-Key: $ADMIN_KEY" -H 'Content-Type: application/json' \
     -d '{"question":"What is an airline alliance?","top_k":5}'

# analyst: текст + підграф
curl -s -X POST $B/ask -H "X-API-Key: $ANALYST_KEY" -H 'Content-Type: application/json' \
     -d '{"question":"Which flights are affected by Fog at Lviv?","use_graph":true}'

# джерело (# -> %23): viewer отримає 403 для restricted, admin 200
ID='<id із поля sources>'; curl -s -H "X-API-Key: $ADMIN_KEY" "$B/sources/${ID//#/%23}"
curl -s -H "X-API-Key: $ANALYST_KEY" "$B/sources/graph:LWO"
```
Структура відповіді `/ask`: `request_id`, `answer`, `abstained`, `sources[{id, kind, doc_id, title, rerank_score}]`, `citations{cited, invalid, ok}`, `tokens`, `latency_ms`, `model`, `access_level`, `graph_used`.
Реальний вивід сценарію з двома ролями дивись у `bash scripts/demo_api.sh` (додай його до звіту).

## Обмеження
- Ліміти зберігаються в пам'яті процесу: для кількох воркерів чи реплік потрібен спільний сховище (наприклад Redis).
- Одночасні виклики RAG обмежено семафором (`RAG_CONCURRENCY`, 2), бо reranker і LLM-клієнт спільні на процес.
- Немає HTTPS і CORS: лише локальний запуск; у продакшені API ставлять за TLS-проксі.
- Ключі не ротуються автоматично: щоб замінити, згенеруй нові й перезапусти сервер.
