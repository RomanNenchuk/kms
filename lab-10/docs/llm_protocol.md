# Протокол «LLM-експерт»: підсумок

## Журнал взаємодії

Усі виклики Gemini записано в `llm_log/*.jsonl` (дата, модель, параметри, версія підказки, сирий вихід, рішення людини). Рішення людини проставлено на рівні партії кандидатів (деталі правок — у полі `review_note` файлів `eval/*.jsonl`).

| модель | версія підказки | викликів |
|---|---|---|
| gemini-3.5-flash-lite | chunkq-v1 | 10 |
| gemini-3.5-flash-lite | gold-gen-v1 | 87 |
| gemini-3.5-flash-lite | kappa-v1 | 48 |
| gemini-3.5-flash-lite | q-gen-v2 | 16 |
| gemini-3.5-flash-lite | translate-v1 | 1 |

Рішення проставлено у 0 записах журналу.

## Таблиця тверджень

`claims/claims.csv`: 69 тверджень; verified — 65 (94%), rejected — 4, pending — 0. Рівні верифікації: V3 — перевірено людиною за текстом корпусу, V4 — підтверджено метриками.

### Відхилені твердження

- c044: Кандидат kw05 (keyword): «air passengers rights rerouting or refunding» — запит дублює заголовок розділу, а «доказ» — лише вступ до списку без самої відповіді
- c045: Кандидат ms04 (multistep): «Which specific German airport hosts a marginal majority of Lufthansa's long-haul flights, and what was the domestic low-cost carrier seat-capacity percentage in Germany in 2017?» — питання склеює два не пов'язані факти; у реченні-доказі немає слів про seat capacity — неоднозначно
- c046: Кандидат na06 (unanswerable): «What was the precise base salary negotiated for senior flight dispatchers in the 2024 collective bargaining agreement at United Airlines?» — статті про диспетчерів могли частково містити відомості про зарплати — відповідь у корпусі не виключена
- c047: Кандидат na11 (unanswerable): «How many maintenance hours are required by Qantas engineers to complete a heavy C-check on an Airbus A380?» — стаття про техобслуговування могла містити типову тривалість перевірок — відповідь у корпусі не виключена

### Перелік джерел

Корпус: англомовна Вікіпедія (CC BY-SA 4.0):

- https://en.wikipedia.org/wiki/Air_Passengers_Rights_Regulation
- https://en.wikipedia.org/wiki/Air_cargo
- https://en.wikipedia.org/wiki/Aircraft_ground_handling
- https://en.wikipedia.org/wiki/Aircraft_lease
- https://en.wikipedia.org/wiki/Aircraft_maintenance
- https://en.wikipedia.org/wiki/Aircrew
- https://en.wikipedia.org/wiki/Airline
- https://en.wikipedia.org/wiki/Airline_hub
- https://en.wikipedia.org/wiki/Airliner
- https://en.wikipedia.org/wiki/Airport_security
- https://en.wikipedia.org/wiki/Computer_reservation_system
- https://en.wikipedia.org/wiki/Convention_on_International_Civil_Aviation
- https://en.wikipedia.org/wiki/Crew_resource_management
- https://en.wikipedia.org/wiki/Eurocontrol
- https://en.wikipedia.org/wiki/Flight_cancellation_and_delay
- https://en.wikipedia.org/wiki/Global_distribution_system
- https://en.wikipedia.org/wiki/IATA_airport_code
- https://en.wikipedia.org/wiki/ICAO_airport_code
- https://en.wikipedia.org/wiki/International_Air_Transport_Association
- https://en.wikipedia.org/wiki/International_Civil_Aviation_Organization
- https://en.wikipedia.org/wiki/Low-cost_carrier
- https://en.wikipedia.org/wiki/Overselling
- https://en.wikipedia.org/wiki/Revenue_management
- https://en.wikipedia.org/wiki/Runway

Другий розмітник у κ — Gemini; людина розмічала наосліп.
