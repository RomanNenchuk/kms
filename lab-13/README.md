# Domain Knowledge Hub — ЛР 13: Видобування знань із текстів

Предметна область: **управління авіаційними перевезеннями**. Гілка: `lab13`.

## Запуск з нуля (Ubuntu, Python 3.10+)
```bash
sudo apt install -y python3-venv python3-pip
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm      # spaCy 3.8, модель 3.8.0
cp .env.example .env                          # вписати GEMINI_API_KEY (AI Studio)
python src/check_env.py                       # перевірка spaCy і корпусу
python src/check_env.py --llm                 # + тестовий виклик Gemini
```
Seed: 42 (`SEED` у `.env`). Версії залежностей зафіксовані в `requirements.txt` (список верхнього рівня — `requirements.in`).

## Структура
| Шлях | Призначення |
|---|---|
| `data/raw/` | 22 документи (D01–D22), `data/sources.csv` — реєстр джерел |
| `data/gold.jsonl` | золотий набір (Результат 2) |
| `docs/` | `extraction_schema.md`, `gold_card.md`, `extraction_eval.md`, `patterns.md` |
| `src/` | `extract_rules.py`, `extract_llm.py`, спільний `config.py` |
| `llm_log/` | журнал взаємодії з LLM (обов'язковий артефакт) |
| `claims/claims.csv` | таблиця тверджень (обов'язковий артефакт) |

## Безпека
Ключ API лише в `.env` (у `.gitignore`), не в коді й не у звіті.

## Результат 3. Видобування тверджень (два методи)

Обидва методи читають `data/raw/*.txt`, пишуть JSONL у `results/` з provenance (документ, офсети, модель, версія промпта/правил, run_id).
Налаштування — **лише на dev**. `test` відкривається тільки з `--split test --final` (Результат 4), кожен доступ пишеться в `results/test_access.log`.

```bash
source .venv/bin/activate
pip install -r requirements.txt && python -m spacy download en_core_web_sm   # один раз
cp .env.example .env     # вписати GEMINI_API_KEY (+ за бажанням GEMINI_PRICE_IN/OUT, $ за 1M токенів)

# Метод А: правила + spaCy (без API)
python src/extract_rules.py --split dev                # -> results/rules_dev.jsonl
# Метод Б: Gemini зі схемою, закритим словником, evidence, повторами й валідацією
python src/extract_llm.py --split dev                  # -> results/llm_dev.jsonl, llm_dev_rejected.jsonl, llm_dev_summary.json
                                                       #    + протокол викликів llm_log/gemini_calls.jsonl

# Оцінка на dev (для налаштування)
python src/gold_tools.py score results/rules_dev.jsonl data/gold.jsonl dev --errors
python src/gold_tools.py score results/llm_dev.jsonl   data/gold.jsonl dev --errors
```
Метод Б: структурований вивід (JSON-схема з enum типів і відношень), evidence — дослівна цитата (перевіряється в тексті, інакше твердження йде в `*_rejected.jsonl`), до 3 повторів (помилки API — з паузою, помилки схеми — з поверненням помилки моделі), перевірка сигнатур.