# Результат 4. Семантичний шар

## Навіщо
Без семантичного шару кожен запит заново визначає «вчасний рейс», «коефіцієнт завантаження» тощо, і різні аналітики отримують різні числа. Тут визначення метрик живуть в одному місці (`semantic/metrics.yml`), а SQL генерується функцією `metric_sql()` (`semantic/metrics.py`). Користувач (або text-to-SQL із результату 5) оперує іменами метрик і вимірів, а не JOIN-ами та формулами.

## Метрики (9, усі поля заповнено)
| Метрика | Визначення | Формула (скорочено) | Одиниця | Статус |
|---|---|---|---|---|
| `flights_count` | кількість рейсів, включно зі скасованими | `COUNT(*)` | рейсів | approved |
| `passengers` | перевезені пасажири | `SUM(passengers)` | пасажирів | approved |
| `total_delay_min` | сумарна затримка | `SUM(delay_minutes)` | хв | approved |
| `avg_delay_min` | середня затримка на рейс (усі рейси) | `AVG(delay_minutes)` | хв | approved |
| `on_time_rate` | частка вчасних (не скасовано, ≤ 14 хв) | `100 * вчасні / COUNT(*)` | % | approved |
| `cancellation_rate` | частка скасованих | `100 * SUM(cancelled) / COUNT(*)` | % | approved |
| `load_factor` | пасажири / місця, лише нескасовані | `100 * SUM(pax) / SUM(seats)` | % | approved |
| `revenue_per_pax` | дохід на пасажира | `SUM(revenue) / SUM(pax)` | USD | approved |
| `fuel_per_pax_km` | пальне на пасажиро-км | `SUM(fuel) / SUM(pax * km)` | кг/(пас·км) | **draft** |

Кожна метрика в YAML має: `name`, `definition`, `formula`, `unit`, `owner`, `sources`, `constraints`, `status`, `reviewed_at`. Неадитивні метрики (відношення, середні) визначено як відношення сум, а не середнє середніх, це зазначено в `constraints`. Метрику `fuel_per_pax_km` не звірено з незалежним обчисленням, тому вона має статус `draft`.

Розділ `dimensions` описує 15 вимірів (сезон, місяць, авіакомпанія, тип літака, клас/підклас причини з таксономії, аеропорти вильоту/призначення тощо) із потрібними JOIN-ами.

## Генерація SQL
```python
from metrics import metric_sql
metric_sql(["on_time_rate", "avg_delay_min"], group_by=["season"],
           filters=[("airline_type", "=", "low-cost")])
```
дає
```sql
SELECT d.season AS season, 100.0 * SUM(CASE WHEN f.cancelled = 0 AND f.delay_minutes <= 14 THEN 1 ELSE 0 END) / COUNT(*) AS on_time_rate, AVG(f.delay_minutes) AS avg_delay_min
FROM fact_flight f
JOIN dim_date d ON f.date_key = d.date_key
JOIN dim_airline al ON f.airline_key = al.airline_key
WHERE al.airline_type = 'low-cost'
GROUP BY 1
ORDER BY 1
```
CLI: `python semantic/metrics.py on_time_rate --by season --by airline_type`.

Безпека: імена метрик, вимірів і оператори беруться лише з реєстру (whitelist), значення фільтрів екрануються; метрики зі статусом `deprecated` відхиляються.

## Перевірка узгодженості
`python semantic/check_consistency.py` (і `pytest tests/test_semantic.py`) порівнює те саме питання трьома шляхами: SQL із семантичного шару, вручну написаний OLAP-запит із результату 3 і pandas з Parquet.

| Питання | Шляхи | Результат |
|---|---|---|
| Вчасність, середня затримка, кількість рейсів за типом авіакомпанії | семантика = `01_rollup.sql` = pandas | PASS |
| Сумарна затримка за класом причини (таксономія) | семантика = `09_drilldown_taxonomy.sql` = pandas | PASS |
| Пасажири за місяцями | семантика = `06_window_cumulative.sql` = pandas | PASS |
| Load factor і дохід на пасажира за типом літака | семантика = pandas | PASS |

## Метадані та управління
У `metrics.yml` кожна метрика має власника (`owner`), статус (`draft` / `approved`) і дату перегляду (`reviewed_at`); загальна версія та дата перегляду — у розділі `meta`. Зміна визначення метрики = зміна одного рядка YAML з оновленням `reviewed_at`; тест узгодженості одразу покаже, чи ще збігаються шляхи обчислення.

## Обмеження
- Генератор будує лише плоскі агрегації (метрики × виміри × прості фільтри); ROLLUP/CUBE/віконні запити пишуться вручну.
- Усі метрики прив'язані до одного факту `fact_flight`.
- Метрики напівадитивної міри (`airframe_hours`) поки що немає.
