# Журнал прогонів Gemini в агенті (Результат 3)

Повні сирі виходи й трасування: `logs/trace_eval_baseline.jsonl`, `logs/trace_eval_fixed.jsonl`, `tests/agent_results_*.jsonl` (скопіюй їх у `llm_log/` перед здачею).

- Модель: ЗАПОВНІТЬ (значення GEMINI_MODEL з .env), Google AI Studio, безкоштовний тариф
- Параметри: temperature 0.0, seed 42 (задано в `agent/llm.py`)
- Версії підказки: `system_v1` (baseline), `system_v2` (fixed); у кожному записі траси є поле `prompt_version`
- Прогони: 12 сценаріїв `tests/agent_scenarios.jsonl`; baseline: 9/12 успішних, fixed: 12/12
- Рішення людини: ЗАПОВНІТЬ САМІ (наприклад: «відповіді s01, s02, s07 прочитано вручну; спотворення визначення і «десятки рейсів» відхилено як хибні — claims C017, C023, C024»).
