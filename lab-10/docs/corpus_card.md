# Картка корпусу

## Загальне
- Домен: управління авіаційними перевезеннями (проєкт Domain Knowledge Hub)
- Мова: en (одномовний корпус; моделі embeddings багатомовні)
- Документів: 36; фрагментів: 795; довжина фрагмента, симв.: min 86, середня 766, max 1408
- Дата збору: 2026-10-31
- Формат: `data/corpus.jsonl` (chunk_id, doc_id, title, section, type, date, sensitivity, source_url, lang, license, text)

## Джерела та ліцензії
Усі документи — статті англійської Вікіпедії (ліцензія CC BY-SA 4.0), завантажені через MediaWiki API.

| doc_id | назва | тип | ліцензія | фрагментів | джерело |
|---|---|---|---|---|---|
| en_air_cargo | Air cargo | overview | CC BY-SA 4.0 | 10 | https://en.wikipedia.org/wiki/Air_cargo |
| en_air_operator_s_certificate | Air operator's certificate | regulation | CC BY-SA 4.0 | 7 | https://en.wikipedia.org/wiki/Air_operator%27s_certificate |
| en_air_passengers_rights_regulation | Air Passengers Rights Regulation | regulation | CC BY-SA 4.0 | 33 | https://en.wikipedia.org/wiki/Air_Passengers_Rights_Regulation |
| en_air_traffic_control | Air traffic control | operations | CC BY-SA 4.0 | 35 | https://en.wikipedia.org/wiki/Air_traffic_control |
| en_air_traffic_flow_management | Air traffic flow management | operations | CC BY-SA 4.0 | 4 | https://en.wikipedia.org/wiki/Air_traffic_flow_management |
| en_air_traffic_management | Air traffic management | operations | CC BY-SA 4.0 | 3 | https://en.wikipedia.org/wiki/Air_traffic_management |
| en_aircraft_ground_handling | Aircraft ground handling | operations | CC BY-SA 4.0 | 13 | https://en.wikipedia.org/wiki/Aircraft_ground_handling |
| en_aircraft_lease | Aircraft lease | operations | CC BY-SA 4.0 | 13 | https://en.wikipedia.org/wiki/Aircraft_lease |
| en_aircraft_maintenance | Aircraft maintenance | operations | CC BY-SA 4.0 | 15 | https://en.wikipedia.org/wiki/Aircraft_maintenance |
| en_aircrew | Aircrew | operations | CC BY-SA 4.0 | 11 | https://en.wikipedia.org/wiki/Aircrew |
| en_airline | Airline | overview | CC BY-SA 4.0 | 63 | https://en.wikipedia.org/wiki/Airline |
| en_airline_alliance | Airline alliance | overview | CC BY-SA 4.0 | 12 | https://en.wikipedia.org/wiki/Airline_alliance |
| en_airline_hub | Airline hub | operations | CC BY-SA 4.0 | 17 | https://en.wikipedia.org/wiki/Airline_hub |
| en_airliner | Airliner | reference | CC BY-SA 4.0 | 49 | https://en.wikipedia.org/wiki/Airliner |
| en_airport | Airport | overview | CC BY-SA 4.0 | 56 | https://en.wikipedia.org/wiki/Airport |
| en_airport_security | Airport security | regulation | CC BY-SA 4.0 | 41 | https://en.wikipedia.org/wiki/Airport_security |
| en_airport_slot | Airport slot | operations | CC BY-SA 4.0 | 4 | https://en.wikipedia.org/wiki/Airport_slot |
| en_aviation_safety | Aviation safety | regulation | CC BY-SA 4.0 | 65 | https://en.wikipedia.org/wiki/Aviation_safety |
| en_codeshare_agreement | Codeshare agreement | operations | CC BY-SA 4.0 | 9 | https://en.wikipedia.org/wiki/Codeshare_agreement |
| en_computer_reservation_system | Computer reservation system | operations | CC BY-SA 4.0 | 10 | https://en.wikipedia.org/wiki/Computer_reservation_system |
| en_convention_on_international_civil_aviation | Convention on International Civil Aviation | regulation | CC BY-SA 4.0 | 11 | https://en.wikipedia.org/wiki/Convention_on_International_Civil_Aviation |
| en_crew_resource_management | Crew resource management | operations | CC BY-SA 4.0 | 24 | https://en.wikipedia.org/wiki/Crew_resource_management |
| en_eurocontrol | Eurocontrol | regulation | CC BY-SA 4.0 | 12 | https://en.wikipedia.org/wiki/Eurocontrol |
| en_flight_cancellation_and_delay | Flight cancellation and delay | operations | CC BY-SA 4.0 | 14 | https://en.wikipedia.org/wiki/Flight_cancellation_and_delay |
| en_flight_dispatcher | Flight dispatcher | operations | CC BY-SA 4.0 | 9 | https://en.wikipedia.org/wiki/Flight_dispatcher |
| en_global_distribution_system | Global distribution system | operations | CC BY-SA 4.0 | 10 | https://en.wikipedia.org/wiki/Global_distribution_system |
| en_iata_airport_code | IATA airport code | reference | CC BY-SA 4.0 | 46 | https://en.wikipedia.org/wiki/IATA_airport_code |
| en_icao_airport_code | ICAO airport code | reference | CC BY-SA 4.0 | 10 | https://en.wikipedia.org/wiki/ICAO_airport_code |
| en_international_air_transport_association | International Air Transport Association | regulation | CC BY-SA 4.0 | 17 | https://en.wikipedia.org/wiki/International_Air_Transport_Association |
| en_international_civil_aviation_organization | International Civil Aviation Organization | regulation | CC BY-SA 4.0 | 34 | https://en.wikipedia.org/wiki/International_Civil_Aviation_Organization |
| en_low_cost_carrier | Low-cost carrier | overview | CC BY-SA 4.0 | 32 | https://en.wikipedia.org/wiki/Low-cost_carrier |
| en_montreal_convention | Montreal Convention | regulation | CC BY-SA 4.0 | 8 | https://en.wikipedia.org/wiki/Montreal_Convention |
| en_overselling | Overselling | operations | CC BY-SA 4.0 | 18 | https://en.wikipedia.org/wiki/Overselling |
| en_revenue_management | Revenue management | operations | CC BY-SA 4.0 | 33 | https://en.wikipedia.org/wiki/Revenue_management |
| en_runway | Runway | reference | CC BY-SA 4.0 | 38 | https://en.wikipedia.org/wiki/Runway |
| en_warsaw_convention | Warsaw Convention | regulation | CC BY-SA 4.0 | 9 | https://en.wikipedia.org/wiki/Warsaw_Convention |

## Правила очищення від шуму
1. Беремо лише текст статті (plain text через `explaintext`): таблиці, зображення, інфобокси та розмітка відсутні.
2. Видаляємо розділи без змістовного тексту: See also, References, External links, Further reading, Notes, Bibliography, Sources, Footnotes, Citations.
3. Заголовки `== X ==` перетворено на markdown `## X`; зайві порожні рядки стиснуто.
4. Статті коротші за 2000 символів відкинуто.
5. Розбиття: за заголовками; розділи довші за 1200 символів діляться по абзацах/реченнях; фрагменти коротші за 250 символів склеюються із сусіднім у межах розділу; фрагменти коротші за 80 символів відкидаються.
6. Вручну прибрано статті не за темою (напр., загальна «Meteorology»).

## Розподіл за sensitivity
- public: 795

Правило: `public` — за замовчуванням для відкритих джерел; `internal` — власні матеріали; `restricted` — фрагмент, де знайдено email, телефон або позначку «confidential / для службового користування». Автоматичну мітку можна змінити вручну (`data/sensitivity_overrides.json`) із поясненням:

| chunk_id | нова мітка | причина |
|---|---|---|
| en_aviation_safety#027 | public | хибне спрацювання: номер рейсу й рік (Flight 1600 (2011)), не телефон |
| en_aviation_safety#028 | public | хибне спрацювання: номер рейсу й рік (Flight 7425 (1985)), не телефон |
| en_aviation_safety#057 | public | хибне спрацювання: дата архівування Wayback Machine (2008-09-21), не телефон |

## Відомі прогалини
- Лише вторинне енциклопедичне джерело; немає первинних нормативних текстів (повні Annex ICAO, регламенти ЄС, Повітряний кодекс України).
- Немає операційних даних авіакомпаній/аеропортів (розклади, інциденти, внутрішні регламенти).
- Лише англійська мова; українські запити перевірятимемо окремо як cross-lingual.
- Зрізи статей на дату збору; Вікіпедія може містити неточності й не завжди актуальна.
- Таблиці й зображення не збережено, тому табличні факти недоступні для пошуку.
- Нерівномірність: деякі теми (Airline, Airport) охоплені значно ширше за інші.
