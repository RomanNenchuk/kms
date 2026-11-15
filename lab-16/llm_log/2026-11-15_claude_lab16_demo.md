# LLM-журнал: демонстратор (Результат 4)
Модель: Claude Sonnet 5.5. Дата: 2026-11-15.

## Запит
Зробити docker-compose для запуску Hub однією командою, API, UI, README, сценарій демо на 7 хв з питанням «не знаю» та атакою.

## Що згенерувала LLM
reco/qa.py (питання до бази без LLM: покриття термінів + заземлення на назви документів + guards), розширений reco/api.py, ui/app.py, Dockerfile, docker-compose.yml, .dockerignore, scripts/smoke_check.py, scripts/fresh_start_check.sh, README.md, docs/demo_script.md, tests/test_api_demo.py.

## Перевірка
Тести API (6) і живий smoke-тест на uvicorn пройшли в пісочниці без Docker. Запуск Docker «з нуля» не перевірено LLM — це робить користувач (make fresh-check).

## Виявлені проблеми в процесі
Пороги «не знаю» (спершу 0.6) пропускали позасферні питання, бо BM25 дає ненульові збіги; додано заземлення на назви документів і поріг 0.5.

## Рішення людини
(заповнити: що прийнято, що змінено, що відхилено)
